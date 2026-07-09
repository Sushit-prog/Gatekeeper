"""Benchmark data loader — reads raw_results.json and report.md."""

import json
from pathlib import Path

import pandas as pd

RESULTS_DIR = Path(__file__).parent.parent.parent / "benchmark" / "results"


def load_raw_results() -> list[dict] | None:
    """Load benchmark raw results from JSON. Returns None if file doesn't exist."""
    raw_path = RESULTS_DIR / "raw_results.json"
    if not raw_path.exists():
        return None
    return json.loads(raw_path.read_text())


def load_report_md() -> str | None:
    """Load benchmark report markdown. Returns None if file doesn't exist."""
    report_path = RESULTS_DIR / "report.md"
    if not report_path.exists():
        return None
    return report_path.read_text()


def extract_persuasiveness_data(results: list[dict]) -> pd.DataFrame:
    """Pivot benchmark results into a DataFrame for the persuasiveness chart."""
    scope_results = [
        r for r in results
        if r.get("category") == "scope_creep" and r.get("persuasiveness")
    ]
    if not scope_results:
        return pd.DataFrame(columns=["persuasiveness", "approach", "catch_rate"])

    df = pd.DataFrame(scope_results)
    # Filter to should_block scenarios only
    df = df[df["ground_truth"] == "should_block"]

    # Compute catch rate per (persuasiveness, approach)
    grouped = df.groupby(["persuasiveness", "approach"]).agg(
        total=("correct", "count"),
        caught=("correct", "sum"),
    ).reset_index()
    grouped["catch_rate"] = (grouped["caught"] / grouped["total"] * 100).fillna(0)

    # Pivot for chart
    pivot = grouped.pivot(index="persuasiveness", columns="approach", values="catch_rate").fillna(0)

    # Ensure tier ordering
    tier_order = ["weak", "moderate", "sophisticated"]
    pivot = pivot.reindex([t for t in tier_order if t in pivot.index])

    return pivot.reset_index()
