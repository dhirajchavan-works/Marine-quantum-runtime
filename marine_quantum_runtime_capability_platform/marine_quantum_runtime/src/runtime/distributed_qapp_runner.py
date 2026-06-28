# src/runtime/distributed_qapp_runner.py
# Runtime-callable distributed QApp propagation module.
# run(payload) -> structured_result

import random
import sys

from src.runtime.envelope import QAppExecutionEnvelope
from src.runtime.nodes import ALL_NODES, reset_all_nodes
from src.runtime.propagation import (
    propagate_qapp_event, replay_qapp_log, get_propagation_log, clear_propagation_log
)


QAPP_ID          = "bhiv.corrosion.delta.v1"
NODE_ORIGIN      = "Node_A"
CONTRACT_VERSION = "qapp-v1.0"

DEFAULT_PAYLOADS = [
    {"node_id": "qnode_01", "energy_delta": 0.0001, "iterations": 120, "confidence": 0.92, "variance": 0.002},
    {"node_id": "qnode_02", "energy_delta": 0.003,  "iterations": 340, "confidence": 0.87, "variance": 0.004},
    {"node_id": "qnode_03", "energy_delta": 0.00005,"iterations": 55,  "confidence": 0.98, "variance": 0.0008},
]


def run(payload: dict) -> dict:
    """
    Runtime-callable entry point for the distributed_qapp module.

    Payload keys (all optional — defaults used if absent):
        payloads   : list of signal dicts to propagate
        prove_determinism : bool — run 5-replay + shuffle proof (default True)
        silent     : bool — suppress console output (default False)
    """
    payloads          = payload.get("payloads", DEFAULT_PAYLOADS)
    prove_determinism = payload.get("prove_determinism", True)
    silent            = payload.get("silent", False)

    # Reset nodes and log for clean run
    reset_all_nodes()
    clear_propagation_log()

    # Create envelopes
    envelopes = []
    for i, pl in enumerate(payloads, start=1):
        env = QAppExecutionEnvelope.create(
            qapp_id=QAPP_ID, node_origin=NODE_ORIGIN,
            payload=pl, sequence_id=i, contract_version=CONTRACT_VERSION,
        )
        envelopes.append(env)

    # Propagate
    for env in envelopes:
        propagate_qapp_event(env)

    log   = get_propagation_log()
    result = replay_qapp_log(log, silent=silent)

    # Determinism proof
    det_proof = None
    shuffle_proof = None
    if prove_determinism:
        hashes = []
        for _ in range(5):
            r = replay_qapp_log(list(log), silent=True)
            hashes.append(r["consensus_hash"])
        all_same = len(set(hashes)) == 1
        det_proof = {"deterministic": all_same, "runs": 5, "consensus_hashes": hashes}

        random.seed(42)
        shuffled = list(log)
        random.shuffle(shuffled)
        rs = replay_qapp_log(shuffled, silent=True)
        shuffle_proof = {
            "converges": rs["consensus_hash"] == result["consensus_hash"],
            "consensus_hash": rs["consensus_hash"],
        }

    return {
        "module":        "distributed_qapp",
        "status":        "SUCCESS",
        "result": {
            "envelopes_propagated": len(envelopes),
            "log_entries":          len(log),
            "consensus_hash":       result["consensus_hash"],
            "log_hash":             result["log_hash"],
            "consistent":           result["consistent"],
            "determinism_proof":    det_proof,
            "shuffle_proof":        shuffle_proof,
        },
        "error": None,
    }
