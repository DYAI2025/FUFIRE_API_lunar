"""routers/match.py — POST /v1/match/bazi-hehun request/response models.

Level 5 (plan §4.1, docs/plans/2026-07-02-bazi-hehun.md). This module is
the HTTP composition seam for the Level-4 ``bazi_engine.match`` engine.

**T8 (models) + T9 (endpoint + mount).** The Pydantic request/response
contract, the handler and the ``/v1``-only mount (DECISION-001 — no legacy
dual-mount, deliberate deviation like the admin router) all live here.
Downstream API-key consumers only ever call ``/v1/*``.

**T9 composition seam (plan §4.2, AC-003a-d):** the handler builds one
``BaziInput`` per person exactly like ``routers/bazi.py`` (via the SAME
``resolve_local_iso``), calls the pure ``compute_bazi()`` twice (no
duplicated core logic, no cross-request state), shapes each person's
pillars with the SAME imported ``format_pillar``, then feeds the raw
``BaziResult`` pairs into the Level-4 ``bazi_engine.match`` engine
(normalize → individual → pair → textblocks → evidence). The ephemeris
mode is attested in ``quality_flags.ephemeris_mode`` in parity with
single-chart responses (planning note b / audit F8).

Binding schema decisions:
- DECISION-002 (docs/context/bazi-hehun.response-schema-decision.md): the
  ADAPTED user schema — meta / request_context / subjects (redacted
  hashes) / individual layers (with deferral statuses) / EXACTLY three
  pair layers / raw_analysis_text blocks / evidence_ledger /
  relationship_context (consent) / safety_and_language_policy /
  missing_and_blockers are adopted.
- D1 (REQ-007): NO score field of any kind exists anywhere in the request
  OR response contract — not even null. ``total_score`` / ``sub_scores`` /
  ``score_class`` / ``awarded_points`` / ``score_confidence`` are absent.
- D3 (NOGOAL-003/006): no interaction-matrix layers, no western/fusion
  modality stubs — exactly three pair layers, BaZi-only.
- D4 (AC-008b): no ``allowed_for_llm_interpretation`` /
  interpretation-readiness flag; the block schema IS the text contract.
- AC-002a/b/c: ``mode`` is ``Literal["birth_input"]`` only; the request
  and its ``options`` forbid unknown keys (raw/scoring payloads ⇒ 422).
- AC-012b/c/d: ``persist_raw`` defaults False; ``second_person_consent_
  confirmed`` is REQUIRED inside the REQUIRED ``options`` object (every
  ancestor on its path is required — contract §3 WATCH item); its
  description is neutral copy that does not imply legal review.

The person payload type is the reused ``BaziRequest`` component
(plan §4.2, REQ-002/AC-002a): one frozen OpenAPI component,
"BaziRequest-compatible" by construction. Its ``include_trace`` field is
accepted and ignored for match requests.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request

from .. import __version__
from ..bazi import compute_bazi
from ..bazi_rules import load_default_ruleset
from ..exc import BaziEngineError, CalculationError
from ..limiter import limiter, tier_limit
from ..match import (
    MATCH_SCHEMA_VERSION,
    analyze_individual,
    analyze_pair,
    build_evidence_ledger,
    build_text_blocks,
    normalize_chart,
)
from ..match.canonical import canonical_hash, to_jsonable
from ..match.observability import record_match_request
from ..match.privacy import log_consent_decision
from ..match.types import (
    EvidenceKind,
    SourceStatus,
    StatementType,
    StemSource,
    WarningCode,
    WarningEntry,
)
from ..provenance import build_provenance
from ..time_utils import LocalTimeError, resolve_local_iso
from ..types import BaziInput, BaziResult, Fold
from .bazi import BaziPillarsResponse, BaziRequest
from .shared import PrecisionBlock, ProvenanceResponse, format_pillar

_log = logging.getLogger(__name__)

# ── T10: reserved error codes (AC-009b) ──────────────────────────────────────
# ``ruleset_incomplete`` is RESERVED for the future domain-approved
# interaction / Ten-Gods / scoring tables (MISSING-001..003). It is part of the
# published error taxonomy but is NEVER emitted while those tables remain
# deferred in the MVP: deferred-capability requests (``mode=raw_bazi``,
# scoring/matrix options) are rejected with a schema ``validation_error``
# (``extra="forbid"`` / the ``mode`` Literal), not this code. Surfaced as a
# module constant so the error contract can assert its reservation without the
# code ever appearing in a live response body.
RESERVED_ERROR_CODES: Tuple[str, ...] = ("ruleset_incomplete",)

# Neutral consent copy (AC-012d / T-012-06): states the effect of the flag,
# never implies legal review, GDPR certification or platform vetting — the
# final legal wording (OQ-001) gates the public launch, not this contract.
_CONSENT_DESCRIPTION: str = (
    "Confirms the second person has agreed to their birth data being used "
    "for this one-off pairwise analysis. This also covers the OPTIONAL "
    "gender field when supplied for the second person, used only to select "
    "a sourced spouse-star convention (never persisted, never echoed in "
    "any response). Required: the request is rejected when this is false "
    "or absent. No data is persisted by default."
)

# Policy STATEMENT prose (DECISION-002 — the score FIELDS stay absent, D1).
# Deliberately avoids the words score/points and any numeric-rating pattern
# so it survives the blocked-language and score-absence scans unchanged.
_NO_SCORE_POLICY: str = (
    "This endpoint returns deterministic, source-labelled raw analysis "
    "only. The MVP contract defines no compatibility rating of any kind "
    "(decision D1); a versioned rating block may be added additively once "
    "domain-approved source data exists."
)


# ── Request models ───────────────────────────────────────────────────────────
class MatchPersonInput(BaziRequest):
    """``BaziRequest`` + an OPTIONAL, match-local gender declaration.

    Deliberately NOT added to ``BaziRequest`` itself — that model is shared
    with ``/calculate/bazi`` (``routers/bazi.py``) and ``/personalize``
    (``routers/personalize.py``); adding a gender field there would leak an
    unrelated field into two unrelated, already-live endpoints. See
    docs/plans/2026-07-04-bazi-hehun-gender-field.md (GF-1).

    Optional and defaulted to ``None``: omitting it is fully backward-
    compatible with every existing caller. Used ONLY to select which Ten-God
    the sourced ``spouse_star_convention`` designates for this person
    (Tabelle 10: male → Direct Wealth, female → Direct Officer). ``divers``
    (the German civil-status third-gender category) is accepted but has NO
    sourced convention — MISSING-008.
    """

    gender: Optional[Literal["male", "female", "divers"]] = Field(
        None,
        description=(
            "Optional self-declared gender, used ONLY to select which Ten-God "
            "the sourced spouse-star convention designates for this person "
            "(male → Direct Wealth, female → Direct Officer). 'divers' "
            "is accepted (German civil-status third-gender category) but has "
            "NO sourced convention — supplying it does not compute a "
            "spouse star; the response reports that explicitly rather than "
            "falling back to the male/female rule."
        ),
    )


class MatchOptions(BaseModel):
    """Per-request options. Unknown keys (scoring/matrix) are rejected.

    ``extra="forbid"`` turns any deferred-capability option (e.g.
    ``include_scores``) into a 422 rather than a silently-ignored key
    (AC-009b). ``second_person_consent_confirmed`` is REQUIRED — the
    server-side consent gate that closes the direct-API bypass (D5/AC-012c).
    """

    model_config = ConfigDict(extra="forbid")

    second_person_consent_confirmed: bool = Field(
        ..., description=_CONSENT_DESCRIPTION
    )
    persist_raw: bool = Field(
        False,
        description=(
            "When false (default) no raw birth data is persisted anywhere. "
            "Accepted and echoed as an option; no persistence path exists "
            "in the MVP."
        ),
    )


class MatchRequest(BaseModel):
    """POST /v1/match/bazi-hehun request — birth_input only (D2).

    ``extra="forbid"`` rejects raw-chart / deferred-mode payloads at the
    top level (AC-002b). ``mode`` is ``Literal["birth_input"]`` so
    ``raw_bazi`` / any other value is a 422 (AC-002b/c, resolves OQ-002).
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "mode": "birth_input",
                "person_a": {
                    "date": "1990-06-15T14:30:00",
                    "tz": "Europe/Berlin",
                    "lon": 13.405,
                    "lat": 52.52,
                },
                "person_b": {
                    "date": "1988-03-21T09:05:00",
                    "tz": "Europe/Berlin",
                    "lon": 13.405,
                    "lat": 52.52,
                },
                "options": {"second_person_consent_confirmed": True},
            }
        },
    )

    mode: Literal["birth_input"] = Field(
        ...,
        description=(
            "Input mode. MVP accepts birth_input only; raw_bazi / canonical "
            "chart input is deferred post-MVP (D2)."
        ),
    )
    person_a: MatchPersonInput = Field(
        ..., description="First person's birth input (reused BaziRequest + optional gender)."
    )
    person_b: MatchPersonInput = Field(
        ..., description="Second person's birth input (reused BaziRequest + optional gender)."
    )
    options: MatchOptions = Field(
        ..., description="Request options, including the required consent flag."
    )


# ── Response — quality / provenance attestation (plan §4.3) ──────────────────
class MatchQualityFlags(BaseModel):
    """BaZi-only quality attestation — ephemeris mode only.

    Field name + value domain are identical to the single-chart quality
    flags so downstream consumers see the same ephemeris attestation
    (planning note b / audit F8). The shared ``QualityFlags`` carries
    western-only ``house_system_*`` fields that would be dishonest noise
    on a BaZi endpoint, so this is a dedicated minimal model.
    """

    model_config = ConfigDict(extra="forbid")

    ephemeris_mode: Literal["SWIEPH", "MOSEPH"]


# ── Response — meta / request context ────────────────────────────────────────
class MatchResponseMeta(BaseModel):
    """Response envelope metadata (DECISION-002 meta block).

    ``no_score_policy`` is a policy STATEMENT (prose is allowed); the score
    FIELDS themselves are absent everywhere (D1).
    """

    schema_name: str = Field("BaziHehunRawResponse")
    schema_version: str
    endpoint: str
    response_kind: Literal["raw_analysis_data"] = "raw_analysis_data"
    generated_at_utc: str
    request_id: str
    correlation_id: Optional[str] = None
    ruleset_id: str
    ruleset_version: str
    engine_version: str
    no_score_policy: str = Field(_NO_SCORE_POLICY)


class MatchRequestContext(BaseModel):
    """Echo of how the request was interpreted (DECISION-002 request_context).

    Redacted-by-default: birth data is never echoed here, only policy and
    mode status.
    """

    mode: Literal["birth_input"] = "birth_input"
    input_mode_status: str = "ACCEPTED"
    birth_input_policy: str = Field(
        "Two birth_input person payloads (date/tz/lon/lat) are required."
    )
    raw_bazi_policy: str = Field(
        "raw_bazi / canonical chart input is deferred post-MVP (D2) and is "
        "not accepted by this contract."
    )
    privacy_echo_policy: str = Field(
        "Raw birth data is never echoed; subjects carry redacted hashes only."
    )
    language: str = "en"


# ── Response — subjects (identity + redacted hashes) ─────────────────────────
class RedactedInputRef(BaseModel):
    """Hash-only references to the birth input — raw data is never echoed."""

    input_hash: str
    canonical_birth_context_hash: str


class SubjectBirthContext(BaseModel):
    """Status + precision of a subject's birth input (no raw values)."""

    birth_time_known: bool
    time_precision: str
    location_precision: str
    status: str = "REDACTED"
    redacted_input_ref: RedactedInputRef


class SubjectIdentity(BaseModel):
    """One subject: pseudonymous identity + redacted birth context."""

    subject_id: str
    role: Literal["person_a", "person_b"]
    display_label: str
    identity_policy: str = Field(
        "Pseudonymous; no real name is required or stored."
    )
    birth_context: SubjectBirthContext


class MatchSubjects(BaseModel):
    person_a: SubjectIdentity
    person_b: SubjectIdentity


# ── Response — per-person individual analysis (REQ-004/005) ──────────────────
class WuxingLedgerEntryModel(BaseModel):
    """One Wu-Xing contribution with source marker + weight (AC-004b)."""

    pillar: str
    stem: str
    element: str
    source: StemSource
    weight: float


class MonthCommandModel(BaseModel):
    branch: str
    branch_index: int
    principal_qi_stem: str
    element: str
    source_status: SourceStatus


class SpousePalaceModel(BaseModel):
    """Spouse-palace identification facts only (AC-005c / audit F7).

    CHANGE (b): the day-branch POSITION identification (日支=夫妻宫) is a
    standard, deterministic BaZi fact, so ``position_source_status`` is
    ``CALCULATED`` with a ``position_source_note``; only the palace
    INTERPRETATION/designation stays deferred (``source_status`` =
    ``NEEDS_DOMAIN_REVIEW``). The two are never collapsed into one status.
    """

    palace_pillar: str
    day_branch: str
    day_branch_index: int
    hidden_stems: List[str]
    position_source_status: SourceStatus
    position_source_note: str
    source_status: SourceStatus


class SpouseStarOccurrenceModel(BaseModel):
    """One located stem match (GF-3/GF-4) — never a count/score (D1)."""

    pillar: str
    source: StemSource
    stem: str
    role: Literal["primary_convention_god", "disruption_signal_god"]


class SpouseStarModel(BaseModel):
    """Per-person spouse-star result (GF-3). Split out of ``derived_fields``
    because it is sometimes computable (gender male/female + the sourced
    Ten-Gods table) — see ``match.individual.SpouseStarResult``."""

    gender_used: Optional[Literal["male", "female", "divers"]]
    source_status: SourceStatus
    confidence: float
    blocked_by: str
    occurrences: List[SpouseStarOccurrenceModel]


class DerivedFieldModel(BaseModel):
    """DMS / Yong-Shen deferral status (AC-005b/c).

    Carries a ``source_status`` and a ``confidence`` marker and NO value —
    a fabricated derived value is unrepresentable while MISSING-003 is
    open. ``spouse_star`` moved to its own ``SpouseStarModel`` (GF-3) since
    it is sometimes computable.
    """

    field: str
    source_status: SourceStatus
    confidence: float
    blocked_by: str


class WarningModel(BaseModel):
    """A surfaced warning: stable code + subject (AC-004c)."""

    code: WarningCode
    subject: str
    message: str
    evidence_ids: List[str] = Field(default_factory=list)


class IndividualAnalysisModel(BaseModel):
    """Per-person analysis mounted under ``individual.person_a/b`` (AC-005a).

    Combines the normalized chart facts (four pillars, day master, Wu-Xing
    vector + ledger) with the individual layers (month command, spouse
    palace, derived-field deferral statuses) and warnings.
    """

    subject: str
    four_pillars: BaziPillarsResponse
    day_master: str
    day_master_element: str
    month_command: MonthCommandModel
    spouse_palace: SpousePalaceModel
    wuxing_vector: List[float]
    wuxing_ledger: List[WuxingLedgerEntryModel]
    derived_fields: List[DerivedFieldModel]
    spouse_star: SpouseStarModel
    source_status: SourceStatus
    warnings: List[WarningModel] = Field(default_factory=list)


class MatchIndividual(BaseModel):
    person_a: IndividualAnalysisModel
    person_b: IndividualAnalysisModel


# ── Response — pair layers (EXACTLY three, D3 / AC-006a) ─────────────────────
class FactModel(BaseModel):
    """One keyed, source-labelled fact inside a pair layer (AC-006d).

    ``value`` is heterogeneous (stem/branch labels, booleans, vectors); no
    fact is ever named or presented as a point/score (D1).
    """

    key: str
    value: Any = None
    source_status: SourceStatus = SourceStatus.CALCULATED


class PairLayerModel(BaseModel):
    """One MVP pair layer — facts / rule applications / source status only."""

    name: Literal[
        "day_master_comparison",
        "spouse_palace_day_branch",
        "wuxing_vector_comparison",
    ]
    facts: List[FactModel]
    source_status: SourceStatus
    evidence_ids: List[str]


class MatchPairLayers(BaseModel):
    """The pair section — EXACTLY the three MVP layers (D3 / AC-006a).

    The field set IS the layer set: a fourth layer or matrix stub cannot be
    emitted without changing this model (AC-006b/c).
    """

    day_master_comparison: PairLayerModel
    spouse_palace_day_branch: PairLayerModel
    wuxing_vector_comparison: PairLayerModel


# ── Response — text blocks / evidence / warnings ─────────────────────────────
class TextBlockModel(BaseModel):
    """AC-008a — exactly these seven fields; this schema IS the text contract.

    Blocks carry ``source_status``/``evidence_ids`` only; the contract makes
    no downstream-model readiness claim of any kind (D4). Any downstream
    consumption of these blocks requires its own separately-gated spec.
    """

    id: str
    layer: str
    statement_type: StatementType
    subject: str
    text: str
    source_status: SourceStatus
    evidence_ids: List[str]


class EvidenceEntryModel(BaseModel):
    """AC-013a — one ledger entry per emitted block and per warning."""

    id: str
    kind: EvidenceKind
    source_ref: str
    description: str


# ── Response — consent / safety / blockers ───────────────────────────────────
class ConsentStatus(BaseModel):
    """Consent acknowledgement + the OQ-001 launch-gate status (DECISION-002).

    ``go_live_blocker`` stays true until the final legal wording (OQ-001)
    resolves; it gates the public-launch flag flip, not this build.
    """

    acknowledgement: bool
    consent_text_version: str
    final_legal_text_status: str
    go_live_blocker: bool = True


class RelationshipContext(BaseModel):
    consent_status: ConsentStatus


class SafetyAndLanguagePolicy(BaseModel):
    """AC-008c safeguards — allowed/blocked output + human-review gate."""

    allowed_output: List[str]
    blocked_output: List[str]
    requires_human_review_before_go_live: bool = True


class MissingBlocker(BaseModel):
    """One open ledger item surfaced to the caller (DECISION-002)."""

    id: str
    title: str
    status: str


class MatchPrecision(BaseModel):
    """Per-person precision block (reuses the single-chart PrecisionBlock)."""

    person_a: PrecisionBlock
    person_b: PrecisionBlock


# ── Response root ────────────────────────────────────────────────────────────
class MatchResponse(BaseModel):
    """POST /v1/match/bazi-hehun response — the ADAPTED DECISION-002 schema.

    Contains NO score field of any kind (D1), no interaction-matrix or
    western/fusion modality stubs (D3), and no downstream-model readiness
    flag (D4). ``quality_flags.ephemeris_mode`` attests the ephemeris
    backend in parity with single-chart responses (planning note b).
    """

    meta: MatchResponseMeta
    request_context: MatchRequestContext
    subjects: MatchSubjects
    individual: MatchIndividual
    pair: MatchPairLayers
    raw_analysis_text: List[TextBlockModel]
    warnings: List[WarningModel] = Field(default_factory=list)
    evidence_ledger: List[EvidenceEntryModel]
    relationship_context: RelationshipContext
    provenance: ProvenanceResponse
    quality_flags: MatchQualityFlags
    precision: MatchPrecision
    safety_and_language_policy: SafetyAndLanguagePolicy
    missing_and_blockers: List[MissingBlocker] = Field(default_factory=list)


# ── T9: endpoint + /v1-only mount ────────────────────────────────────────────
# DECISION-001: this router is mounted in ``app.py`` at ``/v1`` ONLY (no
# legacy dual-mount) — a deliberate deviation from the repo dual-mount idiom,
# like the admin router. ``tags=["Hehun"]`` is the exact literal the frontend
# ``TAG_TO_CATEGORY`` maps to category ``Hehun`` (T-001-05 / AC-001d).
router = APIRouter(prefix="/match", tags=["Hehun"])

# The public-facing endpoint path (echoed in ``meta.endpoint``). The ``/v1``
# prefix is applied at mount time in ``app.py`` (DECISION-001).
_ENDPOINT_PATH: str = "/v1/match/bazi-hehun"

# Neutral consent-text version tag (the final legal wording is OQ-001,
# gating the launch flip, not this contract — AC-012d).
_CONSENT_TEXT_VERSION: str = "neutral-v0"

# Safety/language policy surfaced to callers (AC-008c). Deliberately worded
# so no label collides with the blocked-language lexicon or a score/points
# token (§0.4) — the same body is scanned recursively by T-007-03.
_ALLOWED_OUTPUT: Tuple[str, ...] = (
    "calculated_facts",
    "rule_applications",
    "source_status_markers",
    "warnings",
)
_BLOCKED_OUTPUT: Tuple[str, ...] = (
    "numeric_compatibility_ratings",
    "relationship_outcome_predictions",
    "deterministic_fate_claims",
)

# Open ledger items surfaced honestly to the caller (DECISION-002). Titles
# avoid every forbidden token so the response survives the recursive scans.
# MISSING-002 (Ten-Gods mapping table) is RESOLVED as of 2026-07-04 --
# match.ten_gods implements + tests the sourced table -- so it no longer
# belongs in this OPEN-items list. The field it was blocking (spouse_star)
# has a NEW, distinct open blocker: MISSING-007 (no gender field in the
# request schema to pick the convention-designated spouse star).
_MISSING_AND_BLOCKERS: Tuple[Dict[str, str], ...] = (
    {"id": "MISSING-001", "title": "Branch/stem interaction table pending domain review", "status": "OPEN"},
    {"id": "MISSING-003", "title": "Day-master strength and useful-god thresholds pending domain review", "status": "OPEN"},
    {"id": "MISSING-006", "title": "Wei hidden-stem weighting ordering under domain review", "status": "OPEN"},
    {"id": "MISSING-007", "title": "Gender designation pending request-schema decision", "status": "OPEN"},
    {"id": "OQ-001", "title": "Consent legal wording pending review", "status": "OPEN"},
)


def _effective_ephemeris_mode() -> str:
    """Attest the active ephemeris backend (planning note b / audit F8).

    Resolves via ``EPHEMERIS_MODE`` exactly like ``transit.py`` and
    ``SwissEphBackend.__post_init__`` — so this value is in parity with the
    single-chart responses' ``quality_flags.ephemeris_mode`` in the same
    process (a MOSEPH-computed match never masquerades as SWIEPH).
    """
    return os.environ.get("EPHEMERIS_MODE", "SWIEPH").upper()


def _compute_person_chart(person: BaziRequest) -> BaziResult:
    """Build the ``BaziInput`` and compute one person's chart (AC-003b/c).

    Mirrors ``routers/bazi.py`` (``resolve_local_iso`` → ``BaziInput`` →
    ``compute_bazi``) using the SAME imported engine functions — reuse of
    the core computation, not a copy of it. Pure per call: no shared or
    cross-request state (AC-003d).
    """
    dt_local, _ = resolve_local_iso(
        person.date,
        person.tz,
        ambiguous=person.ambiguousTime,
        nonexistent=person.nonexistentTime,
    )
    resolved_naive = dt_local.replace(tzinfo=None).isoformat()
    fold: Fold = 0 if person.ambiguousTime == "earlier" else 1
    inp = BaziInput(
        birth_local=resolved_naive,
        timezone=person.tz,
        longitude_deg=person.lon,
        latitude_deg=person.lat,
        time_standard=person.standard,
        day_boundary=person.boundary,
        strict_local_time=True,
        fold=fold,
    )
    return compute_bazi(inp)


def _four_pillars_block(result: BaziResult) -> Dict[str, Any]:
    """Shape the four pillars via the SHARED ``format_pillar`` (AC-003c).

    The same helper single-chart ``/v1/calculate/bazi`` uses, so the
    per-person pillars block deep-equals the single-chart response for the
    same input (proven by tests/test_match_service_boundary.py).
    """
    return {
        "year": format_pillar(result.pillars.year),
        "month": format_pillar(result.pillars.month),
        "day": format_pillar(result.pillars.day),
        "hour": format_pillar(result.pillars.hour),
    }


def _precision_block(birth_time_known: bool) -> Dict[str, Any]:
    """Per-person precision block (same convention as ``routers/bazi.py``)."""
    return {
        "birth_time_known": birth_time_known,
        "provisional_fields": [] if birth_time_known else ["hour"],
    }


def _subject_identity(role: str, display_label: str, person: BaziRequest) -> Dict[str, Any]:
    """Pseudonymous subject block — redacted hashes only, no raw birth data.

    Privacy-by-default (REQ-012): the raw ``date/tz/lon/lat`` are NEVER
    echoed; the subject carries a stable, one-way ``sha256`` reference so a
    caller can correlate without the payload being reflected back.
    """
    input_hash = canonical_hash(person.model_dump())
    context_hash = canonical_hash(
        {
            "date": person.date,
            "tz": person.tz,
            "lon": person.lon,
            "lat": person.lat,
            "standard": person.standard,
            "boundary": person.boundary,
        }
    )
    return {
        "subject_id": f"sub_{input_hash[:16]}",
        "role": role,
        "display_label": display_label,
        "birth_context": {
            "birth_time_known": person.birth_time_known,
            "time_precision": "minute" if person.birth_time_known else "unknown",
            "location_precision": "coordinate",
            "redacted_input_ref": {
                "input_hash": input_hash,
                "canonical_birth_context_hash": context_hash,
            },
        },
    }


def _individual_block(analysis: Any, chart: Any, result: BaziResult) -> Dict[str, Any]:
    """Project one person's individual analysis into the response shape.

    The frozen engine dataclass carries the day master, month command,
    spouse-palace facts, Wu-Xing vector, derived-field statuses and
    warnings; the pillars block and the Wu-Xing ledger (from the T2
    normalized chart) are attached here at the HTTP seam.
    """
    block: Dict[str, Any] = to_jsonable(analysis)
    block["four_pillars"] = _four_pillars_block(result)
    block["wuxing_ledger"] = to_jsonable(chart.wuxing_ledger)
    return block


def _dedupe_warnings(
    warnings: Tuple[WarningEntry, ...],
) -> Tuple[WarningEntry, ...]:
    """Collapse warnings by ``(code, subject)`` — same key the T5 blocks and
    T6 ledger de-duplicate on, so the top-level ``warnings`` array, the
    warning text blocks and their evidence entries stay 1:1 consistent."""
    seen: set = set()
    unique: List[WarningEntry] = []
    for warning in warnings:
        key = (warning.code, warning.subject)
        if key in seen:
            continue
        seen.add(key)
        unique.append(warning)
    return tuple(unique)


@router.post("/bazi-hehun", response_model=MatchResponse)
@limiter.limit(tier_limit)
def match_bazi_hehun_endpoint(request: Request, req: MatchRequest) -> Dict[str, Any]:
    """Deterministic BaZi-Hehun pair analysis — raw, source-labelled facts.

    Computes both charts with the shared engine (``compute_bazi`` ×2),
    normalizes each, and returns the three MVP pair layers
    (``day_master_comparison``, ``spouse_palace_day_branch``,
    ``wuxing_vector_comparison``) plus per-person individual analysis,
    source-linked raw text blocks, an evidence ledger and honest
    source-status markers. **No compatibility score of any kind is computed
    or returned (D1).** The ephemeris backend is attested in
    ``quality_flags.ephemeris_mode``. Birth data is never echoed or
    persisted; subjects carry redacted hashes only.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # ── Consent audit hash-log (AC-012a / AC-012f / D5 / T-012-04) ───────────
    # PII-free hash-log of the consent DECISION (whatever its value) tied to
    # the request_id, emitted BEFORE the gate so a rejected ``false`` is
    # audited too. ``log_consent_decision`` is a Level-4 helper that never
    # receives a birth field — the consent side-effect log cannot leak PII.
    log_consent_decision(request_id, req.options.second_person_consent_confirmed)

    # ── Server-side consent gate (AC-012c / D5 / T-012-02) ───────────────────
    # The consent boolean is REQUIRED (absent ⇒ 422 via the request model), but
    # a present ``false`` value must ALSO be rejected — otherwise this endpoint
    # would compute and return a non-consenting second person's chart. This
    # guard is placed BEFORE the try/except below on purpose: the bare
    # ``except Exception`` there would otherwise convert this HTTPException into
    # a misleading 500. Raises a stable, consent-specific ErrorEnvelope code.
    if not req.options.second_person_consent_confirmed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "consent_required",
                "message": (
                    "Second-person consent is required for this pairwise "
                    "analysis and must be confirmed (true)."
                ),
                "detail": {
                    "code": "consent_required",
                    "field": "options.second_person_consent_confirmed",
                },
            },
        )

    try:
        # ── T12: latency window (AC-015b) ────────────────────────────────────
        # Time ONLY the match computation (both charts → pair → blocks →
        # ledger) so ``match.request_ms`` is distinct from the middleware's
        # total request time (X-Response-Time-ms).
        _t0 = time.perf_counter()

        ruleset = load_default_ruleset()

        result_a = _compute_person_chart(req.person_a)
        result_b = _compute_person_chart(req.person_b)

        chart_a = normalize_chart(
            result_a,
            birth_time_known=req.person_a.birth_time_known,
            subject="person_a",
            ruleset=ruleset,
        )
        chart_b = normalize_chart(
            result_b,
            birth_time_known=req.person_b.birth_time_known,
            subject="person_b",
            ruleset=ruleset,
        )

        individual_a = analyze_individual(
            chart_a, subject="person_a", ruleset=ruleset, gender=req.person_a.gender
        )
        individual_b = analyze_individual(
            chart_b, subject="person_b", ruleset=ruleset, gender=req.person_b.gender
        )

        pair = analyze_pair(individual_a, individual_b)

        warnings = _dedupe_warnings(chart_a.warnings + chart_b.warnings)
        text_blocks = build_text_blocks(pair, warnings=warnings)
        evidence_ledger = build_evidence_ledger(pair, warnings)

        # ── T12: EV-007 demand-attribution + latency record (AC-013b/c/d) ────
        # One PII-free observability line: request_id, match.request_ms,
        # caller team/external class (from request.state.key_info against the
        # allowlist), key-TIER only (never the key), ruleset id/version and
        # warning CLASSES. No birth field is passed in.
        ruleset_id = ruleset.get("ruleset_id", "MISSING")
        ruleset_version = ruleset.get("ruleset_version", "MISSING")
        record_match_request(
            request_id=request_id,
            key_info=getattr(request.state, "key_info", None),
            duration_ms=(time.perf_counter() - _t0) * 1000.0,
            endpoint=_ENDPOINT_PATH,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
            warning_codes=[warning.code.value for warning in warnings],
        )

        return {
            "meta": {
                "schema_version": MATCH_SCHEMA_VERSION,
                "endpoint": _ENDPOINT_PATH,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "ruleset_id": ruleset_id,
                "ruleset_version": ruleset_version,
                "engine_version": __version__,
            },
            "request_context": {},
            "subjects": {
                "person_a": _subject_identity("person_a", "Person A", req.person_a),
                "person_b": _subject_identity("person_b", "Person B", req.person_b),
            },
            "individual": {
                "person_a": _individual_block(individual_a, chart_a, result_a),
                "person_b": _individual_block(individual_b, chart_b, result_b),
            },
            "pair": to_jsonable(pair),
            "raw_analysis_text": [to_jsonable(block) for block in text_blocks],
            "warnings": [to_jsonable(warning) for warning in warnings],
            "evidence_ledger": [to_jsonable(entry) for entry in evidence_ledger],
            "relationship_context": {
                "consent_status": {
                    "acknowledgement": req.options.second_person_consent_confirmed,
                    "consent_text_version": _CONSENT_TEXT_VERSION,
                    "final_legal_text_status": "PENDING_LEGAL_REVIEW",
                    "go_live_blocker": True,
                }
            },
            "provenance": build_provenance(),
            "quality_flags": {"ephemeris_mode": _effective_ephemeris_mode()},
            "precision": {
                "person_a": _precision_block(req.person_a.birth_time_known),
                "person_b": _precision_block(req.person_b.birth_time_known),
            },
            "safety_and_language_policy": {
                "allowed_output": list(_ALLOWED_OUTPUT),
                "blocked_output": list(_BLOCKED_OUTPUT),
                "requires_human_review_before_go_live": True,
            },
            "missing_and_blockers": [dict(item) for item in _MISSING_AND_BLOCKERS],
        }
    except LocalTimeError:
        # DST/ambiguous local-time errors flow through the shared time_utils
        # message, which historically interpolated the raw birth instant + tz
        # (PII) into the client-facing 422 body. match owns its own error
        # contract (T10 / AC-009d, AC-012a) and must be PII-safe independent of
        # the shared module: re-raise a scrubbed, PII-free LocalTimeError so a
        # non-consenting second person's exact birth instant + timezone is never
        # reflected back. (The shared-module leak is fixed product-wide in a
        # separate security commit — CONTRA-T9-SCOPE-001.)
        raise LocalTimeError(
            "Invalid local time (nonexistent or ambiguous due to a DST "
            "transition). Provide a valid time or set the DST handling option."
        ) from None
    except BaziEngineError:
        # Domain/time/ephemeris errors carry their own HTTP mapping via the
        # app-level handlers: EphemerisUnavailableError → 503, InputError → 422,
        # CalculationError → 500 (AC-009c). Re-raise unchanged; the handlers
        # emit a stable ErrorEnvelope and never echo raw birth data.
        raise
    except Exception as exc:  # noqa: BLE001 — never leak internals to the caller.
        # Any other unexpected failure after the consent gate is an internal
        # fault. Log the full traceback for operators, but re-raise as a mapped
        # domain error so the caller gets a generic, PII-free ErrorEnvelope
        # (500, stable ``calculation_error`` code — AC-009c) with the raw
        # exception message stripped. ``from exc`` preserves the cause in the
        # server log only, never in the response body (AC-009d).
        _log.exception("match computation failed")
        raise CalculationError("Internal calculation error") from exc
