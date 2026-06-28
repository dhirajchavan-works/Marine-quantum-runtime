# CHANGELOG.md
# Marine Intelligence Quantum Runtime — Change History

All significant changes are documented here in reverse chronological order.

---

## [Current] — Canonical Repo Convergence + Quantum Hybrid Runtime Foundation
**Date:** May 2026
**Author:** Dhiraj Chavan

### Added
- `src/invoke_runtime.py` — central runtime gateway (`invoke_runtime(module, payload)`)
- `src/quantum/descriptors.py` — `QAppDescriptor` + `marine_corrosion_qapp` registered
- `src/monitoring/operational_drift_monitor.py` — drift detection with `run(payload)` surface
- `src/monitoring/metrics.py` — `RuntimeMetrics` + `MetricsCollector`
- `src/monitoring/persistence.py` — append-only in-memory event log
- `src/contracts/qapp_contract.py` — MARINE-INT-002 v1.0.0 enforcement
- `src/contracts/schema_contract.py` — schema registry + validation
- `src/contracts/versioning.py` — `ContractVersion` + compatibility check
- `run/run_operational_drift.py` — monitoring entry point
- `docs/architecture.md` — what exists, what is simulated, boundaries, limitations
- `docs/execution_flow.md` — full signal → quantum → runtime → monitoring flow
- `docs/handover.md` — startup, FAQ, debugging, known weak spots
- `docs/determinism_proof.md` — formal proof per module
- `docs/failure_matrix.md` — all failure modes across all modules
- `testing/TESTING_PACKET.md` — BHIV Universal Testing Protocol v2 (15 test cases)
- `SELF_TESTING_SHEET.md` — completed self-testing evidence form
- `REVIEW_PACKET.md` — consolidated review document (current task)
- `CHANGELOG.md` — this file
- `data/sample_events.json` — sample signal events
- `data/sample_payloads.json` — sample input payloads for all modules

### Changed
- All source files relocated to prescribed canonical structure:
  - `signal_generator.py` → `src/signal/signal_generator.py`
  - `mapping_logic.py` → `src/signal/mapping_logic.py`
  - `validator.py` → `src/signal/validator.py`
  - `Qapp/envelope.py` → `src/runtime/envelope.py`
  - `Qapp/nodes.py` → `src/runtime/nodes.py`
  - `Qapp/propagation.py` → `src/runtime/propagation.py`
- All run scripts relocated to `run/`
- All review packets consolidated into `review_packets/`

### Architectural decisions
- `invoke_runtime()` is the sole external entry point — all modules reachable from one gateway
- Each module exposes `run(payload) -> structured_result` for runtime-callable discipline
- No direct cross-module imports — all routing through `invoke_runtime`
- `QAppDescriptor` registered on import — no manual registration needed by callers

---

## [Task 9] — Distributed QApp Propagation Layer
**Date:** May 2026

### Added
- `QAppExecutionEnvelope` — frozen dataclass, SHA-256 IDs, deterministic timestamp
- `DistributedNode` — receive/propagate/hash chain
- `Node_A`, `Node_B`, `Node_C` singletons
- `propagate_qapp_event()` — fan-out engine, append-only log
- `replay_qapp_log()` — causal-sort replay, consensus hash
- 4 failure simulators: delayed, duplicate, missing, out-of-order
- 8-phase run script with 5× determinism proof + 3× shuffle convergence

---

## [Task 8] — Quantum Pipeline (HEA + Corrosion QApp)
**Date:** April 2026

### Added
- `marine_corrosion_qapp/` — 6-qubit Hardware-Efficient Ansatz circuit
- `CorrosionInput` / `CorrosionOutput` Pydantic schemas
- `run_corrosion_qapp()` — AerSimulator execution with seeded determinism
- `validate_quantum_contract()` — 8 contract rules (R1–R8)
- `run_quantum_pipeline.py` — production pipeline entry point

---

## [Task 7] — Signal Purification + Core-Ready Contract
**Date:** April 2026

### Added
- `generate_signal()` — clean public API replacing `generate_state_event()`
- `trace_id` field — deterministic, derived from input fields
- `node_id` at top level — directly readable by Core
- `validate_contract(event) -> dict` — externally callable, returns pass/fail dict

### Removed
- `process_event_batch()` — moved to Core responsibility
- `final_hash` parallel chain — dual source of truth eliminated
- Execution policies (APPLIED/SKIPPED/LOGGED) — signal layer must not know execution semantics

---

## [Task 6] — Multi-Event Deterministic Execution
**Date:** May 2026

### Added
- `SequenceRegistry` — per-node monotonic counter, caller-owned
- `signal_adapter.py` — clean abstraction boundary signal → execution
- `process_event_batch()` — 3-event batch, order-invariant via seq-sort
- 5-run hash proof, Case A == Case B (order sensitivity)

---

## [Tasks 1–5] — Foundation (Signal Generator + Physical Engine Integration)
**Date:** April 2026

### Added
- `generate_state_event()` — deterministic quantum node state event
- Priority-ordered transition table (6 rules)
- `validate_input()` / `validate_output()` — full schema enforcement
- Kanishk's physical engine integration (`MultiZoneExecutor`)
- 4-phase execution proof (single run, failures, determinism, observable state)

---

*Dhiraj Chavan · Marine Intelligence System · May 2026*
