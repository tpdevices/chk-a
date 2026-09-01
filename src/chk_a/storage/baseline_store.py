"""Atomic JSON baseline store for the ML Agent (Loop 3).

Persists per-FQDN decayed IP counters and sample counts to a JSON file using an
atomic write (temp file + ``os.replace``) so a crash mid-write can never leave a
corrupt baseline behind. The file is loaded on startup.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..utils.logger import setup_logger

_SCHEMA_VERSION = 1


class BaselineStore:
    """JSON-backed store for ML baselines, loaded on startup, saved atomically."""

    def __init__(
        self,
        path: str | os.PathLike,
        logger_name: str = "chk_a.storage",
    ) -> None:
        self.path = Path(path)
        self.logger = setup_logger(logger_name)
        self._data: dict[str, Any] = {"version": _SCHEMA_VERSION, "baselines": {}}
        self.load()

    # -- persistence -------------------------------------------------------
    def load(self) -> None:
        """Load baselines from disk; a missing/corrupt file yields empty state."""
        if not self.path.exists():
            self._data = {"version": _SCHEMA_VERSION, "baselines": {}}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict) or "baselines" not in raw:
                raise ValueError("unexpected baseline file shape")
            self._data = {
                "version": _SCHEMA_VERSION,
                "baselines": raw.get("baselines", {}),
            }
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            self.logger.warning("Could not load baseline store %s: %s", self.path, exc)
            self._data = {"version": _SCHEMA_VERSION, "baselines": {}}

    def save(self) -> None:
        """Atomically persist baselines (temp file + ``os.replace``)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=str(self.path.parent),
            suffix=".tmp",
            prefix=f".{self.path.name}",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except OSError:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # -- access ------------------------------------------------------------
    def get_raw(self, fqdn: str) -> dict[str, Any] | None:
        """Return the raw baseline record for ``fqdn`` or ``None``."""
        return self._data["baselines"].get(fqdn)

    def set_raw(
        self,
        fqdn: str,
        counter: dict[str, float],
        sample_count: int,
    ) -> None:
        """Replace the raw baseline record for ``fqdn``."""
        self._data["baselines"][fqdn] = {
            "counter": {ip: float(v) for ip, v in counter.items()},
            "sample_count": int(sample_count),
        }

    def get_baseline(self, fqdn: str) -> dict[str, float] | None:
        """Return the normalized baseline probabilities for ``fqdn`` or ``None``."""
        raw = self._data["baselines"].get(fqdn)
        if not raw:
            return None
        return self._normalize(raw.get("counter", {}))

    @staticmethod
    def _normalize(counter: dict[str, float]) -> dict[str, float]:
        total = sum(counter.values())
        if total <= 0.0:
            return {}
        return {ip: v / total for ip, v in counter.items()}

    def all_fqdns(self) -> list[str]:
        """Return the FQDNs that currently have a stored baseline."""
        return list(self._data["baselines"].keys())


__all__ = ["BaselineStore"]
