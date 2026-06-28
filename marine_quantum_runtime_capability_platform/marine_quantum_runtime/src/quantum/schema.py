# src/quantum/schema.py
# Quantum output schema definitions — stdlib-only version.
# When pydantic is available, use CorrosionInput/CorrosionOutput Pydantic models.

import math


class SchemaValidationError(ValueError):
    pass


CORROSION_INPUT_BOUNDS = {
    "salinity":                    (0.0,  50.0),
    "temperature_celsius":         (-5.0, 45.0),
    "pH":                          (0.0,  14.0),
    "material_oxidation_potential": (-2.0, 2.0),
    "dissolved_oxygen_mgl":        (0.0,  20.0),
    "current_density_mAcm2":       (0.0,  10.0),
}


def validate_corrosion_input(payload: dict) -> dict:
    errors = []
    for field, (lo, hi) in CORROSION_INPUT_BOUNDS.items():
        if field not in payload:
            errors.append(f"Missing required field: '{field}'")
            continue
        v = payload[field]
        try:
            v = float(v)
        except (TypeError, ValueError):
            errors.append(f"Field '{field}' must be numeric, got {type(v).__name__}")
            continue
        if not (lo <= v <= hi):
            errors.append(f"Field '{field}' = {v} out of range [{lo}, {hi}]")
    if errors:
        raise SchemaValidationError("Corrosion input validation failed:\n" + "\n".join(f"  • {e}" for e in errors))
    return {k: float(payload[k]) for k in CORROSION_INPUT_BOUNDS}


def normalize_corrosion_input(validated: dict) -> dict:
    """Map physical values to [0, π] for circuit parameterisation."""
    bounds = CORROSION_INPUT_BOUNDS
    def norm(v, lo, hi):
        return math.pi * (v - lo) / (hi - lo)
    return {
        "theta_salinity":    norm(validated["salinity"],                    *bounds["salinity"]),
        "theta_temperature": norm(validated["temperature_celsius"],         *bounds["temperature_celsius"]),
        "theta_pH":          norm(validated["pH"],                          *bounds["pH"]),
        "theta_oxidation":   norm(validated["material_oxidation_potential"],*bounds["material_oxidation_potential"]),
        "theta_oxygen":      norm(validated["dissolved_oxygen_mgl"],        *bounds["dissolved_oxygen_mgl"]),
        "theta_current":     norm(validated["current_density_mAcm2"],       *bounds["current_density_mAcm2"]),
    }


def validate_corrosion_output(result: dict) -> bool:
    required = ["degradation_probability", "confidence_score", "recommended_anode_current",
                "dominant_state", "measurement_distribution", "shots_used"]
    for k in required:
        if k not in result:
            return False
    if not (0.0 <= result["degradation_probability"] <= 1.0): return False
    if not (0.0 <= result["confidence_score"] <= 1.0):        return False
    if result["confidence_score"] < 0.5:                      return False
    if result["recommended_anode_current"] < 0.0:             return False
    if result["shots_used"] < 512:                            return False
    total = sum(result["measurement_distribution"].values())
    if not (0.99 <= total <= 1.01):                           return False
    if not result["dominant_state"]:                          return False
    return True
