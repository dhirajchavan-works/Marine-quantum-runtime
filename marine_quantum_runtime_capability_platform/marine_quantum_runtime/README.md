# marine_quantum_runtime

# marine_quantum_runtime

**Marine Intelligence System — Canonical Quantum Runtime Foundation**
**Author:** Dhiraj Chavan · BHIV Core · May 2026

> One repo. One lineage. One deterministic execution surface.

---

## Quick Start

```bash
# All modules — no pip installs, no arguments
python run/run_signal.py
python run/run_quantum_pipeline.py
python run/run_distributed_qapp.py
python run/run_operational_drift.py
```

**Requirements:** Python 3.8+ · No external dependencies · stdlib only

Exit code `0` = PASS. Exit code `1` = FAIL (reason printed before exit).

---

## What This Is

One canonical repository consolidating the full Marine Intelligence quantum pipeline build history (Tasks 1–9) into a deterministic, runtime-callable, quantum-hybrid-ready foundation.

```
Tasks 1–4  →  Signal generator + BHIV Core interface
Tasks 5–7  →  Execution integration + contract governance
Task 8     →  Quantum pipeline (HEA circuit + corrosion QApp)
Task 9     →  Distributed QApp propagation + replay
Current    →  Canonical convergence + invoke_runtime surface
```

---

## Repository Structure

```
marine_quantum_runtime/
├── README.md
├── requirements.txt
├── CHANGELOG.md
├── REVIEW_PACKET.md
├── SELF_TESTING_SHEET.md
├── .gitignore
│
├── run/
│   ├── run_signal.py              ← Tasks 1–4 entry point
│   ├── run_quantum_pipeline.py    ← Task 8 entry point
│   ├── run_distributed_qapp.py    ← Task 9 entry point
│   └── run_operational_drift.py   ← Monitoring entry point
│
├── src/
│   ├── invoke_runtime.py          ← SINGLE GATEWAY: invoke_runtime(module, payload)
│   │
│   ├── signal/                    ← Tasks 1–4: Signal generator
│   │   ├── signal_generator.py
│   │   ├── mapping_logic.py
│   │   └── validator.py
│   │
│   ├── quantum/                   ← Task 8: Quantum pipeline
│   │   ├── descriptors.py         ← QAppDescriptor + marine_corrosion_qapp
│   │   ├── schema.py
│   │   ├── algorithm.py
│   │   └── execution.py
│   │
│   ├── runtime/                   ← Task 9: Distributed propagation
│   │   ├── envelope.py
│   │   ├── nodes.py
│   │   ├── propagation.py
│   │   ├── replay.py
│   │   ├── observability.py
│   │   └── distributed_qapp_runner.py
│   │
│   ├── monitoring/                ← Monitoring layer
│   │   ├── operational_drift_monitor.py
│   │   ├── metrics.py
│   │   └── persistence.py
│   │
│   └── contracts/                 ← Contract governance
│       ├── qapp_contract.py       ← MARINE-INT-002 v1.0.0
│       ├── schema_contract.py
│       └── versioning.py
│
├── review_packets/
│   ├── task_1_review.md  →  task_current_review.md
│
├── testing/
│   ├── TESTING_PACKET.md          ← Vinayak: BHIV Universal Testing Protocol v2
│   ├── testing_evidence/          ← Screenshots go here
│   └── console_output.txt
│
├── docs/
│   ├── architecture.md
│   ├── execution_flow.md
│   ├── determinism_proof.md
│   ├── failure_matrix.md
│   └── handover.md
│
└── data/
    ├── sample_events.json
    └── sample_payloads.json
```

---

## invoke_runtime API

```python
import sys
sys.path.insert(0, ".")
from src.invoke_runtime import invoke_runtime

# Signal module
result = invoke_runtime("signal", {
    "node_id": "qnode_01", "energy_delta": 0.0001,
    "iterations": 120, "confidence": 0.92, "variance": 0.002
})

# Quantum pipeline
result = invoke_runtime("quantum_pipeline", {
    "salinity": 35.2, "temperature_celsius": 18.5,
    "pH": 7.8, "material_oxidation_potential": 0.44,
    "dissolved_oxygen_mgl": 6.5, "current_density_mAcm2": 0.12
})

# Distributed QApp
result = invoke_runtime("distributed_qapp", {})

# Operational monitor
result = invoke_runtime("operational_monitor", {"events": [signal_event]})
```

Every result has: `{ module, status, result, error }`.

---

## State Transitions (Signal Layer)

| Condition | State |
|---|---|
| `energy_delta > 0.01` | DIVERGED |
| `iterations > 500` | DIVERGED |
| `confidence < 0.70` | SUSPENDED |
| `variance > 0.01` | SUSPENDED |
| `confidence >= 0.85` AND `variance <= 0.005` AND `energy_delta <= 0.005` | CONVERGED |
| fallback | SUSPENDED |

---

## System-Wide Guarantees

- Same input → identical output, always
- No `datetime.now()` anywhere in core engine
- No randomness in signal, runtime, or contracts layers
- Fails loudly on bad input — no silent failures
- Append-only propagation log — never mutated after write
- Replay of any log → same hash, same state

---

## Integration Block

| Partner | Role |
|---|---|
| Kanishk | Distributed replay-safe execution and reconciliation |
| Raj | Invocation and routing architecture |
| Raj Prajapati | Enforcement and execution governance |
| Jaffer Ali | Distributed telemetry propagation systems |
| Ganesh | Deterministic runtime coordination systems |

---

## Testing

See `testing/TESTING_PACKET.md` for Vinayak's BHIV Universal Testing Protocol v2.
15 test cases across 5 domains. All pass on exit code 0.

---

## Known Limitations

See `docs/architecture.md` for complete list. Key points:
- Synthetic timestamp (`iterations × 60s` — not wall-clock)
- VQE pipeline is design-only (classical stub in `src/quantum/execution.py`)
- Single-process node propagation (not true distributed)

---

*Dhiraj Chavan · Marine Intelligence System · BHIV Core · May 2026*
