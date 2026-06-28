# src/monitoring/persistence.py
# In-memory event persistence — append-only log.
# No file I/O. No databases. Pure Python lists.

import hashlib
import json
from typing import List, Optional

_EVENT_LOG: List[dict] = []
_LOG_HASH: str = "0" * 64


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def append_event(event: dict) -> str:
    """Append an event to the log. Returns the new log hash."""
    global _LOG_HASH
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    entry_hash = _sha256(f"{_LOG_HASH}:{canonical}")
    _EVENT_LOG.append({**event, "_entry_hash": entry_hash})
    _LOG_HASH = entry_hash
    return entry_hash


def get_log() -> List[dict]:
    return list(_EVENT_LOG)


def get_log_hash() -> str:
    return _LOG_HASH


def get_event_count() -> int:
    return len(_EVENT_LOG)


def query_by_node(node_id: str) -> List[dict]:
    return [e for e in _EVENT_LOG if e.get("node_ref") == node_id or e.get("node_id") == node_id]


def query_by_state(state: str) -> List[dict]:
    return [e for e in _EVENT_LOG if e.get("transition", {}).get("next") == state]


def clear_log() -> None:
    global _LOG_HASH
    _EVENT_LOG.clear()
    _LOG_HASH = "0" * 64


def log_summary() -> dict:
    states = {}
    for e in _EVENT_LOG:
        s = e.get("transition", {}).get("next", "UNKNOWN")
        states[s] = states.get(s, 0) + 1
    return {
        "total_events":  len(_EVENT_LOG),
        "log_hash":      _LOG_HASH,
        "state_counts":  states,
    }
