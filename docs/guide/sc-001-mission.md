# SC-001: inspect, recover, release, deliver

SC-001 is the opt-in local showcase of the graph-authorized native fleet path. It has a strict seven-task DAG with an explicit owner gate between recovery evidence and courier access. The manifest and ordered task plan are declared in [`runtime/bootstrap.py`](../../src/witness_fleet/runtime/bootstrap.py); the integration assertion is [`tests/e2e/test_integrated_fleet.py`](../../tests/e2e/test_integrated_fleet.py).

![Native mission top view and actor/sensor footprints](../diagrams/sc-001-robotics.svg)

The source scene is editable at [`sc-001-robotics.excalidraw`](../diagrams/sc-001-robotics.excalidraw). Geometry and footprint labels reflect [`facility.xml`](../../services/simulator/assets/facility.xml) and [`world.py`](../../services/simulator/world.py); the sketch is an explanatory top view, not a camera capture or to-scale screenshot.

## Seven tasks and gate

| Order | Task key | Robot | Action | What it establishes |
|---:|---|---|---|---|
| 1 | `scout-inspect` | scout | inspect | Initial scoped sensor sample; an acknowledgment alone is not clearance |
| 2 | `recovery-recover` | recovery | recover | Bounded physical contact/displacement attempt; must still be verified |
| 3 | `scout-park` | scout | travel | Park at the declared safe observation pose |
| 4 | `scout-verify` | scout | verify | Fresh post-recovery observation; now mission pauses for owner release |
| **Gate** | `courier-release` | configured local maintenance-owner principal | explicit approve | Checks active release identity and expected policy epoch, captures fresh courier-scoped proof, commits approval/release provenance |
| 5 | `courier-approach` | courier | travel | Only after named release, current authorization and fresh clearance |
| 6 | `courier-verify` | courier | verify | Courier-specific verification (scout clearance is not inherited) |
| 7 | `courier-deliver` | courier | deliver | Arrival plus scoped physical postconditions; final task/outcome becomes verified |

The gate occurs after the **first four** task rows above; the courier's three tasks are not admitted before it. This is a local synthetic demo-owner flow, not production user authentication. The owner identity is loaded from the retained synthetic manifest and the backend ignores caller-supplied actor/approval fields ([`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py), [`runtime/approval.py`](../../src/witness_fleet/runtime/approval.py), [`runtime/approval_writer.py`](../../src/witness_fleet/runtime/approval_writer.py)).

## Native evidence and successful integration assertion

The e2e contract checks exactly seven unique task IDs and seven command IDs, all task and command states verified in the final state, an initially staged release and no delivery command before explicit approval, native command evidence, and a measured payload-in-delivery-zone postcondition after delivery. These are **test assertions**, not a claim that this documentation turn ran the integrated suite or that every environment is ready. See the complete test at [`tests/e2e/test_integrated_fleet.py`](../../tests/e2e/test_integrated_fleet.py).

Recovery verification is more than a controller `done`: [`runtime/effects.py`](../../src/witness_fleet/runtime/effects.py) binds positive measured displacement/contact to current visible courier-fit evidence. Observations preserve the actual observer identity. Owner release verification records two specific predicates, `recovery_verified` and `courier_fit`, in the original approval proof ([`graph/verification.py`](../../src/witness_fleet/graph/verification.py)). Courier delivery remains blocked until this release path is valid and its own physical requirements are met.

## Replay and HOLD

A mission event ID and canonical intent are durably recorded before native work. Same ID/same intent returns the retained result; same ID/different intent rejects. An unresolved request is not replayed: it puts execution into an explicit unknown/HOLD path ([`runtime/mission.py`](../../src/witness_fleet/runtime/mission.py)). At the lower simulator boundary, ordered event identity and journal receipts preserve exactly what was applied ([`services/simulator/journal.py`](../../services/simulator/journal.py)).

Recovery, release, and delivery are separate facts. A successful HTTP response, simulator `CONTROLLER_DONE`, status projection, persisted `Release`, or graph `DeliveryReceipt` alone must not be substituted for `OUTCOME_VERIFIED`. See the [sequence diagram](../diagrams/command-evidence-sequence.svg) and [evidence guide](evidence.md).

## What this scenario does not show

SC-001 is not a general benchmark across the scenario catalog; does not evaluate an LLM; does not certify map accuracy, visual perception, wheel odometry, stopping distance, contact realism or sim-to-real transfer; and does not execute a physical robot. Other world classes exist in [`world.py`](../../services/simulator/world.py), but one completed SC-001 mission does not prove them. Do not treat a rendered replay or static diagram as test evidence.
