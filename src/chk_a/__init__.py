"""chk-a: Multi-agent DNS A-record anomaly detector."""

from importlib.metadata import version as _pkg_version, PackageNotFoundError

def _get_version() -> str:
    """Get package version, trying multiple methods."""
    # Method 1: importlib.metadata (works when installed as package)
    try:
        return _pkg_version("chk-a")
    except PackageNotFoundError:
        pass
    except Exception:
        pass
    
    # Method 2: Read from .dist-info/METADATA directly (installed package)
    try:
        from pathlib import Path
        import sys
        # Check site-packages for chk_a-*.dist-info/METADATA
        for path in sys.path:
            dist_info_dirs = Path(path).glob("chk_a-*.dist-info")
            for dist_info in dist_info_dirs:
                metadata_file = dist_info / "METADATA"
                if metadata_file.exists():
                    content = metadata_file.read_text()
                    import re
                    match = re.search(r"^Version:\s*(.+)$", content, re.MULTILINE)
                    if match:
                        return match.group(1).strip()
    except Exception:
        pass
    
    # Method 3: Read from pyproject.toml (development)
    try:
        from pathlib import Path
        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        if pyproject_path.exists():
            import re
            content = pyproject_path.read_text()
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                return match.group(1)
    except Exception:
        pass
    
    # Fallback
    return "0.1.0"

__version__ = _get_version()
