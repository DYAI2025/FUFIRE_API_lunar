# Adding an endpoint

The engine's HTTP surface is deliberately cheap to extend: a new endpoint is a
router module plus **one line** in the mount registry. This checklist keeps new
endpoints consistent with the frozen contract, the rate-limit invariant, and the
import hierarchy.

## Checklist

1. **Router module** — add `bazi_engine/routers/<domain>.py`. The router only
   translates HTTP (parse request → call a domain function → shape the
   response). All calculation logic lives in a domain module at Level ≤ 4
   (`bazi.py`, `fusion.py`, `wuxing/`, …). Never put business logic in the
   router or in `app.py`.

2. **Rate limiting** — every handler on a protected router gets, directly under
   the `@router.<method>(...)` decorator:
   ```python
   @router.post("/thing", response_model=ThingResponse)
   @limiter.limit(tier_limit)
   def thing_endpoint(request: Request, req: ThingRequest) -> ...:
   ```
   `request: Request` **must** be the first parameter — slowapi requires it.
   `tests/test_rate_limit_coverage.py` fails the build if a protected route is
   missing the decorator (there is no default limit; undecorated = unlimited).

3. **Mount it** — add one `Mount(...)` line to `bazi_engine/routers/registry.py`.
   The default is dual-mount (legacy + `/v1`, protected). Deviations need a
   documented reason, following the existing rows:
   - public (no API key) → `protected=False` (see `info`)
   - `/v1`-only new B2B surface → `legacy_prefix=None` (see `match`, `admin`)
   - `/v2`-only revised semantics → `legacy_prefix=None`, `v1_prefix=None`,
     `v2_prefix="/v2"` (see `astronomy`)
   - internal / schema-hidden → `include_in_schema=False`, `v1_prefix=None`
     (see `webhooks`)

4. **Boundary tests** — assert at the real HTTP boundary via `TestClient` on
   `resp.json()` / `resp.text` / `resp.headers`, never on internal objects
   (the WS-A convention — see the Testing section of `CLAUDE.md`). Cover the
   happy path, auth (401 without a key when required), and validation (422).

5. **Regenerate the contract** — the OpenAPI spec is the source of truth and CI
   fails on drift:
   ```bash
   python scripts/export_openapi.py
   git add spec/openapi/openapi.json
   ```

6. **Regenerate the route-table golden** — intentionally, since the route set
   changed:
   ```bash
   python tests/golden/regen_route_table.py
   git add tests/golden/route_table.json
   ```
   (`tests/test_app_composition.py` compares against this snapshot.)

7. **Register in the import hierarchy** — add `routers.<domain>` to the `LAYERS`
   map in `tests/test_import_hierarchy.py` (Level 5). Unregistered modules are
   skipped, not enforced.

8. **Bump the engine build label if the surface changed** — update
   `bazi_engine/__init__.py` `__version__` (release-please owns
   `pyproject.toml`'s `version` automatically; never hand-edit that one),
   then re-run `scripts/export_openapi.py`
   (`tests/test_openapi_spec_version.py` guards the pairing).

9. **Sync the LIVE mirror** — the BFF consumes the engine spec. After merging,
   run the engine→LIVE sync (see the LIVE repo, plan Phase 4) so
   `src/api/openapi.json` + `public/openapi.json` track the new artifact.

## Why it's this shape

`app.py` is a thin factory: production-auth guard → `FastAPI(...)` →
middleware/CORS → `register_exception_handlers` → `mount_all` →
`install_custom_openapi`. The mount table, the OpenAPI post-processing, and the
exception handlers each live in their own module (`routers/registry.py`,
`openapi_ext.py`, `error_handlers.py`), so adding an endpoint touches the
registry — not the composition root.
