# src/runtime/envelope.py
# QAppExecutionEnvelope — immutable execution envelope for distributed QApp propagation.
#
# Rules:
#   no datetime.now()  — timestamp is deterministic from sequence_id
#   no randomness      — all IDs are SHA-256 of deterministic inputs
#   frozen dataclass   — immutable after construction

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

_ANCHOR       = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_STEP_SECONDS = 60
CONTRACT_DEFAULT = "qapp-v1.0"


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def compute_trace_id(qapp_id: str, node_origin: str, sequence_id: int) -> str:
    return _sha256(f"trace:{qapp_id}:{node_origin}:{sequence_id}")


def compute_invocation_id(trace_id: str, payload_hash: str, sequence_id: int) -> str:
    return _sha256(f"invoke:{trace_id}:{payload_hash}:{sequence_id}")


def compute_timestamp(sequence_id: int) -> str:
    ts = _ANCHOR + timedelta(seconds=sequence_id * _STEP_SECONDS)
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class QAppExecutionEnvelope:
    trace_id:         str
    qapp_id:          str
    node_origin:      str
    invocation_id:    str
    payload_hash:     str
    sequence_id:      int
    timestamp:        str
    contract_version: str

    @classmethod
    def create(cls, qapp_id: str, node_origin: str, payload: dict,
               sequence_id: int, contract_version: str = CONTRACT_DEFAULT) -> "QAppExecutionEnvelope":
        payload_hash  = compute_payload_hash(payload)
        trace_id      = compute_trace_id(qapp_id, node_origin, sequence_id)
        invocation_id = compute_invocation_id(trace_id, payload_hash, sequence_id)
        timestamp     = compute_timestamp(sequence_id)
        return cls(
            trace_id=trace_id, qapp_id=qapp_id, node_origin=node_origin,
            invocation_id=invocation_id, payload_hash=payload_hash,
            sequence_id=sequence_id, timestamp=timestamp,
            contract_version=contract_version,
        )

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id, "qapp_id": self.qapp_id,
            "node_origin": self.node_origin, "invocation_id": self.invocation_id,
            "payload_hash": self.payload_hash, "sequence_id": self.sequence_id,
            "timestamp": self.timestamp, "contract_version": self.contract_version,
        }

    def short(self) -> str:
        return (f"Envelope(seq={self.sequence_id}, qapp={self.qapp_id!r}, "
                f"origin={self.node_origin}, invoke={self.invocation_id[:12]}...)")
