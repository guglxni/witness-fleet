---
version: alpha
name: Witness Fleet
description: Evidence-first industrial operations console for a simulated robot team.
colors:
  primary: "#E6EDF5"
  secondary: "#A8B6C8"
  tertiary: "#63D9C6"
  neutral: "#101722"
  surface: "#192332"
  warning: "#FFD580"
  danger: "#FF9DA4"
  success: "#8EE3A7"
typography:
  h1:
    fontFamily: Inter
    fontSize: 2rem
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  body-md:
    fontFamily: Inter
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: Inter
    fontSize: 0.875rem
    fontWeight: 600
    lineHeight: 1.4
  code:
    fontFamily: JetBrains Mono
    fontSize: 0.8125rem
    lineHeight: 1.5
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "{spacing.md}"
  label-muted:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
  button-primary:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.sm}"
    padding: 12px
  button-primary-hover:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
  status-warning:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.warning}"
  status-danger:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.danger}"
  status-success:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.success}"
---

## Overview

An operational evidence console, not a sci-fi control room or generic chatbot. The primary question is “why did this robot act or stop?” Make the answer legible before showing a complex graph. Working title only; no brand/trademark clearance implied.

This file specifies future UI tokens and behavior. No screenshot or working interface is delivered by this document. DESIGN.md CLI validation checks tokens/contrast, not application accessibility.

## Colors

Dark neutral background reduces competition with robot/graph state. Teal is the primary actionable accent. Amber is pending/unknown; coral is denied/failure; green is verified outcome. Every status also has an icon and text: color alone never communicates permission.

Do not use green for controller acceptance. “Accepted”, “running”, “controller done”, “outcome verified” and “policy permitted” are different states. An amber unresolved state is not a low-confidence success.

## Typography

Inter with system sans fallback for interface prose; JetBrains Mono with system monospace fallback for IDs, query templates and exact quotations. Fonts are optional local assets; check licenses before bundling, no external font request required for judge setup. Main reason text 16–20 px; metadata no smaller than 13 px. Never uppercase long explanations.

## Layout

Desktop: top status strip (simulation mode, graph/model health, policy epoch, pause/hold); center-left facility scene; right decision/witness panel; bottom timeline and robot/task queue. At narrow widths stack scene → current reason → evidence → timeline. Graph visualization is a focused witness, not a full tangled network.

Recommended screens:
1. **Incident console:** three robot cards, active task, current reason, next permitted step.
2. **Decision inspector:** proposed action, passed/failed/unknown predicates, query ID/version, selected/rejected robots.
3. **Company witness:** branched source/revision/span/decision/owner/restriction graph, exact source reader and currentness/scope badges.
4. **Recovery console:** command ID, last receipt, unknown state, current fence/epoch, reconcile/hold controls.
5. **Evaluation:** matched variant metrics with raw denominators, model disabled/shadow/advisory labels and links to traces.

## Elevation & Depth

Use borders and restrained panel separation, not glowing neon shadows. Selected graph path has a clear solid outline; predicted effects use dashed styling and a “hypothesis” label. Stale edges remain visible with an expiry label rather than disappearing.

## Shapes

8 px panels, 4 px controls; minimum 44 px touch targets where practical. Robot roles have both distinct shape and label (Scout, Recovery, Courier). Arrowheads show stored edge direction; clicking reveals relationship type. Do not render a fictional linear evidence chain.

## Components

- **Gate status:** separate Physical / Policy / Claim / Freshness rows; one explicit reason code with plain explanation.
- **Evidence card:** exact quoted span, source revision, actor/owner, effective interval, expiry and link to source. Quote text comes from retained bytes, not generated prose.
- **Approval panel:** show restriction being lifted, exact scope, approving role and policy epoch. Rejected/stale approval is a first-class state. No dangerous default-selected confirmation.
- **Model panel:** show provider/model and shadow/advisory mode, complete label distribution if real data exists, abstain/error status and input evidence IDs. In model-free mode show “Disabled — deterministic baseline”; never synthetic scores.
- **Timeline:** intent, claim, dispatch, ack, observation, verification and release as distinct event types; expandable IDs/version details.
- **Graph witness:** focus only current decision paths, retain contradictory/missing-provenance indicators, allow keyboard traversal via adjacent table view.
- **Connection banner:** stale SSE/graph state prominently disables new affected actions; cached UI is labeled stale.

## Do's and Don'ts

Do use keyboard focus, semantic buttons/headings, ARIA live polite event summaries, table alternatives for graphs, reduced-motion mode and visible errors. Respect browser zoom and high contrast. Avoid automatic camera spinning, critical flashing or graphs requiring pointer-only interaction.

Do show the hero statement: **“Physically clear. Loaded courier still restricted.”** Then identify exact source/owner/release conditions. Do not replace it with an unexplained confidence gauge.

Do label simulation, sensor mode, oracle overlays and replay/live inference. Do not imply physical certification, visual perception or model benefit without corresponding tests.
