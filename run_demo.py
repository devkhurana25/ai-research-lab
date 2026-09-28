"""
End-to-end demo: run an investigation against the sample dataset and
write the report to disk.

Usage: python run_demo.py
"""
from core.orchestrator import run_investigation

if __name__ == "__main__":
    state = run_investigation(
        question="Why did revenue decrease, and what should the company do?",
        dataset_paths=["sample_data/sales.csv"],
    )

    with open("reports_out.md", "w") as f:
        f.write(state.report_markdown)

    print(f"\nInvestigation {state.id} finished with status {state.status.value}")
    print(f"Hypotheses: {len(state.hypotheses)}  Critic findings: {len(state.critic_findings)}")
    print("Report written to reports_out.md")
