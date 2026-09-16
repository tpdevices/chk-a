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
from typing import TYPE_CHECKING

import dns.asyncresolver
import dns.asyncquery
import dns.exception
import dns.nameserver
import dns.resolver

from ..models.schemas import CheckResult, ResolverConfig
from ..utils.logger import setup_logger

if TYPE_CHECKING:
    import aiohttp


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
        max_concurrent: int | None = None,
        default_timeout_ms: int = 2000,
    ) -> None:
        self.resolvers: dict[str, ResolverConfig] = {r.name: r for r in resolvers}
        self.health: dict[str, ResolverHealth] = {name: ResolverHealth() for name in self.resolvers}

        # Use config values or fall back to provided parameters
        if max_concurrent is None:
            # Default fallback if not provided via config
            max_concurrent = 10
        self.max_concurrent = max_concurrent

        self.default_timeout_ms = default_timeout_ms
        self.logger = setup_logger(logger_name)
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._instances: dict[str, dns.asyncresolver.Resolver] = {}
        self._doh_names: set[str] = set()
        self._dot_names: set[str] = set()
        self._doh_sessions: dict[str, "aiohttp.ClientSession"] = {}
        self._dot_nameservers: dict[str, "dns.nameserver.DoTNameserver"] = {}
        for name, cfg in self.resolvers.items():
            if cfg.address.startswith(("http://", "https://")):
                # DoH resolver - will use aiohttp for DNS-over-HTTPS
                self._doh_names.add(name)
                self._instances[name] = None  # No dnspython resolver needed
            elif cfg.address.startswith("tls://"):
                # DoT resolver - will use dnspython's DoTNameserver
                self._dot_names.add(name)
                self._instances[name] = None  # No standard resolver needed
                self._dot_nameservers[name] = self._build_dot_nameserver(cfg)
            else:
                self._instances[name] = self._build_resolver(cfg, self.default_timeout_ms)

    @staticmethod
    def _build_resolver(
        cfg: ResolverConfig, default_timeout_ms: int = 2000
    ) -> dns.asyncresolver.Resolver:
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
        # Use resolver-specific timeout if set, otherwise use default
        timeout = (cfg.timeout_ms or default_timeout_ms) / 1000.0
        resolver.timeout = timeout
        resolver.lifetime = timeout
        return resolver

    def _build_dot_nameserver(self, cfg: ResolverConfig) -> "dns.nameserver.DoTNameserver":
        """Create a DoTNameserver instance for DNS-over-TLS."""
        # Parse tls://host:port format
        addr = cfg.address
        assert addr.startswith("tls://")
        host_port = addr[6:]  # Remove "tls://"
        host, port_str = host_port.rsplit(":", 1)
        port = int(port_str)
        # Resolve hostname to IP address (DoTNameserver requires IP in address field)
        import socket
        try:
            # Get IPv4 address first
            ip = socket.gethostbyname(host)
        except socket.gaierror as e:
            raise ValueError(f"Cannot resolve DoT hostname {host}: {e}")
        # Use resolver-specific timeout if set, otherwise use default
        timeout = (cfg.timeout_ms or self.default_timeout_ms) / 1000.0
        # hostname verification uses the host for SNI
        return dns.nameserver.DoTNameserver(
            address=ip,
            port=port,
            hostname=host,
            verify=True,
        )

    async def _get_doh_session(self, resolver_name: str) -> "aiohttp.ClientSession":
        """Get or create aiohttp ClientSession for DoH resolver."""
        if resolver_name not in self._doh_sessions or self._doh_sessions[resolver_name].closed:
            import aiohttp
            timeout = aiohttp.ClientTimeout(total=self.default_timeout_ms / 1000.0)
            self._doh_sessions[resolver_name] = aiohttp.ClientSession(timeout=timeout)
        return self._doh_sessions[resolver_name]

    async def _query_doh(self, fqdn: str, resolver_name: str) -> CheckResult:
        """Query a DoH resolver via HTTPS using DNS wireformat (RFC 8484)."""
        import dns.message
        import dns.rdatatype
        
        cfg = self.resolvers[resolver_name]
        url = cfg.address
        # Ensure URL has proper path
        if not url.endswith("/dns-query"):
            url = url.rstrip("/") + "/dns-query"
        
        # Build DNS query message in wireformat
        query = dns.message.make_query(fqdn, dns.rdatatype.A)
        wire = query.to_wire()
        
        # Use wireformat (application/dns-message) for broad compatibility
        headers = {
            "Accept": "application/dns-message",
            "Content-Type": "application/dns-message",
        }
        
        session = await self._get_doh_session(resolver_name)
        start = time.perf_counter()
        try:
            async with self._semaphore:
                async with session.post(url, data=wire, headers=headers) as resp:
                    resp.raise_for_status()
                    response_wire = await resp.read()
            latency_ms = (time.perf_counter() - start) * 1000.0
        except Exception as exc:  # noqa: BLE001
            return self._failure(fqdn, resolver_name, start, f"DOH_ERROR: {exc}")
        
        # Parse DNS wireformat response
        try:
            response = dns.message.from_wire(response_wire)
        except Exception as exc:
            return self._failure(fqdn, resolver_name, start, f"DOH_PARSE_ERROR: {exc}")
        
        # Extract A records from answer section
        ips = []
        for rrset in response.answer:
            for rdata in rrset:
                if rdata.rdtype == dns.rdatatype.A:
                    ips.append(str(rdata))
        
        success = len(ips) > 0
        self.health[resolver_name].record(latency_ms, success)
        return CheckResult(
            fqdn=fqdn,
            resolver=resolver_name,
            ips=ips,
            latency_ms=round(latency_ms, 2),
            success=success,
            error=None if ips else "NO_ANSWER",
        )

    async def _query_dot(self, fqdn: str, resolver_name: str) -> CheckResult:
        """Query a DoT resolver via DNS-over-TLS."""
        import dns.message
        import dns.rdatatype
        
        nameserver = self._dot_nameservers[resolver_name]
        start = time.perf_counter()
        try:
            # Build DNS query message
            query = dns.message.make_query(fqdn, dns.rdatatype.A)
            # Use the async backend
            import dns.asyncbackend
            backend = dns.asyncbackend.get_default_backend()
            timeout = (self.resolvers[resolver_name].timeout_ms or self.default_timeout_ms) / 1000.0
            
            async with self._semaphore:
                response = await nameserver.async_query(
                    query,
                    timeout=timeout,
                    source=None,
                    source_port=0,
                    max_size=False,
                    backend=backend,
                    one_rr_per_rrset=False,
                    ignore_trailing=False,
                )
            latency_ms = (time.perf_counter() - start) * 1000.0
            
            # Parse response
            ips = []
            for rrset in response.answer:
                for rdata in rrset:
                    if rdata.rdtype == dns.rdatatype.A:
                        ips.append(str(rdata))
            
            success = len(ips) > 0
            self.health[resolver_name].record(latency_ms, success)
            return CheckResult(
                fqdn=fqdn,
                resolver=resolver_name,
                ips=ips,
                latency_ms=round(latency_ms, 2),
                success=success,
                error=None if ips else "NO_ANSWER",
            )
        except dns.resolver.NXDOMAIN:
            return self._failure(fqdn, resolver_name, start, "NXDOMAIN")
        except dns.resolver.NoAnswer:
            return self._failure(fqdn, resolver_name, start, "NO_ANSWER")
        except dns.exception.Timeout:
            return self._failure(fqdn, resolver_name, start, "TIMEOUT")
        except dns.exception.DNSException as exc:
            return self._failure(fqdn, resolver_name, start, f"DNS_ERROR: {exc}")
        except Exception as exc:  # noqa: BLE001
            return self._failure(fqdn, resolver_name, start, f"DOT_ERROR: {exc}")

    async def check_fqdn(self, fqdn: str) -> list[CheckResult]:
        """Query every configured resolver for ``fqdn`` and return results."""
        tasks = [self._query_one(fqdn, name) for name in self.resolvers]
        return await asyncio.gather(*tasks)

    async def _query_one(self, fqdn: str, resolver_name: str) -> CheckResult:
        """Query a single resolver, recording health and returning a CheckResult."""
        # Handle DoH resolvers
        if resolver_name in self._doh_names:
            return await self._query_doh(fqdn, resolver_name)
        
        # Handle DoT resolvers
        if resolver_name in self._dot_names:
            return await self._query_dot(fqdn, resolver_name)
        
        resolver = self._instances[resolver_name]
        start = time.perf_counter()
        try:
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
