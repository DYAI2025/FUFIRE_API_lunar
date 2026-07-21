Phase-specific instructions for the **Code** phase. Extends [../CLAUDE.md](../CLAUDE.md).

## Purpose

This phase contains the **implementation**. Focus on clean, tested, maintainable code.

---

## Components

### Calculation Engine

- **Directory**: [`engine/`](engine/)
- **Technology**: Python 3.10+ / Swiss Ephemeris
- **Responsibility**: Deterministic astronomical calculations — BaZi pillars, Western chart, Wu-Xing vectors, fusion, transit, aspects, phases, narrative
- **Source**: `bazi_engine/` Levels 0–4

### API Layer

- **Directory**: [`api/`](api/)
- **Technology**: Python / FastAPI / slowapi / Pydantic v2
- **Responsibility**: HTTP routers, middleware, rate limiting, auth, OpenAPI contract, CLI
- **Source**: `bazi_engine/` Level 5 (app.py, cli.py, middleware.py, limiter.py, routers/)

### External Services

- **Directory**: [`services/`](services/)
- **Technology**: Python / httpx / Pydantic v2
- **Responsibility**: Superglue proxy (ElevenLabs), geocoding, soulprint, daily generators
- **Source**: `bazi_engine/services/`, `bazi_engine/routers/superglue.py`

### BAFE — Contract-First Validation

- **Directory**: [`bafe/`](bafe/)
- **Technology**: Python / jsonschema / Pydantic v2
- **Responsibility**: JSON Schema (Draft-07) validation for `/validate` endpoint
- **Source**: `bazi_engine/bafe/`

---

## Component Isolation

All source code, configuration, and assets for a component **must reside within that component's directory**. Specifically:

- **No code outside component directories** — never place source files, configuration files, or build artifacts in `3-code/` itself or anywhere else outside the owning component's directory.
- **No cross-component configuration** — configuration that spans multiple components should never be necessary. If such a situation arises, treat it as a potential design flaw or incorrect component separation. Stop work, notify the user with a clear description of the conflict, and propose alternative actions (e.g., refactoring responsibilities, introducing a new component, or adjusting the design).
- **Do not rename or move component directories** — the directory names listed above are fixed; renaming or relocating them breaks cross-phase references and tooling assumptions.

---

## Build Commands

Scripts and commands for each component are documented in that component's own codebase (package.json, Makefile, README, or equivalent). Check there first.

When invoking any command, apply active decisions from the component's `CLAUDE.component.md` whose trigger conditions match.

---

## Task Tracking

All development tasks are tracked in [`tasks.md`](tasks.md).

To create the initial implementation plan (phased tasks from design artifacts), run `/SDLC-implementation-plan`. This should be done after `/SDLC-decompose` and before starting any coding work.

---

## Linking to Other Phases

- Implementation follows designs in `2-design/`
- Tests verify requirements from `1-spec/`
- Infrastructure code goes in `4-deploy/`; when a coding task modifies IaC, the deploy phase instructions ([`CLAUDE.deploy.md`](../4-deploy/CLAUDE.deploy.md)) apply as well
