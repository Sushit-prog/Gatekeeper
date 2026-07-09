"""Benchmark runner — entry point for running the full benchmark."""

import argparse
import asyncio
import json
from pathlib import Path

from benchmark.report import save_report
from benchmark.runner import ALL_SCENARIOS, run_benchmark
from benchmark.scenarios.schema import ScenarioResult

RESULTS_DIR = Path(__file__).parent / "results"


def load_raw_results() -> list[ScenarioResult]:
    """Load cached raw results from JSON."""
    raw_path = RESULTS_DIR / "raw_results.json"
    if not raw_path.exists():
        raise FileNotFoundError(f"No cached results found at {raw_path}")
    data = json.loads(raw_path.read_text())
    return [ScenarioResult(**item) for item in data]


async def run_full_benchmark() -> None:
    """Run the full benchmark suite."""
    print(f"Running benchmark with {len(ALL_SCENARIOS)} scenarios...")
    print("Approaches: no_gate, llm_judge, gatekeeper")
    print()

    results = await run_benchmark()

    # Save raw results
    RESULTS_DIR.mkdir(exist_ok=True)
    raw_path = RESULTS_DIR / "raw_results.json"
    raw_path.write_text(json.dumps([r.model_dump() for r in results], indent=2))
    print(f"Raw results saved to {raw_path}")

    # Generate report
    report_path = save_report(results)
    print(f"Report saved to {report_path}")

    # Print summary
    _print_summary(results)


def regenerate_report() -> None:
    """Regenerate report from cached raw results without re-running benchmark."""
    print("Loading cached raw results...")
    results = load_raw_results()
    print(f"Loaded {len(results)} results from cache")

    report_path = save_report(results)
    print(f"Report saved to {report_path}")

    _print_summary(results)


def _print_summary(results: list[ScenarioResult]) -> None:
    """Print a summary of metrics for each approach."""
    from benchmark.metrics import compute_metrics
    for approach in ["no_gate", "llm_judge", "gatekeeper"]:
        m = compute_metrics(results, approach)
        print(f"\n{approach}:")
        print(f"  Catch rate: {m.catch_rate:.1f}%")
        print(f"  False positive rate: {m.false_positive_rate:.1f}%")
        print(f"  False negative rate: {m.false_negative_rate:.1f}%")


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()  # Load .env before any module reads env vars

    parser = argparse.ArgumentParser(description="GateKeeper Benchmark")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Regenerate report from cached raw_results.json without re-running benchmark",
    )
    args = parser.parse_args()

    if args.report_only:
        regenerate_report()
    else:
        asyncio.run(run_full_benchmark())


if __name__ == "__main__":
    main()
