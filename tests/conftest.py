"""Shared pytest fixtures and configuration for chk-a tests.

Sets up the baseline store directory allowlist so that tests using temporary
directories are not rejected by the SEC-002 path traversal guard in
``BaselineStore.__init__``.

The env var must be set before any ``BaselineStore`` is constructed (including
inside ``build_agents`` in ``main.py`` which uses the config default path).
Setting it here at import time guarantees every test module sees a consistent,
test-friendly allowlist.
"""

import os
from pathlib import Path
import tempfile

# SEC-002 compatibility: allow baseline stores under /tmp so that pytest's
# tmp_path fixture (which lives under /tmp/pytest-of-<user>/...) passes the
# path-traversal guard. Tests that exercise the default production path can
# override via monkeypatch when needed.
os.environ.setdefault("CHK_A_BASELINE_DIR", "/tmp")
os.environ.setdefault("CHK_A_FQDN_DIR", "/tmp/chk-a-test/fqdns")

# Ensure test directories exist
Path("/tmp/chk-a-test/fqdns").mkdir(parents=True, exist_ok=True)


def _make_temp_path(suffix: str = "baselines.json", subdir: str = "") -> Path:
    """Create a temporary file path under /tmp for test isolation."""
    if subdir:
        base_dir = f"/tmp/{subdir}"
        Path(base_dir).mkdir(parents=True, exist_ok=True)
        return Path(tempfile.mktemp(suffix=f"_{suffix.split('/')[-1]}", prefix="test_", dir=base_dir))
    return Path(tempfile.mktemp(suffix=f"_{suffix}", prefix="chk-a-test_", dir="/tmp"))
