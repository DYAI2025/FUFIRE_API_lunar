"""ZWDS-P0-04 — typed failure-code contract.

Every ZWDS failure code is a distinct exception class carrying a frozen
``error_code`` string. Base choice encodes the HTTP status contract:
caller-input failures are ``InputError`` (4xx); internal integrity/computation
failures and the release-gate state are engine-base subclasses (5xx). Because
all of them ultimately subclass ``BaziEngineError``, the global handler in
``error_handlers.py`` renders each into the standard ErrorEnvelope with no
handler changes.
"""

from __future__ import annotations

import pytest

from bazi_engine import exc
from bazi_engine.zwds import errors

# class name -> exact, contract-frozen error_code string
NAME_TO_CODE = {
    "ZwdsBirthTimeRequiredError": "zwds_birth_time_required",
    "ZwdsRulesetNotFoundError": "zwds_ruleset_not_found",
    "ZwdsRulesetNotReleaseReadyError": "zwds_ruleset_not_release_ready",
    "ZwdsCalendarConversionFailedError": "zwds_calendar_conversion_failed",
    "ZwdsDirectionBasisMissingError": "zwds_direction_basis_missing",
    "ZwdsRequestedScopeUnavailableError": "zwds_requested_scope_unavailable",
    "ZwdsRulesetIntegrityFailedError": "zwds_ruleset_integrity_failed",
    "ZwdsGraphInvariantFailedError": "zwds_graph_invariant_failed",
}

# class name -> expected immediate base from bazi_engine.exc
NAME_TO_BASE = {
    "ZwdsBirthTimeRequiredError": exc.InputError,
    "ZwdsRulesetNotFoundError": exc.InputError,
    "ZwdsDirectionBasisMissingError": exc.InputError,
    "ZwdsRequestedScopeUnavailableError": exc.InputError,
    "ZwdsCalendarConversionFailedError": exc.CalculationError,
    "ZwdsRulesetIntegrityFailedError": exc.CalculationError,
    "ZwdsGraphInvariantFailedError": exc.CalculationError,
    "ZwdsRulesetNotReleaseReadyError": exc.BaziEngineError,
}

# The four caller-input codes MUST render as a 4xx.
CALLER_INPUT_NAMES = {
    "ZwdsBirthTimeRequiredError",
    "ZwdsRulesetNotFoundError",
    "ZwdsDirectionBasisMissingError",
    "ZwdsRequestedScopeUnavailableError",
}


def test_contract_maps_are_complete() -> None:
    # Both maps describe exactly the same eight classes.
    assert set(NAME_TO_CODE) == set(NAME_TO_BASE)
    assert len(NAME_TO_CODE) == 8


@pytest.mark.parametrize("name, code", sorted(NAME_TO_CODE.items()))
def test_error_class_exists_with_exact_code(name: str, code: str) -> None:
    cls = getattr(errors, name)
    assert isinstance(cls, type)
    assert cls.error_code == code


@pytest.mark.parametrize("name, base", sorted(NAME_TO_BASE.items()))
def test_error_class_subclasses_expected_base(name: str, base: type) -> None:
    cls = getattr(errors, name)
    assert issubclass(cls, base)
    # Every ZWDS error is a BaziEngineError so the global handler catches it.
    assert issubclass(cls, exc.BaziEngineError)


@pytest.mark.parametrize("name", sorted(NAME_TO_CODE))
def test_status_split_caller_input_is_4xx(name: str) -> None:
    cls = getattr(errors, name)
    if name in CALLER_INPUT_NAMES:
        assert issubclass(cls, exc.InputError)
        assert 400 <= cls.http_status < 500
    else:
        # Internal integrity / release-gate failures are server-side (5xx),
        # never surfaced as caller-fixable input errors.
        assert 500 <= cls.http_status < 600
        assert not issubclass(cls, exc.InputError)


@pytest.mark.parametrize("name, code", sorted(NAME_TO_CODE.items()))
def test_raise_roundtrips_message_code_and_detail(name: str, code: str) -> None:
    cls = getattr(errors, name)
    message = f"boom::{code}"
    with pytest.raises(cls) as excinfo:
        raise cls(message, detail={"field": "when"})
    err = excinfo.value
    # error_code is accessible on the instance and str(exc) contains the message.
    assert err.error_code == code
    assert message in str(err)
    # detail dict capability is preserved from the base (no __init__ override).
    assert err.detail == {"field": "when"}
    # to_dict() (what error_handlers renders) carries the machine-readable code.
    body = err.to_dict()
    assert body["error"] == code
    assert message in body["message"]
    assert body["detail"] == {"field": "when"}


def test_raise_without_detail_defaults_to_empty_dict() -> None:
    with pytest.raises(errors.ZwdsBirthTimeRequiredError) as excinfo:
        raise errors.ZwdsBirthTimeRequiredError("birth time missing")
    assert excinfo.value.detail == {}


def test_zwds_error_maps_into_error_envelope_or_skips() -> None:
    """Sub-assertion (4): ErrorEnvelope rendering.

    ``error_handlers.py`` wires every ``BaziEngineError`` subclass through
    ``register_exception_handlers`` -> ``_error_body``, but ``_error_body``
    needs a live starlette ``Request`` (it reads ``request.url.path`` and
    ``request.state``) and the handlers are async closures bound to the app.
    There is no request-free pure mapping function to call, so per the task we
    SKIP rather than fabricate a Request. The real ErrorEnvelope / HTTP-boundary
    assertion belongs to the later ZWDS endpoint task (TestClient on resp.json()).
    """
    from bazi_engine import error_handlers

    pure_mapping = getattr(error_handlers, "map_to_envelope", None)
    if pure_mapping is None:
        pytest.skip(
            "error_handlers exposes no request-free mapping function "
            "(_error_body requires a live Request); ErrorEnvelope shape is "
            "verified at the HTTP boundary in the ZWDS endpoint task"
        )
    envelope = pure_mapping(errors.ZwdsRulesetNotFoundError("nope"))
    assert envelope["error"] == "zwds_ruleset_not_found"
