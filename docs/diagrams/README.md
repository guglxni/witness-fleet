# Architecture and robotics diagrams

Three complementary, editable diagrams are checked in with real render workflows. Palette is shared: charcoal ink `#263238`, off-white canvas `#F6F5F1`, teal for graph/evidence `#137C75`, blue for sensing/robotics `#3976A8`, amber for operator gate `#D28A18`, red for HOLD `#B6443E`. Solid lines mean current/local flow; dashed boundary denotes unconfigured future deployment.

| Diagram | Editable source | Rendered preview | Best for |
|---|---|---|---|
| Local architecture + trust/deployment boundary | [`system-boundaries.drawio`](system-boundaries.drawio) | [`system-boundaries.png`](system-boundaries.png) · [`system-boundaries.svg`](system-boundaries.svg) | Component ownership, advisory-vs-authority boundary, current localhost and future-placeholder cloud boundary |
| Command and evidence sequence / unknown HOLD | [`command-evidence-sequence.mmd`](command-evidence-sequence.mmd) | [`command-evidence-sequence.svg`](command-evidence-sequence.svg) | Graph authorization, sequenced delivery, native receipt vs. verified outcome, unknown-state branch |
| SC-001 robotics top view | [`sc-001-robotics.excalidraw`](sc-001-robotics.excalidraw) | [`sc-001-robotics.svg`](sc-001-robotics.svg) · [`sc-001-robotics.png`](sc-001-robotics.png) | Corridor layout, relative actor footprints, sensor cone, obstacle/recovery bay/delivery and separate gate |

The architecture graph includes a dashed hosting boundary because a candidate Azure VM/network Bicep source exists at `deploy/azure/main.bicep`, while the separate hosting gateway is in progress in parent-owned work. Neither the source nor the boundary demonstrates a running cloud deployment or available endpoint. Robotics geometry is explanatory and not a simulator screenshot or hardware drawing.

## Re-render reproducibly

Requires Node.js and npm, plus `/Applications/draw.io.app/Contents/MacOS/draw.io` on macOS (the workflow can also discover a `drawio` executable). Mermaid CLI and Excalidraw SVG renderer package versions are exact-pinned in [`package.json`](../../scripts/diagrams/package.json) and `package-lock.json`.

```sh
npm --prefix scripts/diagrams ci
npm --prefix scripts/diagrams run render
```

`render` uses the installed draw.io desktop CLI to export its editable XML to PNG and SVG, `mmdc` from `@mermaid-js/mermaid-cli` to render Mermaid SVG, and a project-owned Node entrypoint calling Excalidraw's published `@excalidraw/utils` SVG export API to render the standard editable `.excalidraw` scene to SVG. The Excalidraw PNG preview is derived deterministically from its rendered SVG by the render script using Sharp, with the same editable scene as the source. This repository does **not** claim an official standalone Excalidraw CLI; this is an explicitly implemented renderer-library workflow.

To use one renderer independently:

```sh
# From repository root, after npm ci above
/Applications/draw.io.app/Contents/MacOS/draw.io -x docs/diagrams/system-boundaries.drawio -o docs/diagrams/system-boundaries.svg
npm --prefix scripts/diagrams exec -- mmdc -i ../../docs/diagrams/command-evidence-sequence.mmd -o ../../docs/diagrams/command-evidence-sequence.svg
npm --prefix scripts/diagrams run render:excalidraw
```

The convenience command discovers draw.io from common paths and normalizes output names. Rendering overwrites only previews in this folder; it does not edit root README, site content or deployment configuration.

## Validate

```sh
npm --prefix scripts/diagrams run check
```

The check parses editable file structures, verifies Markdown local link targets under the guide/diagram/owned render outputs, checks rendered image signatures/dimensions and confirms required semantic labels. It does not validate architecture behavior, simulate movement, or execute backend tests. When changing an interface or command lifecycle, update the source diagram and relevant guide and verify the rendered preview before committing.
