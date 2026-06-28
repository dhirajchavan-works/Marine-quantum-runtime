# src/monitoring/metrics.py
# Metrics collection for the marine quantum runtime.

import hashlib
import json
from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class RuntimeMetrics:
    total_signal_events:     int = 0
    total_converged:         int = 0
    total_suspended:         int = 0
    total_diverged:          int = 0
    total_validation_errors: int = 0
    total_drift_events:      int = 0
    total_propagations:      int = 0
    consensus_checks:        int = 0
    divergence_count:        int = 0

    @property
    def convergence_rate(self) -> float:
        total = self.total_converged + self.total_suspended + self.total_diverged
        return round(self.total_converged / total, 4) if total > 0 else 0.0

    @property
    def divergence_rate(self) -> float:
        return round(self.divergence_count / self.consensus_checks, 4) if self.consensus_checks > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "total_signal_events":     self.total_signal_events,
            "total_converged":         self.total_converged,
            "total_suspended":         self.total_suspended,
            "total_diverged":          self.total_diverged,
            "total_validation_errors": self.total_validation_errors,
            "total_drift_events":      self.total_drift_events,
            "total_propagations":      self.total_propagations,
            "consensus_checks":        self.consensus_checks,
            "divergence_count":        self.divergence_count,
            "convergence_rate":        self.convergence_rate,
            "divergence_rate":         self.divergence_rate,
        }


class MetricsCollector:
    def __init__(self):
        self._metrics = RuntimeMetrics()
        self._event_hashes: List[str] = []

    def record_signal_event(self, event: dict) -> None:
        self._metrics.total_signal_events += 1
        state = event.get("transition", {}).get("next", "")
        if state == "CONVERGED":  self._metrics.total_converged  += 1
        elif state == "SUSPENDED": self._metrics.total_suspended += 1
        elif state == "DIVERGED":  self._metrics.total_diverged  += 1
        h = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        self._event_hashes.append(h[:16])

    def record_validation_error(self) -> None:
        self._metrics.total_validation_errors += 1

    def record_drift_event(self) -> None:
        self._metrics.total_drift_events += 1

    def record_propagation(self) -> None:
        self._metrics.total_propagations += 1

    def record_consensus_check(self, diverged: bool = False) -> None:
        self._metrics.consensus_checks += 1
        if diverged:
            self._metrics.divergence_count += 1

    def snapshot(self) -> dict:
        return self._metrics.to_dict()

    def reset(self) -> None:
        self._metrics = RuntimeMetrics()
        self._event_hashes.clear()
