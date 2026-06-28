# src/runtime/propagation.py
# Distributed QApp propagation engine.

import hashlib
import json
from typing import Optional

from src.runtime.envelope import QAppExecutionEnvelope
from src.runtime.nodes import Node_A, Node_B, Node_C, init_node_hash

_ALL_NODE_IDS = ["Node_A", "Node_B", "Node_C"]
_STEP_ORDER: dict = {"ORIGIN": 0, "PROPAGATE": 1}
_PROPAGATION_LOG: list = []


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _append(entry: dict) -> None:
    _PROPAGATION_LOG.append(entry)


def get_propagation_log() -> list:
    return list(_PROPAGATION_LOG)


def clear_propagation_log() -> None:
    _PROPAGATION_LOG.clear()


def propagate_qapp_event(envelope: QAppExecutionEnvelope) -> None:
    env_dict = envelope.to_dict()
    print(f"\n  [PROPAGATE] seq={envelope.sequence_id} | ts={envelope.timestamp}")
    print(f"    trace      : {envelope.trace_id[:24]}...")
    print(f"    invocation : {envelope.invocation_id[:24]}...")

    Node_A.receive(env_dict)
    _append({"step": "ORIGIN", "from": "Node_A", "to": "Node_A",
             "invocation_id": envelope.invocation_id, "sequence_id": envelope.sequence_id,
             "trace_id": envelope.trace_id, "timestamp": envelope.timestamp})
    print(f"\n    Node_A  ← origin    hash={Node_A.execution_hash[:16]}...")

    Node_A.record_propagation(env_dict, "Node_B")
    Node_B.receive(env_dict)
    _append({"step": "PROPAGATE", "from": "Node_A", "to": "Node_B",
             "invocation_id": envelope.invocation_id, "sequence_id": envelope.sequence_id,
             "trace_id": envelope.trace_id, "timestamp": envelope.timestamp})
    print(f"    Node_A → Node_B  ✅  hash={Node_B.execution_hash[:16]}...")

    Node_A.record_propagation(env_dict, "Node_C")
    Node_C.receive(env_dict)
    _append({"step": "PROPAGATE", "from": "Node_A", "to": "Node_C",
             "invocation_id": envelope.invocation_id, "sequence_id": envelope.sequence_id,
             "trace_id": envelope.trace_id, "timestamp": envelope.timestamp})
    print(f"    Node_A → Node_C  ✅  hash={Node_C.execution_hash[:16]}...")


def _replay_node_hashes(sorted_log: list) -> dict:
    hashes = {nid: init_node_hash(nid) for nid in _ALL_NODE_IDS}
    for entry in sorted_log:
        to = entry["to"]
        if to in hashes:
            hashes[to] = _sha256(f"{hashes[to]}:{entry['invocation_id']}")
    return hashes


def _compute_log_hash(sorted_log: list) -> str:
    canonical = json.dumps(sorted_log, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def _compute_consensus_hash(node_hashes: dict) -> str:
    ordered = json.dumps({k: node_hashes[k] for k in sorted(node_hashes)}, separators=(",", ":"))
    return _sha256(ordered)


def _causal_sort(log: list) -> list:
    return sorted(log, key=lambda e: (e["sequence_id"], _STEP_ORDER.get(e["step"], 99)))


def replay_qapp_log(log: Optional[list] = None, silent: bool = False) -> dict:
    if log is None:
        log = _PROPAGATION_LOG
    sorted_log   = _causal_sort(log)
    node_hashes  = _replay_node_hashes(sorted_log)
    log_hash     = _compute_log_hash(sorted_log)
    consensus    = _compute_consensus_hash(node_hashes)

    def _inv_for(node_id: str) -> list:
        return sorted(e["invocation_id"] for e in sorted_log if e["to"] == node_id)

    coverage   = {nid: _inv_for(nid) for nid in _ALL_NODE_IDS}
    consistent = (coverage["Node_A"] == coverage["Node_B"] == coverage["Node_C"])

    if not silent:
        print(f"\n  [REPLAY] {len(sorted_log)} log entries — causal-sorted")
        for nid in _ALL_NODE_IDS:
            print(f"    {nid} hash    : {node_hashes[nid][:24]}...")
        print(f"    Consistent   : {'✅ YES' if consistent else '❌ NO'}")
        print(f"    Consensus    : {consensus[:24]}...")

    return {
        "log_entry_count": len(sorted_log),
        "node_hashes": node_hashes,
        "log_hash": log_hash,
        "consensus_hash": consensus,
        "consistent": consistent,
        "coverage": coverage,
    }
