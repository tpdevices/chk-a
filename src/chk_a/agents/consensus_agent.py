"""Consensus Agent — weighted majority vote, entropy scoring, resolver reputation.

Takes the per-resolver :class:`CheckResult` list produced by the Resolver Agent
for a single FQDN and produces a :class:`ConsensusResult`:

  * a **weighted majority vote** of the returned A-record IPs
    (``weight = resolver_config.weight * resolver_health.success_rate``)
  * a **consensus_score** in ``[0, 1]`` derived from the normalized Shannon
    entropy of the IP weight distribution (``1`` = full agreement)
  * **outlier** detection for resolvers that disagree while carrying little
    weight (``weight < 0.2 * total_weight``)
  * a running per-resolver **reputation** EMA (agreement with consensus, α=0.05)

The agent is pure computation — no network or I/O — so ``aggregate`` is sync.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from ..models.schemas import CheckResult, ConsensusResult, ResolverConfig
from ..utils.logger import setup_logger

if TYPE_CHECKING:  # avoid a hard import edge at package-init time
    from .resolver_agent import ResolverHealth


class ConsensusAgent:
    """Aggregates resolver results into a weighted consensus for one FQDN."""

    def __init__(
        self,
        resolvers: list[ResolverConfig],
        health: dict[str, "ResolverHealth"] | None = None,
        logger_name: str = "chk_a.consensus",
        reputation_alpha: float = 0.05,
    ) -> None:
        self.resolvers: dict[str, ResolverConfig] = {r.name: r for r in resolvers}
        self.health: dict[str, Any] = health or {}
        self.reputation_alpha = reputation_alpha
        self.reputation: dict[str, float] = {name: 1.0 for name in self.resolvers}
        self.logger = setup_logger(logger_name)

    # -- weight helpers ----------------------------------------------------
    def _resolver_weight(self, name: str) -> float:
        """Effective weight = config weight * health success-rate EMA."""
        cfg = self.resolvers.get(name)
        if cfg is None:
            return 0.0
        sr = 1.0
        h = self.health.get(name)
        if h is not None:
            sr = float(getattr(h, "success_rate", 1.0))
        return cfg.weight * sr

    @staticmethod
    def _normalized_entropy(weights: list[float]) -> float:
        """Shannon entropy of ``weights`` normalized to ``[0, 1]``.

        ``0`` means a single value carries all the weight (full agreement);
        ``1`` means the weight is spread evenly across every value.
        """
        total = sum(weights)
        if total <= 0.0 or len(weights) <= 1:
            return 0.0
        entropy = 0.0
        for w in weights:
            if w <= 0.0:
                continue
            p = w / total
            entropy -= p * math.log2(p)
        norm = entropy / math.log2(len(weights))
        return min(1.0, max(0.0, norm))

    # -- main entry --------------------------------------------------------
    def aggregate(
        self,
        fqdn: str,
        results: list[CheckResult],
        min_consensus: float = 0.6,
    ) -> ConsensusResult:
        """Compute the weighted consensus for ``fqdn`` from ``results``."""
        # Tally IP weights from successful, non-empty results only.
        ip_weight: dict[str, float] = {}
        total_weight = 0.0
        for r in results:
            if not r.success or not r.ips:
                continue
            w = self._resolver_weight(r.resolver)
            if w <= 0.0:
                continue
            total_weight += w
            for ip in r.ips:
                ip_weight[ip] = ip_weight.get(ip, 0.0) + w

        # Majority IPs: cumulative weight >= min_consensus of the total.
        majority_ips: list[str] = []
        if total_weight > 0.0:
            for ip, w in ip_weight.items():
                if w / total_weight >= min_consensus:
                    majority_ips.append(ip)
        majority_ips.sort()

        # Consensus score from the normalized entropy of the IP distribution.
        if total_weight <= 0.0 or not ip_weight:
            consensus_score = 0.0
        else:
            consensus_score = 1.0 - self._normalized_entropy(list(ip_weight.values()))

        # Outlier detection: a successful result whose IPs are not in the
        # majority AND whose resolver weight is < 0.2 * total_weight.
        outliers: list[CheckResult] = []
        if total_weight > 0.0:
            outlier_threshold = 0.2 * total_weight
            majority_set = set(majority_ips)
            for r in results:
                if not r.success or not r.ips:
                    continue
                if set(r.ips) & majority_set:
                    continue
                if self._resolver_weight(r.resolver) < outlier_threshold:
                    outliers.append(r)

        # Reputation EMA: agreement = 1 if any returned IP is in the majority.
        # Only update reputation for SUCCESSFUL results; failed/empty results
        # should not affect reputation (they are not "disagreeing", they just failed).
        majority_set = set(majority_ips)
        for r in results:
            if not r.success or not r.ips:
                # Skip failed/empty results - no reputation change
                continue
            agreement = 1.0 if (set(r.ips) & majority_set) else 0.0
            name = r.resolver
            if name in self.reputation:
                prev = self.reputation[name]
                self.reputation[name] = (
                    1 - self.reputation_alpha
                ) * prev + self.reputation_alpha * agreement

        return ConsensusResult(
            fqdn=fqdn,
            majority_ips=majority_ips,
            consensus_score=round(consensus_score, 4),
            outliers=outliers,
            resolver_reputation=dict(self.reputation),
        )


__all__ = ["ConsensusAgent"]
