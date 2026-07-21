"""ZWDS-P1-18 — star-graph consistency validation.

Pure structural invariant checks over the schema ``chart`` object. Any
violation raises
:class:`~bazi_engine.zwds.errors.ZwdsGraphInvariantFailedError` with a message
that names the specific invariant that failed. Messages carry only
chart-structure identifiers (palace roles, branch ids, placement ids, family
ids) — never birth PII — so they are safe to surface.

Level: stdlib-only plus ``bazi_engine.zwds.errors``. Imports no other sibling.
"""

from __future__ import annotations

from typing import Any, NoReturn

from bazi_engine.zwds.errors import ZwdsGraphInvariantFailedError


def _fail(invariant: str, message: str, detail: dict[str, Any]) -> NoReturn:
    """Raise the graph-invariant error, naming the ``invariant`` that failed."""
    raise ZwdsGraphInvariantFailedError(
        f"ZWDS chart-graph invariant '{invariant}' violated: {message}",
        detail={"invariant": invariant, **detail},
    )


def _check_duplicate_placements(placements: list) -> None:
    """Invariant 2: each ``placement_id`` appears exactly once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for placement in placements:
        pid = placement["placement_id"]
        if pid in seen:
            duplicates.add(pid)
        seen.add(pid)
    if duplicates:
        _fail(
            "duplicate_placement",
            f"placement_id(s) appear more than once in star_placements: "
            f"{sorted(duplicates)}",
            {"duplicate_placement_ids": sorted(duplicates)},
        )


def _check_palace_references(
    palaces: list, placement_by_id: dict[str, Any]
) -> dict[str, str]:
    """Invariant 1: palace ↔ placement reference integrity.

    Returns ``owner_of`` (placement_id → the single palace role that claims it).
    """
    owner_of: dict[str, str] = {}
    for palace in palaces:
        role = palace["palace_role_id"]
        for pid in palace["placement_ids"]:
            if pid not in placement_by_id:
                _fail(
                    "palace_placement_reference",
                    f"palace {role!r} references placement_id {pid!r} that is "
                    f"absent from star_placements",
                    {"palace_role_id": role, "placement_id": pid},
                )
            if pid in owner_of:
                _fail(
                    "palace_placement_reference",
                    f"placement_id {pid!r} is referenced by more than one "
                    f"palace ({owner_of[pid]!r} and {role!r})",
                    {"placement_id": pid, "palace_role_ids": [owner_of[pid], role]},
                )
            owner_of[pid] = role
    return owner_of


def _check_placement_agreement(
    owner_of: dict[str, str],
    placement_by_id: dict[str, Any],
    palace_by_role: dict[str, Any],
) -> None:
    """Invariant 3: placement fields agree with the referencing palace."""
    for pid, role in owner_of.items():
        placement = placement_by_id[pid]
        palace = palace_by_role[role]
        if placement["palace_role_id"] != palace["palace_role_id"]:
            _fail(
                "placement_palace_disagreement",
                f"placement {pid!r} declares palace_role_id "
                f"{placement['palace_role_id']!r} but is referenced by palace "
                f"{palace['palace_role_id']!r}",
                {
                    "placement_id": pid,
                    "placement_palace_role_id": placement["palace_role_id"],
                    "referencing_palace_role_id": palace["palace_role_id"],
                },
            )
        if placement["branch_id"] != palace["branch_id"]:
            _fail(
                "placement_palace_disagreement",
                f"placement {pid!r} is on branch {placement['branch_id']!r} but "
                f"its palace {role!r} is on branch {palace['branch_id']!r}",
                {
                    "placement_id": pid,
                    "placement_branch_id": placement["branch_id"],
                    "palace_branch_id": palace["branch_id"],
                },
            )


def _check_palace_set(palaces: list) -> None:
    """Invariant 4: the twelve palaces form a well-formed cover."""
    sequence_indices = [palace["sequence_index_0"] for palace in palaces]
    if sorted(sequence_indices) != list(range(12)):
        _fail(
            "palace_set",
            f"sequence_index_0 values are not a permutation of 0..11: "
            f"{sequence_indices}",
            {"sequence_index_0": sequence_indices},
        )
    branch_ids = [palace["branch_id"] for palace in palaces]
    if len(set(branch_ids)) != len(branch_ids):
        _fail(
            "palace_set",
            f"palace branch_id values are not all distinct: {branch_ids}",
            {"branch_ids": branch_ids},
        )


def _check_completeness(chart: dict, placements: list) -> None:
    """Invariant 5: completeness families are internally consistent."""
    completeness = chart["completeness"]
    declared_families = set(completeness["ruleset_declared_families"])
    stated_emitted = set(completeness["emitted_families"])
    stated_missing = set(completeness["missing_families"])
    actual_emitted = {placement["family_id"] for placement in placements}
    if stated_emitted != actual_emitted:
        _fail(
            "completeness_families",
            f"completeness.emitted_families {sorted(stated_emitted)} does not "
            f"equal the distinct family_id set actually present "
            f"{sorted(actual_emitted)}",
            {
                "stated_emitted_families": sorted(stated_emitted),
                "actual_emitted_families": sorted(actual_emitted),
            },
        )
    expected_missing = declared_families - actual_emitted
    if stated_missing != expected_missing:
        _fail(
            "completeness_families",
            f"completeness.missing_families {sorted(stated_missing)} does not "
            f"equal declared − emitted {sorted(expected_missing)}",
            {
                "stated_missing_families": sorted(stated_missing),
                "expected_missing_families": sorted(expected_missing),
            },
        )


def validate_chart_graph(chart: dict) -> None:
    """Validate the star/palace graph of a schema ``chart`` object.

    Raises :class:`ZwdsGraphInvariantFailedError` on the first violated
    invariant (checked in this order):

    1. ``duplicate_placement`` — a ``placement_id`` appears more than once in
       ``star_placements`` (each star is placed exactly once).
    2. ``palace_placement_reference`` — a palace references a ``placement_id``
       absent from ``star_placements``, or the same placement is claimed by
       more than one palace (each star lives in exactly one palace).
    3. ``placement_palace_disagreement`` — a placement's ``palace_role_id`` /
       ``branch_id`` disagree with the palace that references it.
    4. ``palace_set`` — the twelve ``sequence_index_0`` are not a permutation
       of 0..11, or the twelve ``branch_id`` are not all distinct.
    5. ``completeness_families`` — ``emitted_families`` disagrees with the
       distinct ``family_id`` set actually present in ``star_placements``, or
       ``missing_families`` disagrees with ``declared − emitted``.

    Returns ``None`` when every invariant holds.
    """
    palaces = chart["palaces"]
    placements = chart["star_placements"]

    _check_duplicate_placements(placements)
    placement_by_id = {p["placement_id"]: p for p in placements}
    owner_of = _check_palace_references(palaces, placement_by_id)
    palace_by_role = {palace["palace_role_id"]: palace for palace in palaces}
    _check_placement_agreement(owner_of, placement_by_id, palace_by_role)
    _check_palace_set(palaces)
    _check_completeness(chart, placements)
