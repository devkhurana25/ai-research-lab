"""
Evaluation harness (spec section 26).

A small benchmark of question+dataset pairs with known expected outcomes,
run against the real pipeline (not mocked) so this catches actual
regressions, not just "does it not crash".
"""
from __future__ import annotations
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator_langgraph import run_investigation
from core.state import InvestigationStatus


BENCHMARK = [
    {
        "name": "declining_revenue_detected",
        "question": "Why did revenue decrease, and what should the company do?",
        "datasets": ["sample_data/sales.csv"],
        "checks": [
            lambda s: s.status == InvestigationStatus.COMPLETED,
            lambda s: any("decreasing" in h.statement and h.status == "SUPPORTED" for h in s.hypotheses),
            lambda s: all(0 <= e.payload.get("p_value", 0) <= 1 for e in s.evidence if e.kind == "statistical_test"),
        ],
        "check_names": ["completes", "detects_real_decline", "p_values_are_valid_probabilities"],
    },
    {
        "name": "insufficient_evidence_not_fabricated",
        "question": "What caused the merger to fail?",  # no relevant signal in this dataset
        "datasets": ["sample_data/sales.csv"],
        "checks": [
            lambda s: s.status == InvestigationStatus.COMPLETED,
            # the system should NOT invent a merger-related hypothesis it has no data for
            lambda s: not any("merger" in h.statement.lower() for h in s.hypotheses),
        ],
        "check_names": ["completes", "does_not_fabricate_unrelated_hypothesis"],
    },
]


def run_benchmark() -> bool:
    all_passed = True
    for case in BENCHMARK:
        state = run_investigation(case["question"], case["datasets"])
        print(f"\n[{case['name']}]")
        for check, name in zip(case["checks"], case["check_names"]):
            try:
                ok = check(state)
            except Exception as e:
                ok = False
                print(f"  FAIL {name} (raised {e})")
                all_passed = False
                continue
            print(f"  {'PASS' if ok else 'FAIL'} {name}")
            all_passed = all_passed and ok
    return all_passed


if __name__ == "__main__":
    passed = run_benchmark()
    print(f"\n{'ALL CHECKS PASSED' if passed else 'SOME CHECKS FAILED'}")
    sys.exit(0 if passed else 1)
