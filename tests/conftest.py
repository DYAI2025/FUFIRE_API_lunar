import os
import sys
from pathlib import Path

import pytest

# Ensure repository root is importable when running pytest without installation.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _se1_files_available() -> bool:
    """Check if Swiss Ephemeris SE1 files are available."""
    from bazi_engine.ephemeris import EPHEMERIS_FILES_REQUIRED, _resolve_ephe_path
    path = _resolve_ephe_path(None)
    return all((path / name).exists() for name in EPHEMERIS_FILES_REQUIRED)


_HAS_SE1 = _se1_files_available()

# If SE1 files are not present and EPHEMERIS_MODE is not explicitly set,
# default to MOSEPH so the bulk of the test suite can still run.
# Tests that specifically validate SWIEPH behavior should use @pytest.mark.swieph.
if not os.environ.get("EPHEMERIS_MODE") and not _HAS_SE1:
    os.environ["EPHEMERIS_MODE"] = "MOSEPH"


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "swieph: requires Swiss Ephemeris SE1 files")


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.swieph tests when SE1 files are not available."""
    if _HAS_SE1:
        return
    skip_swieph = pytest.mark.skip(reason="SE1 files not available (set SE_EPHE_PATH)")
    for item in items:
        if "swieph" in item.keywords:
            item.add_marker(skip_swieph)


@pytest.fixture(autouse=True)
def clear_transit_caches():
    """Clear transit caches between tests to prevent order-dependent results."""
    from bazi_engine.transit import _timeline_cache, _transit_cache
    _transit_cache.clear()
    _timeline_cache.clear()
    yield
    _transit_cache.clear()
    _timeline_cache.clear()


@pytest.fixture(autouse=True)
def clear_ephemeris_cache():
    """Clear ensure_ephemeris_files LRU cache between tests."""
    from bazi_engine.ephemeris import ensure_ephemeris_files
    ensure_ephemeris_files.cache_clear()
    yield
    ensure_ephemeris_files.cache_clear()


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi in-memory rate limit counters between tests."""
    from bazi_engine.limiter import reset_limiter_storage
    reset_limiter_storage()
    yield
    reset_limiter_storage()
