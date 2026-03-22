"""
Seed demo data for dashboard demonstration.
Runs the Phase 1 pipeline against fixture CSVs and outputs a demo Excel report.

Usage:
    python scripts/seed_demo_data.py --reset
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import Base, engine
from config.logging import configure_logging

configure_logging()


def reset_db():
    print("Resetting database...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    print("Database reset complete.")


def main(reset: bool = False):
    if reset:
        reset_db()
    else:
        Base.metadata.create_all(engine)

    # Seed rules
    from scripts.seed_rules import seed_rules
    print("\nSeeding rules...")
    seed_rules()

    # Run Phase 1 against fixture CSVs
    from scripts.run_phase1 import run_phase1
    fixture_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    eft_file = fixture_dir / "sample_eft.csv"
    reported_file = fixture_dir / "sample_reported.csv"

    print(f"\nRunning Phase 1 pipeline against fixtures...")
    print(f"  EFT:      {eft_file}")
    print(f"  Reported: {reported_file}")

    summary = run_phase1(str(eft_file), str(reported_file), "demo_operator")

    # Copy report to demo location
    import shutil
    exports_dir = Path("data/exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    src_report = Path(summary["report_path"])
    demo_report = exports_dir / "demo_missed_transactions.xlsx"
    shutil.copy2(src_report, demo_report)
    print(f"\nDemo report saved to: {demo_report}")

    print("\n=== Demo Data Summary ===")
    print(f"Run ID: {summary['run_id']}")
    print(f"EFT transactions: {summary['eft_rows']}")
    print(f"Reported transactions: {summary['reported_rows']}")
    print(f"Matched: {summary['reconciliation']['matched']}")
    print(f"Missed: {summary['reconciliation']['missed']}")
    print(f"Phantom: {summary['reconciliation']['phantom']}")
    print(f"Breaches: {summary['reconciliation']['breaches']}")
    print(f"Rule findings: {summary['rules']['findings']}")
    print(f"\nDashboard demo data ready!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo data for dashboard")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    args = parser.parse_args()
    main(args.reset)
