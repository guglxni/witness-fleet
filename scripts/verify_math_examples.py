#!/usr/bin/env python3
"""Recompute the explicitly synthetic worked examples. No model/sim calls."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    d = json.loads((ROOT / 'evidence/math-worked-examples.json').read_text())
    gap = d['clearance']
    lower = gap['gap_m'] - gap['uncertainty_m']
    required = gap['courier_width_m'] + 2 * gap['margin_each_side_m']
    assert math.isclose(lower, gap['lower_gap_m'])
    assert math.isclose(required, gap['required_width_m'])
    assert (lower >= required) == gap['passes']
    brier = d['brier_example']
    assert len(brier['probabilities']) == len(brier['labels']) > 0
    score = sum((p-y)**2 for p,y in zip(brier['probabilities'],brier['labels'], strict=True)) / len(brier['labels'])
    assert math.isclose(score, brier['binary_brier'])
    voc = d['value_of_computation']
    value = (voc['q_fallback']-voc['q_fast'])*voc['wrong_label_loss']-voc['extra_compute_cost']-voc['latency_cost']
    assert math.isclose(value, voc['net_value'])
    ci = d['zero_failure_iid_upper_example']
    bound = 1-(1-ci['confidence'])**(1/ci['n'])
    assert math.isclose(bound, ci['one_sided_upper'])
    print(json.dumps({'status':'passed','scope':'four synthetic arithmetic examples only; not application performance','clearance_passes':gap['passes'],'binary_brier':score,'net_value':value,'zero_failure_upper':bound}, indent=2))


if __name__ == '__main__':
    main()
