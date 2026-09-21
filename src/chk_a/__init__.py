"""chk-a: Multi-agent DNS A-record anomaly detector."""

from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("chk-a")
except Exception:
    __version__ = "0.1.0"
