# invoke_runtime.py
# Phase 2 — Runtime Surface Unification
#
# Single unified invocation surface for all marine_quantum_runtime modules.
#
# Usage:
#   from invoke_runtime import invoke_runtime
#   result = invoke_runtime("signal", payload)
#
# Supported modules:
#   signal              — quantum signal generator (Dhiraj layer)
#   quantum_pipeline    — marine corrosion QApp via AerSimulator
#   distributed_qapp    — 3-node propagation runtime (Kanishk/Jaffer Ali layer)
#   operational_monitor — drift detection and observability
#
# Result schema (all modules):
# {
#   "status":            "SUCCESS" | "FAILED",
#   "execution_id":      str (SHA-256),
#   "deterministic_hash":str (SHA-256 of canonical output),
#   "duration_ms":       float,
#   "metrics":           dict,
#   "payload":           dict (echo of input),
#   "errors":            list[str]
# }
#
# Rules:
#   replay-safe           — same payload → same execution_id
#   deterministic         — no datetime.now() in output hashing
#   structured logs       — every invocation logged to console
#   contract validation   — input checked before any execution
#   no script-only logic  — everything callable from Python

import hashlib
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

_ANCHOR = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_SUPPORTED = {"signal", "quantum_pipeline", "distributed_qapp", "operational_monitor"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _execution_id(module: str, payload: dict) -> str:
    """Deterministic per (module, payload). Same input → same ID. Replay-safe."""
    return _sha256(f"exec:{module}:{_canonical(payload)}")


def _deterministic_hash(result: Any) -> str:
    """SHA-256 of the canonical result. Proves identical outputs across runs."""
    return _sha256(_canonical(result))


def _success(module: str, payload: dict, output: Any, metrics: dict, elapsed_ms: float) -> dict:
    return {
        "status":             "SUCCESS",
        "module":             module,
        "execution_id":       _execution_id(module, payload),
        "deterministic_hash": _deterministic_hash(output),
        "duration_ms":        round(elapsed_ms, 3),
        "metrics":            metrics,
        "payload":            payload,
        "output":             output,
        "errors":             [],
    }


def _failure(module: str, payload: dict, errors: list, elapsed_ms: float) -> dict:
    return {
        "status":             "FAILED",
        "module":             module,
        "execution_id":       _execution_id(module, payload),
        "deterministic_hash": "",
        "duration_ms":        round(elapsed_ms, 3),
        "metrics":            {},
        "payload":            payload,
        "output":             None,
        "errors":             errors,
    }


# ── Module runners ─────────────────────────────────────────────────────────────

def _run_signal(payload: dict) -> dict:
    from src.signal.signal_generator import generate_state_event
    from src.signal.validator import ValidationError
    try:
        event = generate_state_event(payload)
        return {"output": event, "errors": [], "metrics": {
            "transition": event["transition"]["next"],
            "sigma": event["uncertainty_envelope"]["sigma"],
        }}
    except ValidationError as exc:
        return {"output": None, "errors": [str(exc)], "metrics": {}}
    except Exception as exc:
        return {"output": None, "errors": [f"UnexpectedError: {exc}"], "metrics": {}}


def _run_quantum_pipeline(payload: dict) -> dict:
    from src.quantum.schema import CorrosionInput
    from src.quantum.execution import run_corrosion_qapp, validate_quantum_contract
    try:
        inp = CorrosionInput(**payload)
    except Exception as exc:
        return {"output": None, "errors": [f"InputValidation: {exc}"], "metrics": {}}
    try:
        seed  = int(payload.get("seed", 42))
        shots = int(payload.get("shots", 4096))
        raw   = run_corrosion_qapp(inp, seed=seed, shots=shots)
        if not validate_quantum_contract(raw):
            return {"output": None, "errors": ["CONTRACT_VIOLATION: output failed quantum contract"], "metrics": {}}
        return {"output": raw, "errors": [], "metrics": {
            "degradation_probability":  raw["degradation_probability"],
            "confidence_score":         raw["confidence_score"],
            "recommended_anode_current":raw["recommended_anode_current"],
        }}
    except Exception as exc:
        return {"output": None, "errors": [f"QuantumExecution: {exc}"], "metrics": {}}


def _run_distributed_qapp(payload: dict) -> dict:
    """
    Single-envelope propagation run.
    payload must have: qapp_id, node_origin, sequence_id, contract_version, data (dict).
    """
    from src.runtime.envelope import QAppExecutionEnvelope
    from src.runtime.nodes import DistributedNode, init_node_hash
    from src.runtime.propagation import propagate_qapp_event, replay_qapp_log, clear_propagation_log
    from src.runtime.nodes import reset_all_nodes

    required = {"qapp_id", "node_origin", "sequence_id", "data"}
    missing  = required - set(payload.keys())
    if missing:
        return {"output": None, "errors": [f"MissingFields: {sorted(missing)}"], "metrics": {}}

    try:
        reset_all_nodes()
        clear_propagation_log()

        env = QAppExecutionEnvelope.create(
            qapp_id          = payload["qapp_id"],
            node_origin      = payload["node_origin"],
            payload          = payload["data"],
            sequence_id      = int(payload["sequence_id"]),
            contract_version = payload.get("contract_version", "qapp-v1.0"),
        )
        propagate_qapp_event(env)
        replay_result = replay_qapp_log(silent=True)

        output = {
            "envelope":       env.to_dict(),
            "replay":         replay_result,
            "consistent":     replay_result["consistent"],
            "consensus_hash": replay_result["consensus_hash"],
        }
        return {"output": output, "errors": [], "metrics": {
            "consistent":     replay_result["consistent"],
            "log_entries":    replay_result["log_entry_count"],
            "consensus_hash": replay_result["consensus_hash"][:16] + "...",
        }}
    except Exception as exc:
        return {"output": None, "errors": [f"PropagationError: {exc}"], "metrics": {}}


def _run_operational_monitor(payload: dict) -> dict:
    """
    Ingest a list of engine events and return drift report.
    payload must have: events (list of engine event dicts), [window] (int).
    """
    from src.monitoring.operational_drift_monitor import record_event, compute_drift_report, reset
    if "events" not in payload:
        return {"output": None, "errors": ["MissingField: 'events' list required"], "metrics": {}}
    try:
        reset()
        for ev in payload["events"]:
            record_event(ev)
        window = int(payload.get("window", 20))
        report = compute_drift_report(window=window)
        return {"output": report, "errors": [], "metrics": {
            "drift_status":  report["drift_status"],
            "total_events":  report["total_events"],
            "alerts_count":  len(report["alerts"]),
        }}
    except Exception as exc:
        return {"output": None, "errors": [f"MonitorError: {exc}"], "metrics": {}}


# ── Dispatch table ─────────────────────────────────────────────────────────────

_DISPATCH = {
    "signal":               _run_signal,
    "quantum_pipeline":     _run_quantum_pipeline,
    "distributed_qapp":     _run_distributed_qapp,
    "operational_monitor":  _run_operational_monitor,
}


# ── Public API ─────────────────────────────────────────────────────────────────

def invoke_runtime(module_name: str, payload: dict) -> dict:
    """
    Unified runtime invocation surface.

    Parameters
    ----------
    module_name : str
        One of: signal, quantum_pipeline, distributed_qapp, operational_monitor.
    payload : dict
        Module-specific input. See each _run_* function for schema.

    Returns
    -------
    dict
        Structured result with status, execution_id, deterministic_hash,
        duration_ms, metrics, payload, output, errors.
    """
    t0 = time.perf_counter()

    print(f"\n[INVOKE] module={module_name!r}  exec_id={_execution_id(module_name, payload)[:16]}...")

    if module_name not in _SUPPORTED:
        elapsed = (time.perf_counter() - t0) * 1000
        return _failure(module_name, payload, [
            f"UnknownModule: '{module_name}'. Supported: {sorted(_SUPPORTED)}"
        ], elapsed)

    runner = _DISPATCH[module_name]
    inner  = runner(payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if inner["errors"]:
        result = _failure(module_name, payload, inner["errors"], elapsed_ms)
        print(f"[INVOKE] FAILED  duration={elapsed_ms:.1f}ms  errors={inner['errors']}")
    else:
        result = _success(module_name, payload, inner["output"], inner["metrics"], elapsed_ms)
        print(f"[INVOKE] SUCCESS  duration={elapsed_ms:.1f}ms  hash={result['deterministic_hash'][:16]}...")

    return result
