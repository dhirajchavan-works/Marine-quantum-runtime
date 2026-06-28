# src/runtime/capability_runtime.py
# Runtime Capability Platform — Invocation Surface
# Phase 3: Production Runtime Integration
#
# This module wraps the existing invoke_runtime dispatch table through:
#   1. RuntimeCapabilityRegistry  — capability discovery + attachment validation
#   2. RuntimeObservabilityLayer  — invocation recording + metrics
#
# PUBLIC API:
#   invoke_capability(capability_id: str, payload: dict) -> dict
#   get_active_capabilities() -> list[dict]
#   get_runtime_health() -> dict
#   get_execution_timeline() -> dict
#   get_latency_metrics() -> dict
#   get_capability_availability() -> dict
#   get_dashboard_json() -> dict        ← Phase 4: Dashboard Capability Surface
#   get_replay_statistics() -> dict     ← Phase 4: Replay stats placeholder
#   get_provenance_status() -> dict     ← Phase 4: Provenance status placeholder
#
# Integration posture:
#   Replay authority    — consumed from CanonicalReplayAuthority (Pritesh layer); never decided locally.
#   Provenance          — ExecutionRecord emitted; never owned locally.
#   Optimization        — attachment surface only; no optimization logic inside runtime.
#
# Rules:
#   No datetime.now() anywhere.
#   All invocation IDs are SHA-256 deterministic.
#   Observability is append-only.
#   This module does NOT replace invoke_runtime.py — it wraps it.

import hashlib
import json
import sys
import os
import time
from typing import Any, Dict, List, Optional

# Path resolution — callable from any working directory
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.runtime.runtime_capability_registry import (
    discover_capability,
    list_capabilities,
    get_capability_health,
    get_registry_summary,
    validate_attachment,
    record_invocation_result,
    RegistryError,
    CapabilityNotFound,
)
from src.runtime.runtime_observability import (
    record_invocation,
    get_runtime_health,
    get_execution_history,
    get_capability_metrics,
    get_runtime_summary,
    get_runtime_heartbeat,
    next_seq,
    InvocationRecord,
    make_invocation_id,
    make_payload_hash,
    make_output_hash,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ── Replay Authority Stub ─────────────────────────────────────────────────────
# The runtime consumes replay authority — it never makes replay decisions.
# When Pritesh's CanonicalReplayAuthority is attached, this stub is replaced.

class _CanonicalReplayAuthorityStub:
    """
    Placeholder for Pritesh's CanonicalReplayAuthority.
    The runtime calls this before every execution.
    Returns PERMIT unless overridden by the real authority.
    """
    def check(self, capability_id: str, payload: dict) -> dict:
        return {
            "authority":    "CanonicalReplayAuthority",
            "decision":     "PERMIT",
            "reason":       "stub — attach real authority via attach_replay_authority()",
            "capability_id": capability_id,
        }


_replay_authority = _CanonicalReplayAuthorityStub()


def attach_replay_authority(authority: Any) -> None:
    """
    Attach Pritesh's CanonicalReplayAuthority.
    The authority must implement: check(capability_id, payload) -> dict
    with a 'decision' key of 'PERMIT' or 'DENY'.
    """
    global _replay_authority
    _replay_authority = authority


# ── Provenance Stub ───────────────────────────────────────────────────────────
# The runtime emits execution records — it never owns provenance.

class _EvidenceLedgerStub:
    """
    Placeholder for Pritesh's EvidenceLedger.
    Collects execution records locally until the real ledger is attached.
    """
    def __init__(self) -> None:
        self._records: List[dict] = []

    def append(self, record: dict) -> None:
        self._records.append(record)

    def get_records(self) -> List[dict]:
        return list(self._records)

    def count(self) -> int:
        return len(self._records)


_evidence_ledger = _EvidenceLedgerStub()


def attach_evidence_ledger(ledger: Any) -> None:
    """
    Attach Pritesh's EvidenceLedger.
    The ledger must implement: append(record: dict) -> None
    """
    global _evidence_ledger
    _evidence_ledger = ledger


# ── Core Invocation ───────────────────────────────────────────────────────────

def invoke_capability(capability_id: str, payload: dict) -> dict:
    """
    Invoke a registered capability through the full capability platform stack:

        Attachment Validation
              ↓
        Replay Authority Check
              ↓
        Runtime Execution (via invoke_runtime dispatch)
              ↓
        Execution Evidence Emission
              ↓
        Observability Recording
              ↓
        Return to Caller

    Args:
        capability_id : str  — registered capability ID
        payload       : dict — capability-specific input

    Returns:
        dict with keys:
            status, capability_id, invocation_id, deterministic_hash,
            duration_ms, output, errors, replay_authority, provenance_ref
    """
    t0  = time.perf_counter()
    seq = next_seq()

    # 1. Discover capability
    try:
        descriptor = discover_capability(capability_id)
    except CapabilityNotFound as exc:
        return {
            "status":        "CAPABILITY_NOT_FOUND",
            "capability_id": capability_id,
            "errors":        [str(exc)],
        }

    # 2. Attachment validation — inputs must satisfy declared contract
    attachment = validate_attachment(capability_id, payload)
    if not attachment["valid"]:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"AttachmentViolation: missing inputs {attachment['missing']} for capability '{capability_id}'"
        _emit_invocation_record(capability_id, seq, payload, None, "VALIDATION_ERROR", err, elapsed_ms)
        return {
            "status":           "VALIDATION_ERROR",
            "capability_id":    capability_id,
            "invocation_id":    make_invocation_id(capability_id, seq, payload),
            "errors":           [err],
            "attachment_check": attachment,
        }

    # 3. Replay authority check — consume, never decide
    replay_decision = _replay_authority.check(capability_id, payload)
    if replay_decision.get("decision") != "PERMIT":
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"ReplayAuthority DENY: {replay_decision.get('reason', 'no reason given')}"
        _emit_invocation_record(capability_id, seq, payload, None, "REPLAY_DENIED", err, elapsed_ms)
        return {
            "status":           "REPLAY_DENIED",
            "capability_id":    capability_id,
            "invocation_id":    make_invocation_id(capability_id, seq, payload),
            "replay_authority": replay_decision,
            "errors":           [err],
        }

    # 4. Execute via existing invoke_runtime dispatch
    try:
        # Import the existing dispatch — capability platform wraps it, doesn't replace it
        import invoke_runtime as _ir
        inner_result = _ir.invoke_runtime(capability_id, payload)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        err = f"ExecutionError: {exc}"
        _emit_invocation_record(capability_id, seq, payload, None, "FAILED", err, elapsed_ms)
        record_invocation_result(capability_id, success=False, error=err)
        return {
            "status":        "FAILED",
            "capability_id": capability_id,
            "invocation_id": make_invocation_id(capability_id, seq, payload),
            "errors":        [err],
        }

    elapsed_ms = (time.perf_counter() - t0) * 1000
    succeeded  = inner_result.get("status") == "SUCCESS"
    errors     = inner_result.get("errors", [])
    output     = inner_result.get("output")

    # 5. Emit execution evidence (consumed by Pritesh's provenance layer)
    invocation_id = make_invocation_id(capability_id, seq, payload)
    evidence_record = {
        "invocation_id":      invocation_id,
        "capability_id":      capability_id,
        "capability_version": descriptor.version,
        "owner":              descriptor.owner,
        "seq":                seq,
        "status":             "SUCCESS" if succeeded else "FAILED",
        "deterministic_hash": inner_result.get("deterministic_hash", ""),
        "payload_hash":       make_payload_hash(payload),
        "output_hash":        make_output_hash(output) if output else "",
        "duration_ms":        round(elapsed_ms, 3),
        "errors":             errors,
    }
    _evidence_ledger.append(evidence_record)

    # 6. Record to observability layer
    status_str = "SUCCESS" if succeeded else "FAILED"
    _emit_invocation_record(
        capability_id, seq, payload, output,
        status_str, errors[0] if errors else None, elapsed_ms
    )
    record_invocation_result(capability_id, success=succeeded, error=errors[0] if errors else None)

    # 7. Assemble and return
    result = {
        "status":             status_str,
        "capability_id":      capability_id,
        "invocation_id":      invocation_id,
        "deterministic_hash": inner_result.get("deterministic_hash", ""),
        "duration_ms":        round(elapsed_ms, 3),
        "output":             output,
        "errors":             errors,
        "replay_authority":   replay_decision,
        "provenance_ref":     invocation_id,    # reference key for Pritesh's ledger
        "metrics":            inner_result.get("metrics", {}),
    }
    return result


def _emit_invocation_record(
    capability_id: str,
    seq:           int,
    payload:       dict,
    output:        Any,
    status:        str,
    error:         Optional[str],
    duration_ms:   float,
) -> None:
    record = InvocationRecord(
        invocation_id = make_invocation_id(capability_id, seq, payload),
        capability_id = capability_id,
        status        = status,
        seq           = seq,
        duration_ms   = round(duration_ms, 3),
        error         = error,
        payload_hash  = make_payload_hash(payload),
        output_hash   = make_output_hash(output) if output else "",
    )
    record_invocation(record)


# ── Phase 4: Dashboard Capability Surface APIs ────────────────────────────────

def get_active_capabilities() -> List[dict]:
    """
    List all registered capabilities with their current health.
    Dashboard-ready JSON.
    """
    caps    = list_capabilities()
    metrics = get_capability_metrics()
    for cap in caps:
        cid = cap["capability_id"]
        cap["health"] = metrics.get(cid, {}).get("health", "IDLE")
    return caps


def get_latency_metrics() -> dict:
    """Per-capability latency metrics. Dashboard-ready JSON."""
    raw = get_capability_metrics()
    return {
        cid: {
            "avg_latency_ms": m.get("avg_latency_ms", 0.0),
            "min_latency_ms": m.get("min_latency_ms", 0.0),
            "max_latency_ms": m.get("max_latency_ms", 0.0),
        }
        for cid, m in raw.items()
    }


def get_capability_availability() -> dict:
    """
    Current availability status for each registered capability.
    AVAILABLE | DEGRADED | UNAVAILABLE | IDLE
    """
    caps    = list_capabilities()
    metrics = get_capability_metrics()
    result  = {}
    for cap in caps:
        cid    = cap["capability_id"]
        health = metrics.get(cid, {}).get("health", "IDLE")
        result[cid] = {
            "availability": "AVAILABLE" if health in ("HEALTHY", "IDLE") else health,
            "version":      cap["version"],
            "owner":        cap["owner"],
        }
    return result


def get_replay_statistics() -> dict:
    """
    Replay statistics surface — consumed from Pritesh's CanonicalReplayAuthority.
    Returns stub data until the real authority is attached.
    """
    return {
        "replay_authority": "CanonicalReplayAuthority",
        "authority_status": "STUB — attach via attach_replay_authority()",
        "permits_issued":   "N/A",
        "denials_issued":   "N/A",
        "note": "This runtime consumes replay authority. It does not own it.",
    }


def get_provenance_status() -> dict:
    """
    Provenance status — execution evidence emitted to Pritesh's EvidenceLedger.
    Returns count of records buffered in local stub until real ledger is attached.
    """
    return {
        "evidence_ledger":  "EvidenceLedger",
        "ledger_status":    "STUB — attach via attach_evidence_ledger()",
        "records_buffered": _evidence_ledger.count(),
        "note": "This runtime emits execution evidence. It does not own provenance.",
    }


def get_dashboard_json() -> dict:
    """
    Complete dashboard-ready JSON output — Phase 4 primary endpoint.

    Aggregates:
        - active_capabilities
        - runtime_health
        - execution_timeline (last 20)
        - latency_metrics
        - capability_availability
        - replay_statistics
        - provenance_status
        - registry_summary
    """
    return {
        "active_capabilities":   get_active_capabilities(),
        "runtime_health":        get_runtime_health(),
        "execution_timeline":    get_execution_history(limit=20),
        "latency_metrics":       get_latency_metrics(),
        "capability_availability": get_capability_availability(),
        "replay_statistics":     get_replay_statistics(),
        "provenance_status":     get_provenance_status(),
        "registry_summary":      get_registry_summary(),
        "runtime_heartbeat":     get_runtime_heartbeat(),
    }
