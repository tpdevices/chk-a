"""Resolver Agent — parallel DNS A-record queries with health tracking.

The agent receives a list of :class:`ResolverConfig` objects and can query any
FQDN concurrently across all of them. Each resolver is queried independently
with its own timeout; results come back as one :class:`CheckResult` per resolver.

Per-resolver health (success-rate EMA and latency EMA) is tracked so later
agents (Consensus, ML, Alert) can weight or distrust flaky resolvers.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import dns.asyncresolver
import dns.exception
import dns.resolver

from ..models.schemas import CheckResult, ResolverConfig
from ..utils.logger import setup_logger


@dataclass
class ResolverHealth:
    """Per-resolver health metrics using exponential moving averages."""

    success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    total_queries: int = 0
    successful_queries: int = 0

    def record(self, latency_ms: float, success: bool, alpha: float = 0.1) -> None:
        """Update EMA metrics for one completed query."""
        self.total_queries += 1
        if success:
            self.successful_queries += 1
            self.success_rate = (1 - alpha) * self.success_rate + alpha * 1.0
            if self.avg_latency_ms == 0.0:
                self.avg_latency_ms = latency_ms
            else:
                self.avg_latency_ms = (1 - alpha) * self.avg_latency_ms + alpha * latency_ms
        else:
            self.success_rate = (1 - alpha) * self.success_rate + alpha * 0.0

    @property
    def weight_factor(self) -> float:
        """Health-adjusted weight factor in [0, 1] for consensus voting."""
        return max(0.0, min(1.0, self.success_rate))


class ResolverAgent:
    """Queries A records for an FQDN from multiple resolvers concurrently."""

    def __init__(
        self,
        resolvers: list[ResolverConfig],
        logger_name: str = "chk_a.resolver",
        max_concurrent: int = 10,
    ) -> None:
        self.resolvers: dict[str, ResolverConfig] = {r.name: r for r in resolvers}
        self.health: dict[str, ResolverHealth] = {name: ResolverHealth() for name in self.resolvers}
        self.max_concurrent = max_concurrent
        self.logger = setup_logger(logger_name)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._instances: dict[str, dns.asyncresolver.Resolver] = {}
        self._doh_names: set[str] = set()
        for name, cfg in self.resolvers.items():
            if cfg.address.startswith(("http://", "https://")):
                # DoH is tracked but not resolved in Loop 1.
                self._doh_names.add(name)
                self._instances[name] = dns.asyncresolver.Resolver(configure=False)
            else:
                self._instances[name] = self._build_resolver(cfg)

    @staticmethod
    def _build_resolver(cfg: ResolverConfig) -> dns.asyncresolver.Resolver:
        """Create a configured async resolver instance for ``cfg``."""
        resolver = dns.asyncresolver.Resolver(configure=False)
        addr = cfg.address
        if ":" in addr:
            host, port_str = addr.rsplit(":", 1)
            port = int(port_str)
        else:
            host, port = addr, 53
        resolver.nameservers = [host]
        resolver.port = port
        timeout = cfg.timeout_ms / 1000.0
        resolver.timeout = timeout
        resolver.lifetime = timeout
        return resolver

    async def check_fqdn(self, fqdn: str) -> list[CheckResult]:
        """Query every configured resolver for ``fqdn`` and return results."""
        tasks = [self._query_one(fqdn, name) for name in self.resolvers]
        return await asyncio.gather(*tasks)

    async def _query_one(self, fqdn: str, resolver_name: str) -> CheckResult:
        """Query a single resolver, recording health and returning a CheckResult."""
        resolver = self._instances[resolver_name]
        start = time.perf_counter()
        try:
            if resolver_name in self._doh_names:
                raise NotImplementedError("DoH resolver not yet supported")
            async with self._semaphore:
                answer = await resolver.resolve(fqdn, rdtype="A")
            latency_ms = (time.perf_counter() - start) * 1000.0
            ips = [str(rdata) for rdata in answer]
            self.health[resolver_name].record(latency_ms, True)
            return CheckResult(
                fqdn=fqdn,
                resolver=resolver_name,
                ips=ips,
                latency_ms=round(latency_ms, 2),
                success=True,
            )
        except dns.resolver.NXDOMAIN:
            return self._failure(fqdn, resolver_name, start, "NXDOMAIN")
        except dns.resolver.NoAnswer:
            return self._failure(fqdn, resolver_name, start, "NO_ANSWER")
        except dns.resolver.NoNameservers:
            return self._failure(fqdn, resolver_name, start, "NO_NAMESERVERS")
        except dns.exception.Timeout:
            return self._failure(fqdn, resolver_name, start, "TIMEOUT")
        except NotImplementedError:
            return self._failure(fqdn, resolver_name, start, "DOH_NOT_SUPPORTED")
        except dns.exception.DNSException as exc:
            return self._failure(fqdn, resolver_name, start, f"DNS_ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001 - one resolver must not crash the cycle
            return self._failure(fqdn, resolver_name, start, f"UNEXPECTED: {exc}")

    def _failure(self, fqdn: str, resolver_name: str, start: float, error: str) -> CheckResult:
        latency_ms = (time.perf_counter() - start) * 1000.0
        self.health[resolver_name].record(latency_ms, False)
        return CheckResult(
            fqdn=fqdn,
            resolver=resolver_name,
            latency_ms=round(latency_ms, 2),
            success=False,
            error=error,
        )


__all__ = ["ResolverAgent", "ResolverHealth"]
