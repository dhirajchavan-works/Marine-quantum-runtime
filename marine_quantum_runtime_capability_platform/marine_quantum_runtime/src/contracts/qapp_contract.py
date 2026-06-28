# src/contracts/qapp_contract.py
# Integration contract enforcement between quantum execution and BHIV Core.
# MARINE-INT-002 v1.0.0

CONTRACT_VERSION = "MARINE-INT-002-v1.0.0"

REQUIRED_OUTPUT_KEYS = [
    "engine_event_version", "node_ref", "transition", "uncertainty_envelope"
]

TRANSITION_KEYS = ["prev", "next", "cause", "seq", "ts"]

VALID_STATES = {"CONVERGED", "SUSPENDED", "DIVERGED"}


class ContractViolation(Exception):
    pass


def enforce_signal_contract(event: dict) -> dict:
    errors = []
    for k in REQUIRED_OUTPUT_KEYS:
        if k not in event:
            errors.append(f"Missing top-level key: '{k}'")
    if "transition" in event:
        t = event["transition"]
        for k in TRANSITION_KEYS:
            if k not in t:
                errors.append(f"transition missing: '{k}'")
        if t.get("next") not in VALID_STATES:
            errors.append(f"transition.next='{t.get('next')}' not in {VALID_STATES}")
    if "uncertainty_envelope" in event:
        ue = event["uncertainty_envelope"]
        if "confidence" not in ue or "sigma" not in ue:
            errors.append("uncertainty_envelope missing confidence or sigma")
        else:
            if not (0.0 <= ue["confidence"] <= 1.0):
                errors.append(f"confidence={ue['confidence']} out of [0.0, 1.0]")
            if ue["sigma"] < 0:
                errors.append(f"sigma={ue['sigma']} must be >= 0")
    if errors:
        raise ContractViolation(
            f"Contract {CONTRACT_VERSION} violated ({len(errors)} error(s)):\n"
            + "\n".join(f"  • {e}" for e in errors)
        )
    return {"status": "PASS", "contract": CONTRACT_VERSION}


def get_contract_summary() -> dict:
    return {
        "contract_id":      CONTRACT_VERSION,
        "valid_states":     sorted(VALID_STATES),
        "required_keys":    REQUIRED_OUTPUT_KEYS,
        "transition_keys":  TRANSITION_KEYS,
        "confidence_range": "[0.0, 1.0]",
        "sigma_bound":      ">= 0.0",
    }
