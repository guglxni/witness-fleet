# Typed semantic decisions — contract and integration

**Proposed application interface, not implemented vendor code.** This file owns semantic family labels and status semantics. Provider-specific transport mappings must pass contract tests before live evaluation.

## 1. Roles and priority

1. **F-001 evidence_relation (first):** given one atomic claim and one exact source span, classify `supports`, `contradicts`, `irrelevant`, `insufficient`. `irrelevant` means unrelated; `insufficient` means relevant but not enough to establish either polarity. Annotators must use this rubric consistently.
2. **F-002 investigation_priority (second):** choose among graph-eligible `inspect_corridor`, `check_source_revision`, `request_operator_review`, `abstain`. Omit unavailable options and retain an explicit defer choice. The selected inspection still passes normal authorization/claim/physical checks.
3. **F-003 alias_candidate (deferred):** choose a supplied canonical ID or `none_of_these`; never auto-merge.
4. **F-004 episode_relevance (deferred):** rank verified compatible episodes; never discard mandatory events or override current preconditions.

Do not ask: “may the courier enter?”, “is this person authorized?”, “is the route physically safe?”, or “should this rule be ignored?”. These are deterministic governance/physics checks, not probabilistic semantic labels.

## 2. Provider-neutral request

```text
DecisionRequest
  request_id: opaque unique ID
  tenant_context_id: locally resolved tenant reference (omit actual tenant identifiers from remote text if unnecessary)
  family_id: F-001 | F-002 | F-003 | F-004
  question_schema_version, projection_version: explicit strings
  graph_version, policy_epoch: integers
  evidence_dependencies: [(id, revision_or_version)]
  input_hash: hash of canonical serialized projected input
  state: bounded sanitized string or structured payload
  questions: ordered list of {id, type, instructions, options_or_levels}
  deadline_monotonic: local-only deadline, not serialized as a provider argument
  allowed_provider, requested_model: configured allowlist values
```

Default proposed bounds for initial profiling: at most 8 candidate spans, 1 atomic claim per span question, 4 relation labels, 1 external fallback attempt, 5 seconds total advisory deadline. These are configuration defaults, **not** learned thresholds or service guarantees. Record truncation; a truncated mandatory governance result is an error. The graph's exhaustive policy query is not limited by this semantic budget.

State fields: atomic claim, exact quoted text, source/revision/span IDs, source status produced by deterministic code, relevant robot/task description only when needed. Never include private documents, hidden simulator truth, evaluation labels, arbitrary tools or secrets. Model input order is fixed by versioned policy in ordinary runs; controlled permutations are separate experiments.

## 3. Normalized result

```text
DecisionResult
  request_id, input_hash
  status: ok | abstain | refusal | unavailable | invalid | stale
  provider, requested_model, resolved_model_or_unknown
  answers: ordered [{question_id, type, labels, probabilities, selected_label,
                     expected_level_or_null, vendor_confidence_or_null}]
  model_version_evidence: response | configured | unknown
  latency_ms, attempt_count
  usage: {input_tokens_or_null, billed_units_or_null}
  error_class_or_null: sanitized enum, never raw payload
  calibration_version_or_none, decision_policy_version
```

Preserve the original response in an access-controlled synthetic-only experiment artifact if permitted; logs contain sanitized structured fields. Do not invent a resolved model when the provider only returns a deployment alias. `abstain` selected as a semantic label and local selective rejection are recorded separately via reason codes.

Validation rejects missing/extra questions, wrong type, wrong labels/order mapping, duplicate labels, nonfinite probabilities, out-of-range values, missing entries and totals outside the configured numerical tolerance. A small floating-point sum tolerance is permissible; silently renormalizing malformed/missing answers is not. Binary independent Nouls need not sum across questions; mutually exclusive Choice probabilities do. Reject a selected label inconsistent with the provider's documented semantics. Do not fabricate confidence/usage when unavailable.

## 4. Provider mappings verified from documentation

| Provider | Request/route | Adapter boundary |
|---|---|---|
| Microsoft-Decision-1 | Resource-host `POST /providers/microsoft/v1/systemone`; `model` is deployment alias; `state` plus named `questions`, each has `type`, `instructions`, `criteria` | `noul`, `choice`, `score`; score criteria ordered low to high; direct HTTPS avoids unrelated SDK version conflicts.[42] |
| TypeSafe Jev | `POST https://api.typesafe.ai/v1/systemone`; named questions and state | Pin stable `jev-1.13.0` for reproducible first comparison; 1.14 preview is a distinct model. SDK code license does not license hosted model/weights.[36][48] |
| OpenAI Decisions | `POST https://api.openai.com/v1/decisions`; `input` plus question array | `predicate`, `choice`, `score`, typed refusal; not the Microsoft endpoint. Account access is unverified; implement only after confirming entitlement.[41] |
| Structured generative baseline | Ordinary generator returns constrained label/JSON | Its written probability numbers are not native next-token or calibrated classifier probabilities. Label them appropriately.[75] |
| AnyJev/open-logit baseline | Isolated local inference over option-label logits | Actual restricted readout is different from generated probability text; count rotation/prefill cost, model and checkpoint license separately. Research-only until installed/evaluated. |

### Microsoft request example (synthetic; not executed)

```json
{
  "model": "ms-decision-1",
  "state": "CLAIM: A release is described for loaded couriers. QUOTED SOURCE: Inspection teams may enter Corridor C; loaded couriers remain prohibited.",
  "questions": {
    "relation": {
      "type": "choice",
      "instructions": "Classify only the semantic relation of the quoted text to the claim. Do not infer operational permission.",
      "criteria": {
        "supports": "Explicitly supports the whole atomic claim",
        "contradicts": "Explicitly conflicts with the atomic claim",
        "irrelevant": "Does not concern the claim",
        "insufficient": "Relevant but establishes neither support nor contradiction"
      }
    }
  }
}
```

This request is schema-shaped from Microsoft documentation, not a saved response or proof that the local deployment is callable. No expected probability values are fabricated. Read `answers.relation` with provider-specific validation; preserve distribution fields as documented at the exact integration version.[42]

## 5. Projection, ranking and gating

Graph retrieves exact candidate IDs and complete governing restrictions separately. Projection verifies source locators before external egress. Relation scores may create two lists—support and contradiction—with evidence ID tie-breaking; do not combine opposing polarity into a “truth score”. A semantic miss affects review usefulness only. The authorizer checks **all** active restrictions, permissions, releases and support integrity regardless of ranking.

After response: validate schema → check deadline → check snapshot/dependency/policy versions → apply frozen per-family calibration/acceptance policy → record Assessment → propose review order or eligible investigation. Recheck deterministically at dispatch even if advice was accepted.

## 6. Calibration and cascade

Start in `disabled` or `shadow`, not active. Modes: disabled (no model), shadow (record only), advisory (may reorder evidence/select eligible investigation), never `authorization`. Fit thresholds on calibration data, freeze and evaluate held-out families. No universal 0.5/0.9 threshold. The Jev benchmark finds materially different behavior for Choice, single Noul and multi-label Noul; it did not test this fleet or a relevance-ranking dataset.[84]

A stronger model is not an omniscient fallback. Compare deterministic, generator-only, System One and one-step selective cascade at matched evidence/action budgets. A timeout never becomes a default `supports`. Fallback can share context biases; measure full-pipeline mistakes, cost and review burden.

## 7. Cache and observability

Cache key includes tenant-local namespace, provider/model, question/projection versions, label order/rubric, input hash, source revision IDs, relevant fact versions and policy epoch. TTL never exceeds the earliest relevant evidence validity. No cross-tenant cache sharing. Do not cache transient errors as factual answers. Stable replay artifacts distinguish stored past outputs from fresh live inference.

Trace request IDs, stages, latency, retries, token usage, selected label, complete probabilities, selective outcome, graph dependencies and eventual human/episode result. Cost-unavailable is null, not zero. Total cost includes failed calls, fallback and retries.

## 8. Required adversarial cases

Answer-preserving plausible distractors, option rotations, negation, contradictory text, repeated source quotes in different revisions, missing correct option, forged approval, irrelevant long context, stale snapshot, wrong tenant, malformed distribution, response from unexpected model, provider refusal/outage and repeated calls for variance. JevOut's targeted-search findings motivate these tests but are not the ordinary error rate or a robot benchmark.[85]

See `math/SYSTEM_ONE.md` and `EVALUATION.md` for equations and denominators. Active advice remains disabled if held-out improvement is absent, rare high-cost errors worsen or the hard gate can be bypassed.

<!-- GENERATED CITATION REFERENCES -->

## Sources

[36] https://docs.typesafe.ai/models — Models - TypeSafe
[41] https://developers.openai.com/api/docs/guides/decisions — Decisions | OpenAI API
[42] https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-microsoft-decision — Deploy and use Microsoft-Decision-1 in Microsoft Foundry - Microsoft Foundry | Microsoft Learn
[48] https://docs.typesafe.ai/api.md — API reference
[75] https://github.com/typesafe-ai/system-one-adapter-python/tree/e1d4cc938204b22fc5a3c3aca7044072fe3f712d
[84] https://arxiv.org/html/2609.37647v1 — Evaluating and Benchmarking the System One Model Jev
[85] https://arxiv.org/html/2609.30243v2 — JevOut: Natural Context Can Flip Decision Models
