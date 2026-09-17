"""FUFIRE-004 guard: every API-key-protected route carries @limiter.limit.

Without default_limits/SlowAPIMiddleware, a route missing the decorator is
completely unlimited — an authenticated free-tier key could hammer ephemeris-
heavy endpoints unboundedly. This test makes that class of bug impossible.
"""
from fastapi.routing import APIRoute

from bazi_engine.app import app
from bazi_engine.limiter import infra_limiter, limiter

# Routes that are deliberately NOT rate-limited must be listed here with a reason.
UNLIMITED_ALLOWLIST: set[str] = set()

# FUF-156A: public infrastructure probes. Not API-key protected, so the
# require_api_key sweep above cannot see them, yet each one runs a live
# ephemeris call per request. They are limited by the dedicated memory-only
# ``infra_limiter`` rather than the shared application limiter — see
# bazi_engine/limiter.py for why a Redis outage must stay reportable.
#
# Scope note: the remaining FUF-156 surfaces (GET /api, GET /v1/api,
# POST /internal/api/webhooks/chart) are NOT listed here yet. They are
# deliberately still unimplemented in this slice, and the executable
# audit-hardening security-boundary gate — not this file — is what holds them
# red until then.
INFRA_PROBE_ROUTES: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("GET", "/v1/health"),
    ("GET", "/ready"),
    ("GET", "/v1/ready"),
}


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
    #
    # A route counts as limited when EITHER limiter owns it: the shared
    # application limiter, or the dedicated infrastructure-probe limiter.
    fn = route.endpoint
    key = f"{fn.__module__}.{fn.__qualname__}"
    return any(
        key in lim._route_limits or key in lim._dynamic_route_limits
        for lim in (limiter, infra_limiter)
    )


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


def test_every_infra_probe_route_is_rate_limited() -> None:
    """FUF-156A: the four public health/readiness mounts carry an explicit limit.

    These are unauthenticated, so ``_is_protected`` skips them — without this
    check a missing decorator on a route that runs an ephemeris call per request
    would go unnoticed.
    """
    found: set[tuple[str, str]] = set()
    missing: set[tuple[str, str]] = set()

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            pair = (method, route.path)
            if pair in INFRA_PROBE_ROUTES:
                found.add(pair)
                if not _is_limited(route):
                    missing.add(pair)

    unmounted = INFRA_PROBE_ROUTES - found
    assert not unmounted, f"infra probe routes are not mounted at all: {sorted(unmounted)}"
    assert not missing, "Infra probe routes without an explicit limit:\n" + "\n".join(
        f"{m} {p}" for m, p in sorted(missing)
    )


def test_infra_probe_routes_are_owned_by_the_infra_limiter() -> None:
    """They must be on the memory-only limiter, not the Redis-backed one.

    Putting a readiness probe on the shared limiter is the defect this slice
    exists to prevent: with a required Redis unreachable the shared limiter
    raises, and the probe would report an opaque 500 instead of the structured
    dependency failure it exists to report.
    """
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if (method, route.path) not in INFRA_PROBE_ROUTES:
                continue
            fn = route.endpoint
            key = f"{fn.__module__}.{fn.__qualname__}"
            in_infra = (
                key in infra_limiter._route_limits
                or key in infra_limiter._dynamic_route_limits
            )
            in_app = key in limiter._route_limits or key in limiter._dynamic_route_limits
            assert in_infra, f"{method} {route.path} is not on the infra limiter"
            assert not in_app, (
                f"{method} {route.path} is also on the shared application limiter — "
                "a Redis outage would turn it into an opaque 500"
            )
