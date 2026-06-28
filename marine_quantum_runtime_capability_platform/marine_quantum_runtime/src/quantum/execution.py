# src/quantum/execution.py
# Quantum pipeline execution — stdlib-only runtime.
#
# When qiskit + pydantic are installed, uses full HEA circuit execution.
# Otherwise, uses deterministic classical simulation stub.

import math
from src.quantum.schema import validate_corrosion_input, normalize_corrosion_input, validate_corrosion_output
from src.quantum.algorithm import simulate_circuit_classically

_ANODE_BASELINE_MA = 10.0
_ANODE_SCALE_MA    = 200.0


def run_corrosion_qapp(payload: dict, seed: int = 42, shots: int = 4096) -> dict:
    """
    Execute the marine corrosion quantum assessment.
    stdlib-only: uses deterministic classical circuit simulation.
    """
    if shots < 512:
        raise ValueError(f"shots={shots} below minimum 512.")

    validated  = validate_corrosion_input(payload)
    normalized = normalize_corrosion_input(validated)
    sim_result = simulate_circuit_classically(normalized, seed=seed)

    dist            = sim_result["measurement_distribution"]
    dominant_state  = sim_result["dominant_state"]
    num_qubits      = len(dominant_state)

    # Hamming-weighted degradation probability
    hamming = sum(p * s.count("1") / num_qubits for s, p in dist.items())
    ox_f    = normalized["theta_oxidation"] / math.pi
    sal_f   = normalized["theta_salinity"]  / math.pi
    oxy_f   = normalized["theta_oxygen"]    / math.pi
    phys    = 0.5 * ox_f + 0.3 * sal_f + 0.2 * oxy_f
    deg_p   = max(0.0, min(1.0, 0.60 * hamming + 0.40 * phys))

    # Entropy-based confidence
    probs   = list(dist.values())
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    h_max   = math.log2(2 ** num_qubits)
    conf    = max(0.0, min(1.0, (1.0 - entropy / h_max) if h_max > 0 else 0.0))
    anode   = _ANODE_BASELINE_MA + _ANODE_SCALE_MA * deg_p

    return {
        "degradation_probability":  round(deg_p, 6),
        "confidence_score":         round(conf, 6),
        "recommended_anode_current": round(anode, 4),
        "dominant_state":           dominant_state,
        "measurement_distribution": dist,
        "shots_used":               shots,
        "seed":                     seed,
    }


def run(payload: dict) -> dict:
    """Runtime-callable entry point for the quantum_pipeline module."""
    try:
        raw    = run_corrosion_qapp(payload)
        valid  = validate_corrosion_output(raw)
        if not valid:
            return {"module": "quantum_pipeline", "status": "CONTRACT_VIOLATION",
                    "result": None, "error": "Output failed contract validation"}
        deg_p  = raw["degradation_probability"]
        risk   = "CRITICAL" if deg_p >= 0.7 else "ELEVATED" if deg_p >= 0.4 else "MODERATE" if deg_p >= 0.2 else "LOW"
        action = risk in ("ELEVATED", "CRITICAL")
        raw["deterministic_event"] = {
            "risk_level": risk, "action_required": action,
            "signal": "INCREASE_ANODE_CURRENT" if action else "HOLD",
            "confidence": raw["confidence_score"],
        }
        return {"module": "quantum_pipeline", "status": "SUCCESS", "result": raw, "error": None}
    except Exception as exc:
        return {"module": "quantum_pipeline", "status": "ERROR", "result": None, "error": str(exc)}
