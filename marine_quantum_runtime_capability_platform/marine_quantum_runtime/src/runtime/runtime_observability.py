# src/runtime/runtime_observability.py
# Runtime Observability Layer — Marine Intelligence System
# Phase 2: Runtime Capability Platform
#
# Provides structured, deterministic observability APIs for all runtime activity.
# Observability is INFORMATIONAL ONLY — no governance, no decisions.
#
# PUBLIC API:
#   record_invocation(record: InvocationRecord) -> None
#   get_runtime_health() -> dict
#   get_execution_history() -> dict
#   get_capability_metrics() -> dict
#   get_runtime_summary() -> dict
#
# Rules:
#   No external dependencies.
#   All records are append-only — no mutation after write.
#   Timestamps are deterministic seq-based offsets, not wall-clock.
#   No governance logic anywhere in this module.
#   Metrics are read-only views — callers cannot modify them.

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Record ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InvocationRecord:
    """
    Immutable record of a single capability invocation.
    Appended to the history log — never mutated.
    """
    invocation_id:  str           # SHA-256 deterministic ID
    capability_id:  str           # Which capability was invoked
    status:         str           # SUCCESS | FAILED | VALIDATION_ERROR
    seq:            int           # Monotonic sequence number within the runtime session
    duration_ms:    float         # Elapsed wall time in milliseconds
    error:          Optional[str] # Error message if status != SUCCESS
    payload_hash:   str           # SHA-256 of the input payload (not the payload itself)
    output_hash:    str           # SHA-256 of the canonical output (not the output itself)

    def to_dict(self) -> dict:
        return {
            "invocation_id": self.invocation_id,
            "capability_id": self.capability_id,
            "status":        self.status,
            "seq":           self.seq,
            "duration_ms":   self.duration_ms,
            "error":         self.error,
            "payload_hash":  self.payload_hash,
            "output_hash":   self.output_hash,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def make_invocation_id(capability_id: str, seq: int, payload: dict) -> str:
    """Deterministic invocation ID — same inputs always produce the same ID."""
    payload_hash = _sha256(_canonical(payload))
    return _sha256(f"invoke:{capability_id}:ph={payload_hash}")


def make_payload_hash(payload: dict) -> str:
    return _sha256(_canonical(payload))


def make_output_hash(output: Any) -> str:
    return _sha256(_canonical(output))


# ── Per-Capability Metrics ────────────────────────────────────────────────────

class CapabilityMetrics:
    def __init__(self, capability_id: str) -> None:
        self.capability_id  = capability_id
        self._total         = 0
        self._success       = 0
        self._failed        = 0
        self._total_ms      = 0.0
        self._min_ms        = float("inf")
        self._max_ms        = 0.0
        self._last_status   = "IDLE"
        self._last_error:   Optional[str] = None

    def record(self, record: InvocationRecord) -> None:
        self._total       += 1
        self._total_ms    += record.duration_ms
        self._min_ms       = min(self._min_ms, record.duration_ms)
        self._max_ms       = max(self._max_ms, record.duration_ms)
        self._last_status  = record.status
        if record.status == "SUCCESS":
            self._success += 1
        else:
            self._failed     += 1
            self._last_error  = record.error

    def to_dict(self) -> dict:
        avg_ms = (self._total_ms / self._total) if self._total > 0 else 0.0
        health = (
            "IDLE" if self._total == 0 else
            "HEALTHY" if self._failed == 0 else
            "DEGRADED" if (self._failed / self._total) < 0.25 else
            "UNHEALTHY"
        )
        return {
            "capability_id":   self.capability_id,
            "total_invocations": self._total,
            "success_count":   self._success,
            "failure_count":   self._failed,
            "avg_latency_ms":  round(avg_ms, 3),
            "min_latency_ms":  round(self._min_ms, 3) if self._total > 0 else 0.0,
            "max_latency_ms":  round(self._max_ms, 3),
            "last_status":     self._last_status,
            "last_error":      self._last_error,
            "health":          health,
        }


# ── Observability Layer ───────────────────────────────────────────────────────

class RuntimeObservabilityLayer:
    """
    Append-only invocation history with structured metrics and health APIs.

    Observability is informational. This layer never makes decisions.
    It exposes what happened, not what should happen.
    """

    def __init__(self) -> None:
        self._history:  List[InvocationRecord]          = []
        self._metrics:  Dict[str, CapabilityMetrics]    = {}
        self._seq:      int                             = 0

    # -- Write -----------------------------------------------------------------

    def record_invocation(self, record: InvocationRecord) -> None:
        """Append an invocation record. Records are immutable after append."""
        self._history.append(record)
        cid = record.capability_id
        if cid not in self._metrics:
            self._metrics[cid] = CapabilityMetrics(cid)
        self._metrics[cid].record(record)

    def next_seq(self) -> int:
        """Return the next monotonic sequence number for this session."""
        self._seq += 1
        return self._seq

    # -- Read APIs (dashboard-ready JSON) --------------------------------------

    def get_runtime_health(self) -> dict:
        """
        Runtime-wide health summary.

        Exposes: overall status, per-capability health, failure counts.
        Informational only — no decisions embedded.
        """
        cap_health = {cid: m.to_dict()["health"] for cid, m in self._metrics.items()}
        unhealthy  = [cid for cid, h in cap_health.items() if h == "UNHEALTHY"]
        degraded   = [cid for cid, h in cap_health.items() if h == "DEGRADED"]

        if unhealthy:
            overall = "UNHEALTHY"
        elif degraded:
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        return {
            "overall_health":         overall,
            "total_invocations":      len(self._history),
            "capability_health":      cap_health,
            "unhealthy_capabilities": unhealthy,
            "degraded_capabilities":  degraded,
        }

    def get_execution_history(self, limit: Optional[int] = None) -> dict:
        """
        Full invocation timeline, ordered by seq.

        Args:
            limit: if set, return only the last N records.

        Returns dashboard-ready JSON with timeline and totals.
        """
        records = self._history[-limit:] if limit else self._history
        timeline = [r.to_dict() for r in records]
        success  = sum(1 for r in records if r.status == "SUCCESS")
        failed   = sum(1 for r in records if r.status != "SUCCESS")
        return {
            "total_records":   len(timeline),
            "success_count":   success,
            "failure_count":   failed,
            "timeline":        timeline,
        }

    def get_capability_metrics(self) -> dict:
        """
        Per-capability latency, invocation counts, and health.
        Dashboard-ready JSON.
        """
        return {
            cid: m.to_dict()
            for cid, m in self._metrics.items()
        }

    def get_runtime_summary(self) -> dict:
        """
        Full runtime observability summary — all APIs combined.
        Primary endpoint for dashboard consumers.
        """
        health  = self.get_runtime_health()
        history = self.get_execution_history()
        metrics = self.get_capability_metrics()

        # Failure aggregation
        errors = [
            {"seq": r.seq, "capability_id": r.capability_id, "error": r.error}
            for r in self._history
            if r.status != "SUCCESS" and r.error
        ]

        return {
            "runtime_health":     health,
            "execution_history":  history,
            "capability_metrics": metrics,
            "failure_aggregation": {
                "total_failures": len(errors),
                "failures":       errors,
            },
        }

    def get_runtime_heartbeat(self) -> dict:
        """
        Lightweight heartbeat for periodic health polling.
        Returns only current status and counts — no timeline.
        """
        health = self.get_runtime_health()
        return {
            "heartbeat":          "ALIVE",
            "overall_health":     health["overall_health"],
            "total_invocations":  len(self._history),
            "session_seq":        self._seq,
            "active_capabilities": list(self._metrics.keys()),
        }


# ── Module-Level Singleton ────────────────────────────────────────────────────

_OBSERVABILITY = RuntimeObservabilityLayer()


def record_invocation(record: InvocationRecord) -> None:
    _OBSERVABILITY.record_invocation(record)


def get_runtime_health() -> dict:
    return _OBSERVABILITY.get_runtime_health()


def get_execution_history(limit: Optional[int] = None) -> dict:
    return _OBSERVABILITY.get_execution_history(limit=limit)


def get_capability_metrics() -> dict:
    return _OBSERVABILITY.get_capability_metrics()


def get_runtime_summary() -> dict:
    return _OBSERVABILITY.get_runtime_summary()


def get_runtime_heartbeat() -> dict:
    return _OBSERVABILITY.get_runtime_heartbeat()


def next_seq() -> int:
    return _OBSERVABILITY.next_seq()
