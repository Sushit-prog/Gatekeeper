"""Report generator — produces a markdown report from benchmark results."""

from pathlib import Path

from benchmark.metrics import compute_metrics
from benchmark.scenarios.schema import ScenarioResult

RESULTS_DIR = Path(__file__).parent / "results"


def generate_report(results: list[ScenarioResult]) -> str:
    """Generate a markdown report from benchmark results."""
    approaches = ["no_gate", "llm_judge", "gatekeeper"]
    metrics = {a: compute_metrics(results, a) for a in approaches}

    lines = [
        "# GateKeeper Benchmark Results",
        "",
        "## Overview",
        "",
        "This benchmark compares three approaches to catching policy violations:",
        "1. **No gate** — baseline, everything executes",
        "2. **LLM judge** — Groq llama-3.3-70b evaluates each tool call",
        "3. **GateKeeper** — deterministic policy engine (Pydantic backend)",
        "",
        f"**Total scenarios**: {len(results) // len(approaches)}",
        "",
        "## Overall Results",
        "",
        "| Approach | Catch Rate | False Positive Rate | False Negative Rate |",
        "|----------|-----------|--------------------|--------------------|",
    ]

    for approach in approaches:
        m = metrics[approach]
        lines.append(
            f"| {approach} | {m.catch_rate:.1f}% | {m.false_positive_rate:.1f}% | {m.false_negative_rate:.1f}% |"
        )

    lines.append("")

    # Category breakdown
    lines.extend([
        "## Results by Category",
        "",
    ])

    categories = set()
    for m in metrics.values():
        categories.update(m.category_breakdown.keys())

    for cat in sorted(categories):
        lines.extend([
            f"### {cat.replace('_', ' ').title()}",
            "",
            "| Approach | Catch Rate | False Positive Rate | False Negative Rate |",
            "|----------|-----------|--------------------|--------------------|",
        ])
        for approach in approaches:
            m = metrics[approach]
            cb = m.category_breakdown.get(cat)
            catch = f"{cb.catch_rate:.1f}%" if cb and cb.catch_rate is not None else "N/A"
            fp = f"{cb.false_positive_rate:.1f}%" if cb and cb.false_positive_rate is not None else "N/A"
            fn = f"{cb.false_negative_rate:.1f}%" if cb and cb.false_negative_rate is not None else "N/A"
            lines.append(f"| {approach} | {catch} | {fp} | {fn} |")
        lines.append("")

    # Persuasiveness breakdown (scope_creep)
    lines.extend([
        "## Scope Creep: Catch Rate by Reasoning Persuasiveness",
        "",
        "This is the key result — does the LLM judge's catch rate drop as reasoning gets more persuasive?",
        "",
        "| Persuasiveness Tier | No Gate | LLM Judge | GateKeeper |",
        "|---------------------|---------|-----------|------------|",
    ])

    tiers = ["weak", "moderate", "sophisticated"]
    for tier in tiers:
        row = [f"**{tier.title()}**"]
        for approach in approaches:
            m = metrics[approach]
            if m.persuasiveness_breakdown and tier in m.persuasiveness_breakdown:
                row.append(f"{m.persuasiveness_breakdown[tier]:.1f}%")
            else:
                row.append("N/A")
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")

    # Interpretation
    gatekeeper_m = metrics["gatekeeper"]
    llm_m = metrics["llm_judge"]
    lines.extend([
        "## Interpretation",
        "",
        f"**GateKeeper** catches {gatekeeper_m.catch_rate:.1f}% of violations with {gatekeeper_m.false_positive_rate:.1f}% false positives.",
        f"**LLM Judge** catches {llm_m.catch_rate:.1f}% of violations with {llm_m.false_positive_rate:.1f}% false positives.",
        "",
    ])

    if gatekeeper_m.catch_rate > llm_m.catch_rate:
        diff = gatekeeper_m.catch_rate - llm_m.catch_rate
        lines.append(
            f"GateKeeper outperforms the LLM judge by {diff:.1f} percentage points on catch rate. "
            "This suggests the deterministic approach is more reliable at catching policy violations, "
            "particularly when agents provide sophisticated justifications."
        )
    elif gatekeeper_m.catch_rate == llm_m.catch_rate:
        lines.append(
            "Both approaches achieve the same catch rate. This may indicate the scenarios "
            "are not challenging enough to differentiate the approaches, or the LLM judge "
            "is performing adequately on this task."
        )
    else:
        diff = llm_m.catch_rate - gatekeeper_m.catch_rate
        lines.append(
            f"The LLM judge outperforms GateKeeper by {diff:.1f} percentage points. "
            "This is an unexpected result that warrants investigation — it may indicate "
            "the deterministic rules are missing some violation patterns that the LLM catches."
        )

    # Persuasiveness analysis
    if gatekeeper_m.persuasiveness_breakdown and llm_m.persuasiveness_breakdown:
        lines.extend(["", "### Persuasiveness Impact"])
        lines.append("")
        for tier in tiers:
            g_rate = gatekeeper_m.persuasiveness_breakdown.get(tier, 0)
            l_rate = llm_m.persuasiveness_breakdown.get(tier, 0)
            lines.append(
                f"- **{tier.title()}** reasoning: GateKeeper {g_rate:.1f}%, LLM Judge {l_rate:.1f}%"
            )
        lines.append("")

    return "\n".join(lines)


def save_report(results: list[ScenarioResult]) -> Path:
    """Generate and save the report."""
    RESULTS_DIR.mkdir(exist_ok=True)

    report_text = generate_report(results)
    report_path = RESULTS_DIR / "report.md"
    report_path.write_text(report_text)

    return report_path
