# src/signal/signal_generator.py
# Entry logic — calls mapping + builds engine-compatible event.
#
# PUBLIC API:
#   generate_state_event(input_payload: dict) -> dict
#   run(payload: dict) -> dict   ← runtime-callable interface
#
# Rules:
#   no file I/O · no global mutable state · no randomness
#   same input always returns identical output

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timezone, timedelta
from src.signal import mapping_logic
from src.signal import validator

_DEFAULT_SEQ = 1


def generate_state_event(input_payload: dict) -> dict:
    """
    Convert a raw quantum-node snapshot into a fully structured
    engine-compatible event (engine_event_version 2.0).
    """
    cleaned   = validator.validate_input(input_payload)
    seq       = int(input_payload.get("seq", _DEFAULT_SEQ))
    mapping   = mapping_logic.resolve_transition(cleaned, seq=seq)
    transition = mapping["transition"]
    sigma      = mapping["sigma"]

    anchor    = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ts_dt     = anchor + timedelta(seconds=cleaned["iterations"] * 60)
    timestamp = ts_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    event = {
        "engine_event_version": "2.0",
        "node_ref": cleaned["node_id"],
        "transition": {
            "prev":  transition["prev"],
            "next":  transition["next"],
            "cause": transition["cause"],
            "seq":   transition["seq"],
            "ts":    timestamp,
        },
        "uncertainty_envelope": {
            "confidence": cleaned["confidence"],
            "sigma":      round(sigma, 8),
        },
    }

    validator.validate_output(event)
    return event


def run(payload: dict) -> dict:
    """
    Runtime-callable entry point for the signal module.
    Wraps generate_state_event() with a structured result envelope.
    """
    try:
        event = generate_state_event(payload)
        return {
            "module":  "signal",
            "status":  "SUCCESS",
            "result":  event,
            "error":   None,
        }
    except validator.ValidationError as exc:
        return {
            "module":  "signal",
            "status":  "VALIDATION_ERROR",
            "result":  None,
            "error":   str(exc),
        }
    except Exception as exc:
        return {
            "module":  "signal",
            "status":  "ERROR",
            "result":  None,
            "error":   str(exc),
        }
