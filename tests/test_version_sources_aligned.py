"""DEV-2026-003 — historical version-drift guard, superseded 2026-07-13.

This test USED to enforce that ``pyproject.toml``'s ``version`` and
``bazi_engine/__init__.py``'s ``__version__`` share the same release-candidate
level, on the theory that they were the same axis manually bumped together.

That's no longer true by design: ``pyproject.toml`` is now owned by
release-please (bumped automatically from Conventional Commits on every
release — see ``release-please-config.json``), while ``__version__`` stays a
separately, manually-curated engine-build label baked into API responses, the
OpenAPI spec, and the golden snapshot fixtures. Requiring them to match would
make every release-please version bump also require a hand-edit here — see
docs/precision/deviations.md's DEV-2026-003 entry for the full history and the
decoupling rationale.

Only the self-contained invariant on ``__version__``'s own shape remains.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_init_version() -> str:
    text = (REPO_ROOT / "bazi_engine" / "__init__.py").read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match, "bazi_engine/__init__.py has no __version__ literal"
    return match.group(1)


def test_init_version_is_consumer_facing_string():
    """Engine version emitted to the API must remain a recognisable
    1.x release-candidate string."""
    init = _read_init_version()
    assert re.match(r"^1\.\d+\.\d+-rc\d+-\d{8}$|^1\.\d+\.\d+rc\d+$", init), (
        f"__version__ = {init!r} does not match the expected "
        "'1.M.P-rcN-YYYYMMDD' or '1.M.PrcN' shape."
    )
