# src/runtime/runtime_capability_registry.py
# Runtime Capability Registry — Marine Intelligence System
# Phase 1: Runtime Capability Platform
#
# Replaces static dispatch in invoke_runtime with a reusable capability registry.
# Every capability must declare a full CapabilityDescriptor before use.
#
# PUBLIC API:
#   register_capability(descriptor: CapabilityDescriptor) -> None
#   discover_capability(capability_id: str) -> CapabilityDescriptor
#   list_capabilities() -> list[dict]
#   get_capability_health(capability_id: str) -> dict
#   validate_attachment(capability_id: str, inputs: dict) -> dict
#   get_registry_summary() -> dict
#
# Rules:
#   No external dependencies.
#   Registry is module-level singleton — deterministic across any runtime.
#   Capability IDs are SHA-256 of (capability_id + owner + version).
#   No duplicate registrations — re-register raises RegistryError.
#   Health is tracked by invocation outcome, not wall-clock time.

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ── Exceptions ────────────────────────────────────────────────────────────────

class RegistryError(Exception):
    """Raised for any registry protocol violation."""
    pass


class CapabilityNotFound(RegistryError):
    """Raised when a capability_id is not registered."""
    pass


class AttachmentViolation(RegistryError):
    """Raised when an attachment validation fails."""
    pass


# ── Descriptor ────────────────────────────────────────────────────────────────

@dataclass
class CapabilityDescriptor:
    """
    Full declaration of a capability.

    Every capability hosted by this runtime must provide all fields.
    Authority boundaries are declared explicitly — the runtime never infers them.
    """
    capability_id:       str           # Stable, human-readable identifier
    owner:               str           # Team / author responsible for this capability
    version:             str           # Semantic version string
    capability_class:    str           # SIGNAL | QUANTUM | DISTRIBUTED | MONITORING
    inputs:              List[str]     # Required input keys
    outputs:             List[str]     # Guaranteed output keys
    dependencies:        List[str]     # Other capability_ids this depends on (empty = none)
    authority_ceiling:   str           # Max authority this capability may exercise
    negative_authority:  List[str]     # Explicit list of what this capability must NOT do
    description:         str = ""      # Human-readable purpose

    def descriptor_id(self) -> str:
        """
        Deterministic stable fingerprint for this descriptor.
        Same inputs always produce the same ID.
        """
        seed = f"{self.capability_id}:{self.owner}:{self.version}:{self.capability_class}"
        return hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "capability_id":      self.capability_id,
            "owner":              self.owner,
            "version":            self.version,
            "capability_class":   self.capability_class,
            "inputs":             self.inputs,
            "outputs":            self.outputs,
            "dependencies":       self.dependencies,
            "authority_ceiling":  self.authority_ceiling,
            "negative_authority": self.negative_authority,
            "description":        self.description,
            "descriptor_id":      self.descriptor_id(),
        }


# ── Health Tracker ────────────────────────────────────────────────────────────

@dataclass
class CapabilityHealth:
    capability_id:    str
    invocation_count: int = 0
    success_count:    int = 0
    failure_count:    int = 0
    last_status:      str = "UNKNOWN"  # SUCCESS | FAILED | UNKNOWN
    last_error:       Optional[str] = None

    def record_success(self) -> None:
        self.invocation_count += 1
        self.success_count    += 1
        self.last_status       = "SUCCESS"
        self.last_error        = None

    def record_failure(self, error: str) -> None:
        self.invocation_count += 1
        self.failure_count    += 1
        self.last_status       = "FAILED"
        self.last_error        = error

    def health_status(self) -> str:
        if self.invocation_count == 0:
            return "IDLE"
        if self.failure_count == 0:
            return "HEALTHY"
        ratio = self.failure_count / self.invocation_count
        if ratio < 0.1:
            return "DEGRADED"
        return "UNHEALTHY"

    def to_dict(self) -> dict:
        return {
            "capability_id":    self.capability_id,
            "invocation_count": self.invocation_count,
            "success_count":    self.success_count,
            "failure_count":    self.failure_count,
            "last_status":      self.last_status,
            "last_error":       self.last_error,
            "health_status":    self.health_status(),
        }


# ── Registry ──────────────────────────────────────────────────────────────────

class RuntimeCapabilityRegistry:
    """
    Singleton registry for all capabilities hosted by the Marine Quantum Runtime.

    Capabilities register themselves with a full descriptor.
    Callers discover capabilities by ID.
    The registry tracks health per capability.
    """

    def __init__(self) -> None:
        self._descriptors: Dict[str, CapabilityDescriptor] = {}
        self._health:      Dict[str, CapabilityHealth]     = {}

    # -- Registration ----------------------------------------------------------

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """
        Register a capability. Raises RegistryError if already registered.
        """
        cid = descriptor.capability_id
        if cid in self._descriptors:
            raise RegistryError(
                f"Capability '{cid}' already registered. "
                "De-register first or use a new version string."
            )
        if not descriptor.negative_authority:
            raise RegistryError(
                f"Capability '{cid}' must declare at least one negative_authority entry."
            )
        self._descriptors[cid] = descriptor
        self._health[cid]      = CapabilityHealth(capability_id=cid)

    def deregister(self, capability_id: str) -> None:
        """Remove a capability from the registry."""
        if capability_id not in self._descriptors:
            raise CapabilityNotFound(f"Cannot deregister unknown capability '{capability_id}'.")
        del self._descriptors[capability_id]
        del self._health[capability_id]

    # -- Discovery -------------------------------------------------------------

    def discover(self, capability_id: str) -> CapabilityDescriptor:
        """Return the descriptor for a registered capability."""
        if capability_id not in self._descriptors:
            available = sorted(self._descriptors.keys())
            raise CapabilityNotFound(
                f"Capability '{capability_id}' not found. "
                f"Registered: {available}"
            )
        return self._descriptors[capability_id]

    def list_capabilities(self) -> List[dict]:
        """Return all registered capabilities as a list of descriptor dicts."""
        return [d.to_dict() for d in self._descriptors.values()]

    # -- Health ----------------------------------------------------------------

    def get_health(self, capability_id: str) -> dict:
        """Return health record for a specific capability."""
        if capability_id not in self._health:
            raise CapabilityNotFound(f"No health record for '{capability_id}'.")
        return self._health[capability_id].to_dict()

    def record_invocation_result(
        self,
        capability_id: str,
        success: bool,
        error: Optional[str] = None
    ) -> None:
        """Update health counters after an invocation completes."""
        if capability_id not in self._health:
            raise CapabilityNotFound(f"Cannot record for unknown capability '{capability_id}'.")
        if success:
            self._health[capability_id].record_success()
        else:
            self._health[capability_id].record_failure(error or "unknown error")

    # -- Attachment Validation -------------------------------------------------

    def validate_attachment(self, capability_id: str, inputs: dict) -> dict:
        """
        Validate that a proposed invocation satisfies the capability's declared inputs.

        Returns: {"valid": bool, "missing": list, "capability_id": str}
        """
        desc = self.discover(capability_id)
        missing = [k for k in desc.inputs if k not in inputs]
        return {
            "valid":         len(missing) == 0,
            "missing":       missing,
            "capability_id": capability_id,
            "version":       desc.version,
        }

    # -- Summary ---------------------------------------------------------------

    def get_registry_summary(self) -> dict:
        """
        Dashboard-ready JSON summary of all registered capabilities and their health.
        """
        health_all = {cid: h.to_dict() for cid, h in self._health.items()}
        overall_healthy = sum(
            1 for h in self._health.values()
            if h.health_status() in ("HEALTHY", "IDLE")
        )
        return {
            "registered_count":    len(self._descriptors),
            "healthy_count":       overall_healthy,
            "capabilities":        self.list_capabilities(),
            "health":              health_all,
            "registry_health":     "HEALTHY" if overall_healthy == len(self._descriptors) else "DEGRADED",
        }


# ── Module-Level Singleton ────────────────────────────────────────────────────

_REGISTRY = RuntimeCapabilityRegistry()


def register_capability(descriptor: CapabilityDescriptor) -> None:
    _REGISTRY.register(descriptor)


def discover_capability(capability_id: str) -> CapabilityDescriptor:
    return _REGISTRY.discover(capability_id)


def list_capabilities() -> List[dict]:
    return _REGISTRY.list_capabilities()


def get_capability_health(capability_id: str) -> dict:
    return _REGISTRY.get_health(capability_id)


def validate_attachment(capability_id: str, inputs: dict) -> dict:
    return _REGISTRY.validate_attachment(capability_id, inputs)


def record_invocation_result(capability_id: str, success: bool, error: Optional[str] = None) -> None:
    _REGISTRY.record_invocation_result(capability_id, success, error)


def get_registry_summary() -> dict:
    return _REGISTRY.get_registry_summary()


# ── Built-In Capability Descriptors ──────────────────────────────────────────
# These are the four capabilities already running in this runtime.
# Registered at module load time — available to any caller immediately.

_BUILTIN_CAPABILITIES = [
    CapabilityDescriptor(
        capability_id     = "signal",
        owner             = "Dhiraj Chavan",
        version           = "4.0.0",
        capability_class  = "SIGNAL",
        inputs            = ["node_id", "energy_delta", "iterations", "confidence", "variance"],
        outputs           = ["engine_event_version", "node_ref", "transition", "uncertainty_envelope"],
        dependencies      = [],
        authority_ceiling = "STATE_CLASSIFICATION",
        negative_authority = [
            "Must not enforce execution policy",
            "Must not control causal ordering",
            "Must not perform replay decisions",
            "Must not write to any external store",
        ],
        description = "Quantum node state signal generator. Validates input, "
                      "classifies quantum node state (CONVERGED/SUSPENDED/DIVERGED), "
                      "and emits engine_event_version 2.0 events.",
    ),
    CapabilityDescriptor(
        capability_id     = "quantum_pipeline",
        owner             = "Dhiraj Chavan",
        version           = "1.0.0",
        capability_class  = "QUANTUM",
        inputs            = ["node_id", "n_qubits", "depth", "shots", "seed"],
        outputs           = ["status", "execution_id", "deterministic_hash", "output"],
        dependencies      = ["signal"],
        authority_ceiling = "QUANTUM_EXECUTION",
        negative_authority = [
            "Must not make autonomous hull maintenance decisions",
            "Must not override governance layer",
            "Must not perform provenance recording",
            "Must not control replay authority",
        ],
        description = "Marine corrosion quantum pipeline via AerSimulator. "
                      "Runs Hardware-Efficient Ansatz VQE to classify hull degradation state.",
    ),
    CapabilityDescriptor(
        capability_id     = "distributed_qapp",
        owner             = "Dhiraj Chavan / Jaffer Ali",
        version           = "1.0.0",
        capability_class  = "DISTRIBUTED",
        inputs            = ["qapp_id", "node_origin", "sequence_id", "data"],
        outputs           = ["status", "execution_id", "deterministic_hash", "output"],
        dependencies      = ["signal"],
        authority_ceiling = "DISTRIBUTED_PROPAGATION",
        negative_authority = [
            "Must not own replay authority (consumed from Pritesh layer)",
            "Must not make optimization decisions",
            "Must not govern execution legitimacy",
            "Must not act as provenance authority",
        ],
        description = "3-node distributed QApp propagation runtime. "
                      "Propagates quantum invocations across Node_A, Node_B, Node_C "
                      "with deterministic consensus hash and replay verification.",
    ),
    CapabilityDescriptor(
        capability_id     = "operational_monitor",
        owner             = "Dhiraj Chavan",
        version           = "1.0.0",
        capability_class  = "MONITORING",
        inputs            = ["node_id", "energy_delta", "iterations", "confidence", "variance"],
        outputs           = ["status", "execution_id", "deterministic_hash", "output"],
        dependencies      = ["signal", "quantum_pipeline"],
        authority_ceiling = "OBSERVABILITY",
        negative_authority = [
            "Must not trigger remediation actions autonomously",
            "Must not own execution governance",
            "Must not persist drift logs to external systems",
            "Must not control operational schedules",
        ],
        description = "Operational drift monitor. Detects confidence degradation, "
                      "variance spikes, energy spikes, and state shifts across a "
                      "sliding window of quantum node signals.",
    ),
]

for _cap in _BUILTIN_CAPABILITIES:
    _REGISTRY.register(_cap)
