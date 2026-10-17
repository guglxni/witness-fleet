# Integration contracts and ownership

Parent owns `src/witness_fleet/runtime/coordinator.py`, `src/witness_fleet/simulation/client.py`, simulator HTTP/service boundary, API and main test-runner metadata. These may be implemented only against separately accepted journal, protocol, graph and native world seams. Current work tests isolated prerequisites first; dependent implementations are not accepted until both module and composition reviews pass.

## Simulator service boundary

HTTP loopback process owns exactly one FacilityWorld and scheduler. It exposes only strict observations, named robot poses/skill receipts, dispatch-ingress and held reconciliation. Policy cannot import world/data/model. Configured synthetic scenarios select initial geometry only; no scenario-ID success table.

`GET /health`, `POST /episodes {episode_id,scenario,seed}`, `POST /events` (DispatchEvent), `GET /events/{id}`, `GET /commands/{id}`, `POST /advance {ticks}`, `GET /observations`, `POST /reconciliation/hold {higher_epoch,reason}`, `POST /reconciliation/cancel {original_event,proof_id}`.

Journal commits identity before receipt; check duplicates/hashes before preflight, apply only contiguous events at effective ticks. Ordered policy/fence/barrier events update installed identity. COMMAND can start skill only after validated matching receipt/journal claim. Admitted/skilled counts derived from journal, never UI. Unknown transport is not failed effect or retry permission. No arbitrary model trajectories/code.

Physics advances independently of network: one owner validates current held state/watchdog before batch step, collects sensor output and persists coherent checkpoint. Restore qpos/qvel/time/control/assets/config only after exact manifest validation; unclean progress beyond checkpoint remains UNKNOWN. Durable SQLite never grants policy.

## Coordinator interface

`ready()`, `state()`, `create_incident(scenario,seed,event_id)`, `step(ticks,event_id)`, `run(event_id)`, `hold(reason,event_id)`, `approve_release(release_id,expected_policy_epoch,event_id)`, `witness(decision_id)`, `source(revision_id)`, `command(command_id)`, `episode(episode_id)`.

Graph canonical writes/versioned tasks and source-governance chains precede effects. Domain VersionVector includes exact task and fact dependency versions; runtime MUST always pass expected_versions to ready_tasks. Reauthorize after claim/fence installation under current graph version. Atomic TransitionStore preparation stores the command, immutable ALLOW receipt and matching payload-bearing outbox event. Graph outage stops admission and triggers local hold. Outcome verification requires fresh sensor evidence; controller_done is insufficient. Restart bumps epoch/barrier and reconciles each earlier immutable event before new claims; no blind old-command resend.

API projects graph+sensors to existing `web/api-contract.ts` and SSE revisioned snapshots. Local maintenance owner comes from trusted server context, not JSON actor/approved. Retained exact release source span and originalrestriction scope bind approval. No synthetic enterprise IAM claim. Model defaults disabled and cannot authorize.
