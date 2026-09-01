"""ML / Baseline Agent — online learning with exponential decay (Loop 3).

Maintains a per-FQDN decayed counter of A-record IPs learned from the consensus
majority. The counter is updated incrementally every cycle (no batch retraining,
no heavy ML deps). Anomaly scoring compares the current observed IP set against
the normalized baseline using a total-variation style distance.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from ..models.schemas import ConsensusResult, MLConfig
from ..storage.baseline_store import BaselineStore
from ..utils.logger import setup_logger


class MLAgent:
    """Incremental baseline learner and anomaly scorer for one or more FQDNs."""

    def __init__(
        self,
        config: MLConfig,
        storage: BaselineStore,
        logger_name: str = "chk_a.ml",
    ) -> None:
        self.config = config
        self.storage = storage
        self.logger = setup_logger(logger_name)
        # In-memory mirror of the per-FQDN counters for fast scoring.
        self._counters: dict[str, Counter[str]] = {}
        self._samples: dict[str, int] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Hydrate in-memory counters from the persistent store."""
        for fqdn in self.storage.all_fqdns():
            raw = self.storage.get_raw(fqdn)
            if not raw:
                continue
            self._counters[fqdn] = Counter(
                {ip: float(v) for ip, v in raw.get("counter", {}).items()}
            )
            self._samples[fqdn] = int(raw.get("sample_count", 0))

    # -- learning ----------------------------------------------------------
    def learn(self, consensus: ConsensusResult) -> None:
        """Update the baseline for ``consensus.fqdn`` from its majority IPs.

        Implements an exponential-decay counter (the "Counter[IP] with
        exponential decay" state described in the Loop 3 spec):

          * every cycle the *whole* counter is decayed by ``(1 - baseline_decay)``
            so stale IPs are gradually forgotten (this is what lets a *gradual
            drift* scenario settle on the new IP instead of keeping the old one
            frozen at its peak weight);
          * the current ``majority_ips`` are then reinforced by ``+1`` each.

        The updated baseline is persisted atomically to the store.
        """
        fqdn = consensus.fqdn
        decay = self.config.baseline_decay
        counter = self._counters.setdefault(fqdn, Counter())

        # Exponential decay of the whole counter (forgetting factor 1 - decay).
        if decay > 0.0:
            for ip in list(counter.keys()):
                counter[ip] *= 1.0 - decay
                if counter[ip] <= 1e-9:
                    del counter[ip]

        # Reinforce the current majority IPs.
        for ip in consensus.majority_ips:
            counter[ip] += 1.0

        self._samples[fqdn] = self._samples.get(fqdn, 0) + 1

        # Persist atomically (temp file + os.replace inside BaselineStore.save).
        self.storage.set_raw(fqdn, dict(counter), self._samples[fqdn])
        self.storage.save()

    # -- scoring -----------------------------------------------------------
    def score(self, fqdn: str, observed_ips: Iterable[str]) -> float:
        """Return an anomaly score in ``[0, 1]`` for ``observed_ips`` vs baseline.

        ``0.0`` means fully consistent with the baseline; ``1.0`` means no overlap
        at all. Returns ``0.0`` (not enough data to judge) until
        ``min_samples_before_alert`` samples have been learned for ``fqdn``.

        The score is ``1 - overlap`` where ``overlap`` is the sum over the union
        of baseline and observed IPs of ``min(baseline_prob[ip], observed_prob[ip])``
        (a total-variation style distance). ``observed_prob`` is uniform over the
        observed IPs.
        """
        observed = set(observed_ips)
        n = self._samples.get(fqdn, 0)
        if n < self.config.min_samples_before_alert:
            return 0.0

        baseline = self._normalize(self._counters.get(fqdn, Counter()))
        if not baseline:
            return 0.0
        if not observed:
            # Baseline expects IPs but nothing was observed -> full anomaly.
            return 1.0

        observed_probs = {ip: 1.0 / len(observed) for ip in observed}
        union = set(baseline) | observed
        overlap = sum(min(baseline.get(ip, 0.0), observed_probs.get(ip, 0.0)) for ip in union)
        return 1.0 - overlap

    def get_baseline(self, fqdn: str) -> dict[str, float]:
        """Return the normalized baseline probabilities for ``fqdn`` (empty if none)."""
        return self._normalize(self._counters.get(fqdn, Counter()))

    def sample_count(self, fqdn: str) -> int:
        """Return the number of baseline samples learned for ``fqdn``."""
        return self._samples.get(fqdn, 0)

    def all_fqdns(self) -> list[str]:
        """Return every FQDN that currently has a stored baseline."""
        return self.storage.all_fqdns()

    @staticmethod
    def _normalize(counter: Counter[str]) -> dict[str, float]:
        total = sum(counter.values())
        if total <= 0.0:
            return {}
        return {ip: v / total for ip, v in counter.items()}


__all__ = ["MLAgent"]
