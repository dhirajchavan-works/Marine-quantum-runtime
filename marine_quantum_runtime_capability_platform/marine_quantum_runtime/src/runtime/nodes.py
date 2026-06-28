# src/runtime/nodes.py
# Distributed node objects for QApp propagation.

import hashlib


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def init_node_hash(node_id: str) -> str:
    return _sha256(f"INIT:{node_id}")


class DistributedNode:
    def __init__(self, node_id: str) -> None:
        self.node_id: str = node_id
        self.received_invocations: list = []
        self.replay_log: list = []
        self.execution_hash: str = init_node_hash(node_id)
        self.propagated_events: list = []

    def receive(self, envelope_dict: dict) -> None:
        self.received_invocations.append(dict(envelope_dict))
        self.replay_log.append({
            "event": "RECEIVED", "node": self.node_id,
            "invocation_id": envelope_dict["invocation_id"],
            "sequence_id": envelope_dict["sequence_id"],
            "trace_id": envelope_dict["trace_id"],
            "from_node": envelope_dict["node_origin"],
            "timestamp": envelope_dict["timestamp"],
        })
        self._update_hash(envelope_dict["invocation_id"])

    def record_propagation(self, envelope_dict: dict, to_node: str) -> None:
        self.propagated_events.append({
            "to_node": to_node,
            "invocation_id": envelope_dict["invocation_id"],
            "sequence_id": envelope_dict["sequence_id"],
            "trace_id": envelope_dict["trace_id"],
        })
        self.replay_log.append({
            "event": "PROPAGATED", "node": self.node_id,
            "invocation_id": envelope_dict["invocation_id"],
            "sequence_id": envelope_dict["sequence_id"],
            "to_node": to_node,
        })

    def _update_hash(self, invocation_id: str) -> None:
        self.execution_hash = _sha256(f"{self.execution_hash}:{invocation_id}")

    def reset(self) -> None:
        self.received_invocations = []
        self.replay_log = []
        self.execution_hash = init_node_hash(self.node_id)
        self.propagated_events = []

    def status(self) -> dict:
        return {
            "node_id": self.node_id,
            "received_count": len(self.received_invocations),
            "propagated_count": len(self.propagated_events),
            "execution_hash": self.execution_hash,
            "replay_log_count": len(self.replay_log),
        }

    def received_invocation_ids(self) -> list:
        return [e["invocation_id"] for e in self.received_invocations]

    def __repr__(self) -> str:
        return (f"DistributedNode({self.node_id!r}, "
                f"recv={len(self.received_invocations)}, "
                f"hash={self.execution_hash[:12]}...)")


Node_A = DistributedNode("Node_A")
Node_B = DistributedNode("Node_B")
Node_C = DistributedNode("Node_C")

ALL_NODES: dict = {"Node_A": Node_A, "Node_B": Node_B, "Node_C": Node_C}


def reset_all_nodes() -> None:
    for node in ALL_NODES.values():
        node.reset()
