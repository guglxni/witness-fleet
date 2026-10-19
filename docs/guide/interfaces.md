# Interface guide

Witness Fleet separates reading a recorded run from operating a new simulation.
The public site, hosted demo and local console have different data and authority
boundaries. A polished visualization does not change those boundaries.

## Public site: inspect retained evidence

The [product site](https://witness-fleet.vercel.app) is a static publication.

- **Find a section:** use the section finder or Ctrl/Cmd-K, then navigate by keyboard.
  Escape closes the finder and returns focus. Reduced-motion preferences are honored.
- **Schema explorer:** select a node or directed relationship to inspect its exact
  semantics and pinned source. Copy or wrap the schema excerpt locally. The diagram
  describes application schema; it is deliberately labeled **not live**. It does not
  execute Cypher or retrieve a current database.
- **Recorded evidence:** choose a retained snapshot, search receipts or filter by
  robot. Expand a task to inspect and copy complete identifiers. Select a command
  to inspect the retained native outcome, ticks and available measured effects.
- **Comparison:** a later retained snapshot can be compared with the preceding one.
  There is no earlier captured snapshot for the first entry, so self-comparison is
  not evidence. Snapshot observation and command-completion ticks remain distinct.
- **Unknowns:** `unauthorized_executed: null` means unknown, never zero. The recorded
  configured demo-owner release was not human-authenticated. The downloadable
  sanitized receipt remains the evidence source; current source-code parity is not
  inferred from a previously captured source hash.

The only embedded film is the FalkorDB YouTube cut. Earlier films remain available
as separately preserved assets; none are replaced by the interface overhaul.

## Hosted demo: operate a bounded synthetic session

The [simulation workbench](https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo)
connects to its own HTTPS gateway, not the local operator API.

1. Start an isolated session. Starting and refreshing do not run mission tasks.
2. Inspect the current sampled state and available native scene.
3. Run authorized tasks. SC-001 pauses at the configured release gate.
4. Inspect the receipts and explicitly confirm the **synthetic** release if desired.
5. Run the remaining authorized tasks and inspect native delivery evidence.

The scene renderer consumes the authenticated `GET /demo/v1/scene` projection of
actual compiled MuJoCo geometry. It never invents a live floor when no usable sample
is available. Source coordinates use metres and +Z up; quaternions are wxyz.
Boxes use half-extents. Cylinders use `[radius, radius, half-height]`.
`model_sha256` identifies the source facility XML, not a compiled-model or safety
certification. The visual grid is an orientation aid rather than simulated geometry.

State and scene are separate reads, not one spanning graph/simulator transaction.
History is bounded browser-memory **sample history**, not a continuous trajectory,
physics replay or a durable journal viewer. Selecting history disables mutation;
return to live before an explicitly authorized action. Missing historical data is
unavailable rather than silently replaced with live values.

If a mutation's outcome is uncertain, further motion/release/replacement-session
controls remain locked. Read-only refresh does not clear that lock or grant retry
authority. Never use a visualization control as a way to reset simulation evidence.
The fallback view exposes only controls its renderer supports.

## Local console: inspect the local operator boundary

Build `web/` and launch the native local mission using the [README](../../README.md#run-the-native-local-mission).
The coordinate-space view uses actual controller-projected robot poses and explicitly
identified orientation aids; it is not the richer hosted native-scene endpoint.
Robot selection, task/event filters, receipt and source inspection remain local.
Existing authority, episode fencing, idempotency and HOLD behavior remain in the
runtime. The console must stay on loopback unless a separately reviewed exposure
path is explicitly configured.

## Verification boundary

Unit and browser tests cover interaction, overflow, readable identifiers, keyboard
navigation, reduced motion, accessible controls and fail-closed state handling.
Native mission tests exercise real isolated FalkorDB and MuJoCo. Mocked browser
fixtures are UI evidence only. See [verification status](../../BUILD_STATUS.md) for
recorded counts and [deployment evidence](deployment-evidence.md) for live read-back.
No emulated viewport check is represented as physical iOS/Android device testing.
