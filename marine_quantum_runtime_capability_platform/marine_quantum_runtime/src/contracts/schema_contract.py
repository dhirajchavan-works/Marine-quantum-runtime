# src/contracts/schema_contract.py
# Schema versioning and contract registry.

SCHEMA_VERSION = "2.0"
ENGINE_EVENT_VERSION = "2.0"

SCHEMA_REGISTRY = {
    "engine_event_v2.0": {
        "version": "2.0",
        "required_fields": [
            "engine_event_version", "node_ref", "transition", "uncertainty_envelope"
        ],
        "transition_fields": ["prev", "next", "cause", "seq", "ts"],
        "uncertainty_fields": ["confidence", "sigma"],
        "valid_states": ["CONVERGED", "SUSPENDED", "DIVERGED"],
        "prev_states": ["INITIALISING", "ACTIVE"],
    }
}


def get_schema(name: str) -> dict:
    if name not in SCHEMA_REGISTRY:
        raise KeyError(f"Schema '{name}' not registered. Available: {list(SCHEMA_REGISTRY)}")
    return SCHEMA_REGISTRY[name]


def validate_against_schema(event: dict, schema_name: str = "engine_event_v2.0") -> dict:
    schema = get_schema(schema_name)
    errors = []
    for k in schema["required_fields"]:
        if k not in event:
            errors.append(f"Missing: '{k}'")
    if "transition" in event:
        t = event["transition"]
        for k in schema["transition_fields"]:
            if k not in t:
                errors.append(f"transition missing: '{k}'")
        if "next" in t and t["next"] not in schema["valid_states"]:
            errors.append(f"transition.next='{t['next']}' invalid")
    if errors:
        return {"valid": False, "errors": errors, "schema": schema_name}
    return {"valid": True, "errors": [], "schema": schema_name}
