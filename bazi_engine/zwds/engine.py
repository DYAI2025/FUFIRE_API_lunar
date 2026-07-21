"""ZWDS-P1-19 — natal engine orchestrator.

Assembles every ZWDS core-seed module into one full ``ZwdsRawResponse`` for a
single immutable ``ruleset_id``. This is the keystone that turns a civil-birth
request into the canonical raw chart contract
(``spec/schemas/zwds/ZwdsRawResponse.schema.json``), reproducing the design-pack
example chart (``docs/zwds/design-pack/response_example_core.json``) for the
formula-derived fields.

Processing order mirrors ``zwds_backend_architecture.md`` "Processing order":

1. load the immutable, hash-locked ruleset;
2. resolve the seed (chronometry + calendar halves) from civil birth input plus
   the ruleset time / late-Zi / leap / year-cycle policies;
3. lay out the twelve palaces (Ming/Shen anchors, Five-Tigers stems);
4. derive the Five-Elements Bureau from the Ming palace;
5. place the 14 major + 4 guide-auxiliary stars;
6. assemble the single canonical ``star_placements[]`` (schema source of truth);
7. assemble ``palaces[]`` (each carries only ``placement_ids`` references);
8. resolve the four transformations for the year stem;
9. compute the twelve San-Fang-Si-Zheng relations;
10. optionally resolve the twelve decadal limits;
11. build ``completeness`` (declared vs emitted star families);
12. graph-validate the chart, fingerprint it, and assemble the full response.

Import surface: ``bazi_engine.zwds.*`` submodules and the standard library only.
It never reaches into ``bazi``/``western``/``fusion``/``impact``/routers/``app``.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Sequence, cast

from bazi_engine.zwds import __zwds_engine_version__, ruleset_repository
from bazi_engine.zwds.bureau import Bureau, five_elements_bureau
from bazi_engine.zwds.decadal import (
    DecadalLimit,
    decadal_direction,
    decadal_limits,
)
from bazi_engine.zwds.decadal import PalaceLike as DecadalPalaceLike
from bazi_engine.zwds.domain import BranchId, StemId
from bazi_engine.zwds.palace import (
    Palace,
    build_palaces,
    ming_branch,
    shen_branch,
)
from bazi_engine.zwds.relations import PalaceLike as RelationsPalaceLike
from bazi_engine.zwds.relations import Relation, relations_for_palaces
from bazi_engine.zwds.ruleset_repository import RulesetRef, load_ruleset
from bazi_engine.zwds.seed import (
    CalendarResolution,
    ChronometryResolution,
    ResolvedZwdsSeed,
    resolve_seed,
)
from bazi_engine.zwds.stars import StarBranch
from bazi_engine.zwds.stars.auxiliary import guide_auxiliary_stars
from bazi_engine.zwds.stars.major import major_stars
from bazi_engine.zwds.trace import chart_fingerprint
from bazi_engine.zwds.transformations import (
    four_transformations,
    transformation_types_by_star,
)
from bazi_engine.zwds.validation import validate_chart_graph

#: Canonical branch order for the chart coordinate system (ZI..HAI).
_BRANCH_ORDER: List[str] = [b.name for b in BranchId]

#: Trace formula id for the Ming-palace derivation step (design-pack example).
_MING_FORMULA_ID: str = "ming-palace.v1"


def _coordinate_system() -> Dict[str, Any]:
    """Return a fresh chart coordinate-system block (schema-constant)."""
    return {
        "branch_index_origin": "ZI_0",
        "branch_order": list(_BRANCH_ORDER),
        "modulus": 12,
    }


def _quality() -> Dict[str, Any]:
    """Return a fresh ``quality`` block for a successful core-seed calculation.

    ``calculation_status`` (the engine produced a result) is kept separate from
    ``source_status`` (the ruleset is a ``SOURCE_NEEDED`` seed, not
    practitioner-reviewed) per the architecture doc's response-ownership rule.
    """
    return {
        "calculation_status": "SUCCESS",
        "source_status": "SOURCE_NEEDED",
        "warnings": [],
        "unresolved_conventions": [
            "School/edition not selected.",
            "Calendar engine is core-seed.",
        ],
        "crosschecks": [
            {
                "oracle_id": "guide-algebra-equivalence",
                "status": "MATCH",
                "note": (
                    "Finite-domain equivalence only; not historical validation."
                ),
            }
        ],
    }


def _provenance() -> List[Dict[str, Any]]:
    """Return a fresh ``provenance[]`` ledger for the core-seed ruleset."""
    return [
        {
            "provenance_id": "src:user-guide",
            "type": "source_document",
            "title": "User-provided ZWDS calculation guide",
            "version": "received-2026-07-11",
            "sha256": None,
            "status": "USER_PROVIDED",
            "license": None,
        },
        {
            "provenance_id": "cmp:iztro-2dfe3ec",
            "type": "implementation_comparator",
            "title": "SylarLong/iztro source comparator",
            "version": "2dfe3ecb41d725b2bea1084bbdfe4dd655e37b13",
            "sha256": None,
            "status": "SOURCE_REVIEWED",
            "license": "MIT",
        },
    ]


def _read_ruleset_json(ruleset_id: str, filename: str) -> Dict[str, Any]:
    """Read one JSON component file of an already-loaded ruleset.

    ``ruleset_id`` must already have passed :func:`load_ruleset` (which
    path-validates the id and hash-locks every component), so the directory
    read here is safe and consistent.
    """
    path = ruleset_repository.RULESETS_DIR / ruleset_id / filename
    return json.loads(path.read_bytes())


def _ruleset_policies(ruleset_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Return the ruleset's ``(time_policy, star_catalog)`` component data.

    Both filenames are resolved through the manifest's ``components`` map rather
    than hard-coded, so the loader tracks the ruleset's own declaration.
    """
    manifest = _read_ruleset_json(ruleset_id, "manifest.json")
    components: Dict[str, str] = manifest["components"]
    time_policy = _read_ruleset_json(ruleset_id, components["time_policy"])
    star_catalog = _read_ruleset_json(ruleset_id, components["star_catalog"])
    return time_policy, star_catalog


def _lunar_date_dict(lunar: Any) -> Dict[str, Any]:
    """Project a seed ``LunarDate`` onto the schema ``LunarDate`` block."""
    return {
        "year_label": lunar.year_label,
        "month": lunar.month,
        "day": lunar.day,
        "is_leap_month": lunar.is_leap_month,
        "month_length": lunar.month_length,
    }


def _chronometry_dict(chrono: ChronometryResolution) -> Dict[str, Any]:
    """Project the chronometry resolution onto its schema block.

    Only the twelve contract fields are emitted; the two derived carry-over
    fields (``chart_local_date`` / ``day_boundary_offset_hours``) are internal
    to the seed pipeline and are not part of the schema block.
    """
    return {
        "civil_local": chrono.civil_local,
        "utc": chrono.utc,
        "effective_local": chrono.effective_local,
        "effective_standard": chrono.effective_standard,
        "timezone": chrono.timezone,
        "location": {
            "lat": chrono.location.lat,
            "lon": chrono.location.lon,
        },
        "local_time_status": chrono.local_time_status,
        "fold": chrono.fold,
        "warning": chrono.warning,
        "hour_branch_id": chrono.hour_branch_id,
        "late_zi_applied": chrono.late_zi_applied,
        "late_zi_policy_id": chrono.late_zi_policy_id,
    }


def _calendar_dict(calendar: CalendarResolution) -> Dict[str, Any]:
    """Project the calendar resolution onto its schema block."""
    return {
        "calendar_engine_id": calendar.calendar_engine_id,
        "pre_late_zi_lunar_date": _lunar_date_dict(calendar.pre_late_zi_lunar_date),
        "chart_lunar_date": _lunar_date_dict(calendar.chart_lunar_date),
        "effective_month_for_chart": calendar.effective_month_for_chart,
        "leap_month_policy_id": calendar.leap_month_policy_id,
        "year_cycle": {
            "stem_id": calendar.year_cycle.stem_id,
            "branch_id": calendar.year_cycle.branch_id,
            "basis_policy_id": calendar.year_cycle.basis_policy_id,
        },
        "warnings": list(calendar.warnings),
    }


def _bureau_dict(bureau: Bureau) -> Dict[str, Any]:
    """Project the Five-Elements Bureau onto its schema block."""
    return {
        "id": bureau.id,
        "phase_id": bureau.phase_id,
        "number": bureau.number,
        "formula_id": bureau.formula_id,
        "source_status": bureau.source_status,
    }


def _transformation_dict(transformation: Any) -> Dict[str, Any]:
    """Project a :class:`Transformation` onto its schema block."""
    return {
        "type": transformation.type,
        "star_id": transformation.star_id,
        "source_stem_id": transformation.source_stem_id,
        "table_id": transformation.table_id,
        "scope": transformation.scope,
    }


def _relation_dict(relation: Relation) -> Dict[str, Any]:
    """Project a :class:`Relation` onto its schema block (ids as names)."""
    return {
        "focus_palace_role_id": relation.focus_palace_role_id,
        "focus_branch_id": relation.focus_branch_id.name,
        "harmony_branch_ids": [b.name for b in relation.harmony_branch_ids],
        "opposition_branch_id": relation.opposition_branch_id.name,
    }


def _decadal_dict(limit: DecadalLimit) -> Dict[str, Any]:
    """Project a :class:`DecadalLimit` onto its schema block (branch as name)."""
    return {
        "sequence_index_0": limit.sequence_index_0,
        "start_age_inclusive": limit.start_age_inclusive,
        "end_age_inclusive": limit.end_age_inclusive,
        "age_reckoning_id": limit.age_reckoning_id,
        "direction": limit.direction,
        "branch_id": limit.branch_id.name,
        "palace_role_id": limit.palace_role_id,
    }


def _resolve_decadal_direction(
    calculation: Dict[str, Any],
    seed: ResolvedZwdsSeed,
    sex_at_birth: Optional[str],
) -> str:
    """Resolve the decadal walk direction from the request's direction method.

    ``explicit`` uses the request's ``flow_direction``; the traditional method
    uses the year-stem yin/yang polarity plus sex-at-birth. The request schema
    already guarantees ``include_decadal_limits=true`` implies a resolvable
    method, so ``omit`` never reaches here.
    """
    method = calculation["direction_method"]
    if method == "explicit":
        return decadal_direction(flow_direction=calculation["flow_direction"])
    if method == "year_stem_yinyang_and_sex":
        return decadal_direction(
            year_stem_index=seed.year_stem_index,
            sex_at_birth=sex_at_birth,
        )
    raise ValueError(
        "decadal limits requested but direction_method "
        f"{method!r} cannot resolve a direction"
    )


def _build_star_placements(
    star_branches: List[StarBranch],
    palaces: List[Palace],
    y_s: int,
    source_status_by_star: Dict[str, str],
) -> tuple[List[Dict[str, Any]], Dict[int, List[str]]]:
    """Assemble the single canonical ``star_placements[]`` + a branch→ids map.

    ``star_placements`` is the schema source of truth; ``placements_by_branch``
    lets each palace carry only ``placement_id`` references.
    """
    branch_to_role: Dict[int, str] = {
        int(p.branch_id): p.palace_role_id for p in palaces
    }
    tx_by_star: Dict[str, List[str]] = transformation_types_by_star(y_s)
    star_placements: List[Dict[str, Any]] = []
    placements_by_branch: Dict[int, List[str]] = {}
    for star in star_branches:
        placement_id = f"natal:{star.star_id}"
        star_placements.append(
            {
                "placement_id": placement_id,
                "star_id": star.star_id,
                "family_id": star.family_id,
                "scope": "natal",
                "branch_id": BranchId(star.branch_index).name,
                "palace_role_id": branch_to_role[star.branch_index],
                "brightness_code": None,
                "transformation_types": list(tx_by_star.get(star.star_id, [])),
                "formula_id": star.formula_id,
                "source_status": source_status_by_star.get(
                    star.star_id, star.source_status
                ),
            }
        )
        placements_by_branch.setdefault(star.branch_index, []).append(
            placement_id
        )
    return star_placements, placements_by_branch


def _build_completeness(
    output: Dict[str, Any],
    declared_families: List[str],
    star_branches: List[StarBranch],
) -> Dict[str, Any]:
    """Completeness block: declared vs emitted families, in declared order."""
    emitted_set = {star.family_id for star in star_branches}
    return {
        "requested_scope": output["star_scope"],
        "ruleset_declared_families": list(declared_families),
        "emitted_families": [f for f in declared_families if f in emitted_set],
        "missing_families": [
            f for f in declared_families if f not in emitted_set
        ],
    }


def _build_decadal_out(
    output: Dict[str, Any],
    calculation: Dict[str, Any],
    seed: Any,
    sex_at_birth: Optional[str],
    palaces: List[Palace],
    bureau_number: int,
) -> Optional[List[Dict[str, Any]]]:
    """Optional decadal limits — ``None`` when ``include_decadal_limits`` is false.

    The decadal layer consumes palaces structurally (read-only
    ``palace_role_id`` + ``branch_id``); the cast reconciles the frozen
    ``Palace`` with its ``PalaceLike`` protocol (settable-attribute variables to
    mypy).
    """
    if not output["include_decadal_limits"]:
        return None
    direction = _resolve_decadal_direction(calculation, seed, sex_at_birth)
    return [
        _decadal_dict(dl)
        for dl in decadal_limits(
            cast("Sequence[DecadalPalaceLike]", palaces),
            bureau_number,
            direction,
        )
    ]


def _build_derivation_trace(
    output: Dict[str, Any],
    seed: Any,
    ming_b: int,
    ruleset: RulesetRef,
    ming_palace: Palace,
    bureau: Bureau,
) -> Optional[List[Dict[str, Any]]]:
    """Optional derivation trace (≥ Ming + Bureau steps); ``None`` when disabled."""
    if not output["include_trace"]:
        return None
    return [
        {
            "step_id": "ming",
            "formula_id": _MING_FORMULA_ID,
            "inputs": {
                "month": seed.month,
                "hour_ordinal": seed.hour_branch_index + 1,
            },
            "output": BranchId(ming_b).name,
            "ruleset_ref": ruleset.ruleset_id,
            "status": "COMPUTED",
        },
        {
            "step_id": "bureau",
            "formula_id": bureau.formula_id,
            "inputs": {
                "stem_id": ming_palace.stem_id.name,
                "branch_id": ming_palace.branch_id.name,
            },
            "output": bureau.id,
            "ruleset_ref": ruleset.ruleset_id,
            "status": "COMPUTED",
        },
    ]


def compute_zwds_raw(
    request: Dict[str, Any],
    *,
    request_id: str = "req_zwds",
    generated_at: str = "1984-02-01T00:00:00Z",
) -> Dict[str, Any]:
    """Compute the full ``ZwdsRawResponse`` for a civil-birth ``request``.

    Parameters
    ----------
    request
        A ``ZwdsRequest``-shaped dict with ``birth`` / ``calculation`` /
        ``output`` blocks.
    request_id
        Correlation id echoed into the response (the router supplies a real id).
    generated_at
        RFC-3339 UTC timestamp; injectable so tests are deterministic (the
        router passes the real UTC now).

    Returns a plain, JSON-serializable dict that validates against
    ``ZwdsRawResponse.schema.json``.
    """
    birth: Dict[str, Any] = request["birth"]
    calculation: Dict[str, Any] = request["calculation"]
    output: Dict[str, Any] = request["output"]

    # 1. Immutable, hash-locked ruleset envelope.
    ruleset: RulesetRef = load_ruleset(calculation["ruleset_id"])
    time_policy, star_catalog = _ruleset_policies(ruleset.ruleset_id)

    # Authoritative per-star source_status (star module values are provisional).
    source_status_by_star: Dict[str, str] = {
        star["star_id"]: star["source_status"]
        for star in star_catalog["stars"]
    }
    declared_families: List[str] = list(star_catalog["declared_families"])

    # 2. Seed resolution (chronometry + calendar) from civil birth + ruleset
    #    time / late-Zi / leap / year-cycle policies.
    sex_at_birth: Optional[str] = birth.get("sex_at_birth")
    chrono, calendar, seed = resolve_seed(
        datetime_local=birth["datetime_local"],
        timezone=birth["timezone"],
        lat=birth["location"]["lat"],
        lon=birth["location"]["lon"],
        ambiguous_time=birth["ambiguousTime"],
        nonexistent_time=birth["nonexistentTime"],
        time_standard=time_policy["time_standard"],
        late_zi_policy_id=time_policy["late_zi_policy_id"],
        leap_month_policy_id=ruleset.leap_month_policy_id,
        year_cycle_basis_policy_id=ruleset.year_cycle_policy_id,
    )
    y_s: int = seed.year_stem_index

    # 3. Palace layout + Ming/Shen anchors.
    palaces: List[Palace] = build_palaces(
        seed.month, seed.hour_branch_index, y_s
    )
    ming_b: int = ming_branch(seed.month, seed.hour_branch_index)
    shen_b: int = shen_branch(seed.month, seed.hour_branch_index)
    ming_palace: Palace = next(p for p in palaces if p.is_ming_palace)

    # 4. Five-Elements Bureau from the Ming palace stem/branch.
    bureau: Bureau = five_elements_bureau(
        int(ming_palace.stem_id), int(ming_palace.branch_id)
    )
    bureau_number: int = bureau.number

    # 5. Stars: 14 major + 4 guide-auxiliary (example emission order).
    star_branches: List[StarBranch] = major_stars(seed.day, bureau_number) + (
        guide_auxiliary_stars(seed.month, seed.hour_branch_index)
    )

    # 6. Single canonical star_placements[] (schema source of truth).
    star_placements, placements_by_branch = _build_star_placements(
        star_branches, palaces, y_s, source_status_by_star
    )

    # 7. palaces[] carry only placement_id references.
    palaces_out: List[Dict[str, Any]] = [
        {
            "palace_role_id": p.palace_role_id,
            "sequence_index_0": p.sequence_index_0,
            "branch_id": p.branch_id.name,
            "stem_id": p.stem_id.name,
            "is_ming_palace": p.is_ming_palace,
            "is_shen_palace": p.is_shen_palace,
            "placement_ids": list(placements_by_branch.get(int(p.branch_id), [])),
            "grid_position": None,
        }
        for p in palaces
    ]

    # 8. Four transformations for the year stem.
    transformations_out = [
        _transformation_dict(t) for t in four_transformations(y_s)
    ]

    # 9. San-Fang-Si-Zheng relations (one per palace). The relations/decadal
    #    layers consume palaces structurally (read-only palace_role_id +
    #    branch_id); the cast reconciles the frozen ``Palace`` with their
    #    PalaceLike protocols, which mypy reads as settable-attribute variables.
    relations_out = [
        _relation_dict(r)
        for r in relations_for_palaces(
            cast("Sequence[RelationsPalaceLike]", palaces)
        )
    ]

    # 10. Optional decadal limits.
    decadal_out = _build_decadal_out(
        output, calculation, seed, sex_at_birth, palaces, bureau_number
    )

    # 11. Completeness (declared vs emitted families, in declared order).
    completeness = _build_completeness(output, declared_families, star_branches)

    # 12. Assemble the chart, validate the graph, fingerprint it.
    chart: Dict[str, Any] = {
        "coordinate_system": _coordinate_system(),
        "birth_cycle": {
            "year_stem_id": StemId(seed.year_stem_index).name,
            "year_branch_id": BranchId(seed.year_branch_index).name,
            "year_animal_id": seed.year_animal_id.name,
            "hour_branch_id": chrono.hour_branch_id,
        },
        "ming_palace_branch_id": BranchId(ming_b).name,
        "shen_palace_branch_id": BranchId(shen_b).name,
        "five_elements_bureau": _bureau_dict(bureau),
        "palaces": palaces_out,
        "star_placements": star_placements,
        "transformations": transformations_out,
        "relations": relations_out,
        "decadal_limits": decadal_out,
        "completeness": completeness,
    }
    validate_chart_graph(chart)
    fingerprint = chart_fingerprint(chart)

    # Optional derivation trace (>= Ming + Bureau steps, per the schema shape).
    derivation_trace = _build_derivation_trace(
        output, seed, ming_b, ruleset, ming_palace, bureau
    )

    return {
        "request_id": request_id,
        "schema_version": "zwds.raw.v1",
        "engine_version": __zwds_engine_version__,
        "generated_at": generated_at,
        "chart_fingerprint": fingerprint,
        "ruleset": asdict(ruleset),
        "normalized_input": {
            "birth": birth,
            "calculation": calculation,
            "output": output,
        },
        "resolution": {
            "chronometry": _chronometry_dict(chrono),
            "calendar": _calendar_dict(calendar),
        },
        "chart": chart,
        # Catalog materialization is deferred for the core-seed engine
        # (ids-only); emitted only when include_catalog is honored downstream.
        "catalog": None,
        "quality": _quality(),
        "provenance": _provenance(),
        "derivation_trace": derivation_trace,
    }
