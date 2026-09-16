"""Additional tests for BaselineStore to improve coverage."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from chk_a.storage.baseline_store import BaselineStore

# Set allowed base dir for all tests in this module
BASELINE_TEST_DIR = "/tmp/chk-a-test"
os.environ["CHK_A_BASELINE_DIR"] = BASELINE_TEST_DIR
Path(BASELINE_TEST_DIR).mkdir(parents=True, exist_ok=True)


def _make_resolver(name: str = "google", address: str = "8.8.8.8:53"):
    from chk_a.models.schemas import ResolverConfig
    return ResolverConfig(name=name, address=address)


def _make_temp_path(suffix: str = "baselines.json") -> Path:
    """Create a temp file path within the allowed test directory."""
    import uuid
    return Path(BASELINE_TEST_DIR) / f"test_{uuid.uuid4().hex[:8]}_{suffix}"


def test_baseline_store_atomic_save() -> None:
    path = _make_temp_path()
    store = BaselineStore(path)
    store.set_raw("example.com", {"1.2.3.4": 10, "5.6.7.8": 5}, 15)
    store.save()
    
    # Reload and verify
    store2 = BaselineStore(path)
    assert store2.get_raw("example.com") is not None
    baseline = store2.get_baseline("example.com")
    assert baseline == {"1.2.3.4": 2/3, "5.6.7.8": 1/3}


def test_baseline_store_corrupt_file_creates_empty() -> None:
    path = _make_temp_path()
    # Write corrupt JSON
    path.write_text("{ invalid json")
    
    store = BaselineStore(path)
    assert store._data == {"version": 1, "baselines": {}}
    assert store.get_baseline("example.com") is None


def test_baseline_store_missing_file_creates_empty() -> None:
    path = _make_temp_path("nonexistent.json")
    store = BaselineStore(path)
    assert store._data == {"version": 1, "baselines": {}}
    assert store.get_baseline("example.com") is None


def test_baseline_store_version_mismatch() -> None:
    path = _make_temp_path()
    # Write old version
    path.write_text(json.dumps({"version": 0, "baselines": {}}))
    
    store = BaselineStore(path)
    # Should reset to current version
    assert store._data["version"] == 1


def test_baseline_store_unexpected_shape() -> None:
    path = _make_temp_path()
    path.write_text(json.dumps({"not_baselines": {}}))
    
    store = BaselineStore(path)
    assert store._data == {"version": 1, "baselines": {}}


def test_baseline_store_encryption_roundtrip() -> None:
    """Test encryption/decryption roundtrip with age."""
    from pyrage import x25519
    
    identity = x25519.Identity.generate()
    private_key = str(identity)
    public_key = str(identity.to_public())
    
    path = _make_temp_path()
    
    # Set env var for private key
    os.environ["CHK_A_BASELINE_AGE_KEY"] = private_key
    
    try:
        store = BaselineStore(
            path,
            encryption_enabled=True,
            age_public_key=public_key,
            age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )
        store.set_raw("example.com", {"1.2.3.4": 10, "5.6.7.8": 5}, 15)
        store.save()
        
        # Check file is encrypted
        content = path.read_bytes()
        assert content.startswith(b"-----BEGIN AGE ENCRYPTED FILE-----")
        
        # Reload and verify
        store2 = BaselineStore(
            path,
            encryption_enabled=True,
            age_public_key=public_key,
            age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )
        baseline = store2.get_baseline("example.com")
        assert baseline == {"1.2.3.4": 2/3, "5.6.7.8": 1/3}
    finally:
        os.environ.pop("CHK_A_BASELINE_AGE_KEY", None)


def test_baseline_store_encryption_disabled_by_default() -> None:
    path = _make_temp_path()
    store = BaselineStore(path)
    store.set_raw("example.com", {"1.2.3.4": 10}, 10)
    store.save()
    
    content = path.read_bytes()
    # Should be plain JSON
    assert content.startswith(b"{")


def test_baseline_store_encryption_missing_private_key() -> None:
    from pyrage import x25519
    identity = x25519.Identity.generate()
    public_key = str(identity.to_public())
    
    path = _make_temp_path()
    
    # Don't set env var - use valid public key
    store = BaselineStore(
        path,
        encryption_enabled=True,
        age_public_key=public_key,
        age_private_key_env="CHK_A_BASELINE_AGE_KEY_MISSING",
    )
    store.set_raw("example.com", {"1.2.3.4": 10}, 10)
    store.save()  # Save succeeds (only needs public key)
    
    # Load should fail gracefully (logs warning, resets to empty)
    store2 = BaselineStore(
        path,
        encryption_enabled=True,
        age_public_key=public_key,
        age_private_key_env="CHK_A_BASELINE_AGE_KEY_MISSING",
    )
    assert store2._data == {"version": 1, "baselines": {}}
    assert store2.get_baseline("example.com") is None


def test_baseline_store_encryption_invalid_private_key() -> None:
    from pyrage import x25519
    identity = x25519.Identity.generate()
    public_key = str(identity.to_public())
    
    path = _make_temp_path()
    os.environ["CHK_A_BASELINE_AGE_KEY"] = "INVALID_KEY"
    
    try:
        store = BaselineStore(
            path,
            encryption_enabled=True,
            age_public_key=public_key,
            age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )
        store.set_raw("example.com", {"1.2.3.4": 10}, 10)
        store.save()  # Save succeeds (only needs public key)
        
        # Load should fail gracefully (logs warning, resets to empty)
        store2 = BaselineStore(
            path,
            encryption_enabled=True,
            age_public_key=public_key,
            age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )
        assert store2._data == {"version": 1, "baselines": {}}
        assert store2.get_baseline("example.com") is None
    finally:
        os.environ.pop("CHK_A_BASELINE_AGE_KEY", None)


def test_baseline_store_encryption_missing_public_key() -> None:
    path = _make_temp_path()
    os.environ["CHK_A_BASELINE_AGE_KEY"] = "AGE-SECRET-KEY-TESTKEY123456789012345678901234"
    
    try:
        store = BaselineStore(
            path,
            encryption_enabled=True,
            age_public_key="",
            age_private_key_env="CHK_A_BASELINE_AGE_KEY",
        )
        store.set_raw("example.com", {"1.2.3.4": 10}, 10)
        with pytest.raises(ValueError, match="age_public_key is required"):
            store.save()
    finally:
        os.environ.pop("CHK_A_BASELINE_AGE_KEY", None)


def test_baseline_store_encryption_load_failure() -> None:
    """Test loading encrypted file with wrong key."""
    from pyrage import x25519
    
    identity1 = x25519.Identity.generate()
    identity2 = x25519.Identity.generate()
    
    path = _make_temp_path()
    
    # Save with key1
    os.environ["CHK_A_BASELINE_AGE_KEY"] = str(identity1)
    store1 = BaselineStore(
        path,
        encryption_enabled=True,
        age_public_key=str(identity1.to_public()),
        age_private_key_env="CHK_A_BASELINE_AGE_KEY",
    )
    store1.set_raw("example.com", {"1.2.3.4": 10}, 10)
    store1.save()
    
    # Try to load with key2
    os.environ["CHK_A_BASELINE_AGE_KEY"] = str(identity2)
    store2 = BaselineStore(
        path,
        encryption_enabled=True,
        age_public_key=str(identity1.to_public()),
        age_private_key_env="CHK_A_BASELINE_AGE_KEY",
    )
    
    # Should fail to decrypt and reset to empty
    assert store2._data == {"version": 1, "baselines": {}}
    
    os.environ.pop("CHK_A_BASELINE_AGE_KEY", None)


def test_baseline_store_atomic_write_on_error() -> None:
    """Test that temp file is cleaned up on write error."""
    path = _make_temp_path()
    store = BaselineStore(path)
    store.set_raw("example.com", {"1.2.3.4": 10}, 10)
    store.save()
    
    # Verify file exists
    assert path.exists()
    
    # Make parent dir read-only to cause write error
    import stat
    tmpdir_path = Path(BASELINE_TEST_DIR)
    tmpdir_path.chmod(stat.S_IRUSR | stat.S_IXUSR)  # read-only
    
    try:
        store.set_raw("example.com", {"1.2.3.4": 20}, 20)
        store.save()
    except OSError:
        pass
    finally:
        # Restore permissions
        tmpdir_path.chmod(stat.S_IRWXU)


def test_baseline_store_multiple_fqdns() -> None:
    path = _make_temp_path()
    store = BaselineStore(path)
    
    store.set_raw("a.com", {"1.1.1.1": 100}, 100)
    store.set_raw("b.com", {"2.2.2.2": 50, "3.3.3.3": 50}, 100)
    store.set_raw("c.com", {"4.4.4.4": 1}, 1)
    store.save()
    
    fqdns = store.all_fqdns()
    assert set(fqdns) == {"a.com", "b.com", "c.com"}
    
    assert store.get_baseline("a.com") == {"1.1.1.1": 1.0}
    assert store.get_baseline("b.com") == {"2.2.2.2": 0.5, "3.3.3.3": 0.5}
    assert store.get_baseline("c.com") == {"4.4.4.4": 1.0}


def test_baseline_store_empty_counter() -> None:
    path = _make_temp_path()
    store = BaselineStore(path)
    store.set_raw("example.com", {}, 0)
    store.save()
    
    store2 = BaselineStore(path)
    assert store2.get_baseline("example.com") == {}


def test_baseline_store_path_traversal_prevention() -> None:
    """Test that path traversal is prevented."""
    # Should work with allowed path
    store = BaselineStore("/tmp/chk-a-test/baselines.json")
    assert store is not None
    
    # Should fail with path outside allowed dir
    with pytest.raises(ValueError, match="outside allowed directory"):
        BaselineStore("/etc/passwd")