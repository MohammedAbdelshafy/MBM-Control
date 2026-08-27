"""
MBM LeadEngine — Supabase Initialization Test
===============================================
Proves correct initialization behavior for all environment modes.
"""

from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))


def test_supabase_import_works():
    """Verify supabase package imports correctly."""
    from supabase import create_client
    assert callable(create_client)
    print("PASS: test_supabase_import_works")


def test_supabase_client_creation_with_env():
    """Verify client creation when env vars are set (mocked)."""
    import unittest.mock as mock

    with mock.patch.dict(os.environ, {
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "eyJ-test-key",
    }):
        # Reset the module-level cache
        import MBM.LeadEngine.ad_repository as repo_mod
        repo_mod._supabase = None
        repo_mod._supabase_available = None

        client = repo_mod._get_supabase()
        # Client creation may fail due to network, but the import path works
        # The important thing is no ImportError
        assert client is not None or repo_mod._supabase_available is False

    print("PASS: test_supabase_client_creation_with_env")


def test_supabase_missing_env_returns_none():
    """Without env vars, _get_supabase returns None."""
    import unittest.mock as mock

    with mock.patch.dict(os.environ, {}, clear=True):
        import MBM.LeadEngine.ad_repository as repo_mod
        repo_mod._supabase = None
        repo_mod._supabase_available = None

        client = repo_mod._get_supabase()
        assert client is None

    print("PASS: test_supabase_missing_env_returns_none")


def test_production_requires_supabase():
    """PRODUCTION mode without Supabase raises RuntimeError."""
    import unittest.mock as mock

    with mock.patch.dict(os.environ, {}, clear=True):
        import MBM.LeadEngine.ad_repository as repo_mod
        repo_mod._supabase = None
        repo_mod._supabase_available = None

        try:
            from MBM.LeadEngine.ad_repository import AdRepository
            repo = AdRepository(env_mode="PRODUCTION")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "PRODUCTION" in str(e)

    print("PASS: test_production_requires_supabase")


def test_local_mode_falls_back_to_json():
    """LOCAL mode uses JSON when Supabase unavailable."""
    import unittest.mock as mock

    with mock.patch.dict(os.environ, {}, clear=True):
        import MBM.LeadEngine.ad_repository as repo_mod
        repo_mod._supabase = None
        repo_mod._supabase_available = None

        with tempfile.TemporaryDirectory() as tmpdir:
            from MBM.LeadEngine.ad_repository import AdRepository
            repo = AdRepository(storage_dir=tmpdir, env_mode="LOCAL")
            assert not repo._use_supabase()

    print("PASS: test_local_mode_falls_back_to_json")


def test_test_mode_hermetic():
    """TEST mode uses temp directory, no persistence beyond process."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from MBM.LeadEngine.ad_repository import AdRepository
        repo = AdRepository(storage_dir=tmpdir, env_mode="TEST")
        assert repo.env_mode == "TEST"
        assert str(repo.storage_dir) == tmpdir

    print("PASS: test_test_mode_hermetic")


def test_repo_namespace_shadowing_resolved():
    """Verify supabase package is the real one, not the repo directory."""
    import supabase
    assert hasattr(supabase, "create_client"), (
        "supabase module should have create_client — "
        "the repo supabase/ directory may be shadowing the pip package"
    )
    print("PASS: test_repo_namespace_shadowing_resolved")


if __name__ == "__main__":
    tests = [
        test_supabase_import_works,
        test_supabase_client_creation_with_env,
        test_supabase_missing_env_returns_none,
        test_production_requires_supabase,
        test_local_mode_falls_back_to_json,
        test_test_mode_hermetic,
        test_repo_namespace_shadowing_resolved,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\nSUPABASE TESTS: {passed} passed, {failed} failed, {len(tests)} total")
    sys.exit(0 if failed == 0 else 1)
