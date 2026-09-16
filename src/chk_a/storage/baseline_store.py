"""Atomic JSON baseline store for the ML Agent (Loop 3).

Persists per-FQDN decayed IP counters and sample counts to a JSON file using an
atomic write (temp file + ``os.replace``) so a crash mid-write can never leave a
corrupt baseline behind. The file is loaded on startup.

SEC-015: Optional encryption at rest using age (via pyrage).
When enabled, the baseline file is encrypted on save and decrypted on load.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pyrage

from ..utils.logger import setup_logger

_SCHEMA_VERSION = 1

# SEC-002: Allowed base directory for baseline stores (prevents path traversal)
# Can be overridden via environment variable for testing
def _get_allowed_base_dir() -> Path:
    return Path(os.getenv("CHK_A_BASELINE_DIR", "/var/lib/chk-a")).resolve()


class BaselineStore:
    """JSON-backed store for ML baselines, loaded on startup, saved atomically.
    
    Supports optional age encryption at rest (SEC-015).
    """

    def __init__(
        self,
        path: str | os.PathLike,
        logger_name: str = "chk_a.storage",
        encryption_enabled: bool = False,
        age_public_key: str = "",
        age_private_key_env: str = "CHK_A_BASELINE_AGE_KEY",
    ) -> None:
        # SEC-002: Validate path to prevent path traversal
        resolved_path = Path(path).resolve()
        if not self._is_path_allowed(resolved_path):
            raise ValueError(
                f"Baseline store path '{resolved_path}' is outside allowed directory '{_get_allowed_base_dir()}'"
            )
        self.path = resolved_path
        self.logger = setup_logger(logger_name)
        self._data: dict[str, Any] = {"version": _SCHEMA_VERSION, "baselines": {}}
        
        # Encryption settings
        self.encryption_enabled = encryption_enabled
        self.age_public_key = age_public_key
        self.age_private_key_env = age_private_key_env
        
        # Cache for age keys (avoid re-parsing on every save/load)
        # Use lazy loading - only load when actually needed
        self._age_identity = None
        self._age_recipient = None

        self.load()

    @staticmethod
    def _is_path_allowed(path: Path) -> bool:
        """Check if the given path is within the allowed base directory."""
        try:
            path.relative_to(_get_allowed_base_dir())
            return True
        except ValueError:
            return False

    def _load_age_keys(self) -> None:
        """Load and cache age keys at initialization."""
        import pyrage
        # Only load private key when actually needed for decryption
        private_key = os.getenv(self.age_private_key_env)
        if private_key and private_key.startswith("AGE-SECRET-KEY-"):
            try:
                self._age_identity = pyrage.x25519.Identity.from_str(private_key)
            except pyrage.IdentityError:
                # Invalid key format - will be handled when actually used
                pass
        if self.age_public_key:
            try:
                self._age_recipient = pyrage.x25519.Recipient.from_str(self.age_public_key)
            except pyrage.IdentityError:
                # Invalid key format
                pass

    def _get_age_identity(self):
        """Get cached age identity (private key)."""
        if self._age_identity is None:
            self._load_age_keys()
        if self._age_identity is None:
            raise ValueError(
                f"Age private key not found or invalid in environment variable '{self.age_private_key_env}'"
            )
        return self._age_identity

    def _get_age_recipient(self):
        """Get cached age recipient (public key) for encryption."""
        if self._age_recipient is None:
            self._load_age_keys()
        if self._age_recipient is None:
            raise ValueError("age_public_key is required when encryption is enabled")
        return self._age_recipient

    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using age."""
        import pyrage
        recipient = self._get_age_recipient()
        return pyrage.encrypt(data, [recipient], armored=True)

    def _decrypt_data(self, data: bytes) -> bytes:
        """Decrypt data using age."""
        import pyrage
        identity = self._get_age_identity()
        return pyrage.decrypt(data, [identity])

    # -- persistence -------------------------------------------------------
    def load(self) -> None:
        """Load baselines from disk; a missing/corrupt file yields empty state."""
        if not self.path.exists():
            self._data = {"version": _SCHEMA_VERSION, "baselines": {}}
            return
        try:
            with open(self.path, "rb") as fh:
                raw_bytes = fh.read()
            
            if self.encryption_enabled:
                # Decrypt if encryption is enabled
                raw_bytes = self._decrypt_data(raw_bytes)
            
            raw = json.loads(raw_bytes.decode("utf-8"))
            if not isinstance(raw, dict) or "baselines" not in raw:
                raise ValueError("unexpected baseline file shape")
            self._data = {
                "version": _SCHEMA_VERSION,
                "baselines": raw.get("baselines", {}),
            }
        except (json.JSONDecodeError, ValueError, OSError, pyrage.DecryptError) as exc:
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
            data_bytes = json.dumps(self._data, indent=2, sort_keys=True).encode("utf-8")
            
            if self.encryption_enabled:
                data_bytes = self._encrypt_data(data_bytes)
            
            with os.fdopen(tmp_fd, "wb") as fh:
                fh.write(data_bytes)
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
