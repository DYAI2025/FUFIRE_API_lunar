"""ZWDS-P0-04 — typed failure-code contract (imports only ``bazi_engine.exc``).

One exception class per ZWDS failure code, each carrying a frozen,
machine-readable ``error_code`` string. Every class ultimately subclasses
:class:`~bazi_engine.exc.BaziEngineError`, so the global handler in
``error_handlers.py`` renders each one straight into the standard
``ErrorEnvelope`` with zero handler changes.

Base choice encodes the HTTP-status contract:

* **Caller-input failures** subclass :class:`~bazi_engine.exc.InputError`
  (HTTP 422) — the caller can fix them by sending different input.
* **Internal integrity / computation failures** subclass
  :class:`~bazi_engine.exc.CalculationError` (HTTP 500) — bugs or corrupt data
  that should never reach a well-formed caller.
* A **ruleset that exists but is gated out of release** subclasses the engine
  base :class:`~bazi_engine.exc.BaziEngineError` (HTTP 500) — a server-side
  governance state, neither a caller error nor a computation failure.

This is a low-level module: it imports ONLY from ``bazi_engine.exc`` and never
imports zwds siblings or any Level-3+ module. The ``detail`` dict capability of
the base ``__init__`` is preserved (no overrides here).
"""

from __future__ import annotations

from bazi_engine.exc import BaziEngineError, CalculationError, InputError

# --- Caller-input failures (HTTP 422 via InputError) -------------------------


class ZwdsBirthTimeRequiredError(InputError):
    """A birth time is required for this ZWDS calculation but was not supplied."""

    error_code = "zwds_birth_time_required"


class ZwdsRulesetNotFoundError(InputError):
    """The requested ZWDS ruleset id/version does not exist."""

    error_code = "zwds_ruleset_not_found"


class ZwdsDirectionBasisMissingError(InputError):
    """Not enough information was supplied to resolve the ZWDS flow direction."""

    error_code = "zwds_direction_basis_missing"


class ZwdsRequestedScopeUnavailableError(InputError):
    """The requested ZWDS output scope is not available for this request."""

    error_code = "zwds_requested_scope_unavailable"


# --- Internal integrity / computation failures (HTTP 500 via CalculationError)


class ZwdsCalendarConversionFailedError(CalculationError):
    """Solar/lunar calendar conversion failed while building the ZWDS chart."""

    error_code = "zwds_calendar_conversion_failed"


class ZwdsRulesetIntegrityFailedError(CalculationError):
    """A loaded ZWDS ruleset failed its integrity / fingerprint check."""

    error_code = "zwds_ruleset_integrity_failed"


class ZwdsGraphInvariantFailedError(CalculationError):
    """A ZWDS chart-graph invariant was violated during construction."""

    error_code = "zwds_graph_invariant_failed"


# --- Governance state (HTTP 500 via the engine base) -------------------------


class ZwdsRulesetNotReleaseReadyError(BaziEngineError):
    """The requested ZWDS ruleset exists but is not flagged release-ready."""

    error_code = "zwds_ruleset_not_release_ready"
