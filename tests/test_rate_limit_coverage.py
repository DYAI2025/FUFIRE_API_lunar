"""FUFIRE-004 guard: every API-key-protected route carries @limiter.limit.

Without default_limits/SlowAPIMiddleware, a route missing the decorator is
completely unlimited — an authenticated free-tier key could hammer ephemeris-
heavy endpoints unboundedly. This test makes that class of bug impossible.
"""
from fastapi.routing import APIRoute

from bazi_engine.app import app
from bazi_engine.limiter import limiter

# Routes that are deliberately NOT rate-limited must be listed here with a reason.
UNLIMITED_ALLOWLIST: set[str] = set()


def _is_protected(route: APIRoute) -> bool:
    # d.call may be a plain function OR a class instance (e.g. APIKeyHeader),
    # which has no __name__ — fall back to the type name for those.
    names = {
        getattr(d.call, "__name__", type(d.call).__name__)
        for d in route.dependant.dependencies
        if d.call is not None
    }
    return "require_api_key" in names


def _is_limited(route: APIRoute) -> bool:
    # slowapi keys both registries by "<module>.<qualname>" (extension.py:698-704).
    # Static string limits land in _route_limits; callable limits (our
    # tier_limit) land in _dynamic_route_limits — check both.
    fn = route.endpoint
    key = f"{fn.__module__}.{fn.__qualname__}"
    return key in limiter._route_limits or key in limiter._dynamic_route_limits


def test_every_protected_route_is_rate_limited() -> None:
    missing = sorted(
        {
            f"{sorted(r.methods)} {r.path}"
            for r in app.routes
            if isinstance(r, APIRoute)
            and _is_protected(r)
            and not _is_limited(r)
            and r.path not in UNLIMITED_ALLOWLIST
        }
    )
    assert not missing, "Protected routes without @limiter.limit:\n" + "\n".join(missing)
