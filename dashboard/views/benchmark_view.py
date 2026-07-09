"""Benchmark Results tab — renders M4 benchmark data with persuasiveness chart."""

import streamlit as st

from dashboard.data.benchmark_loader import (
    extract_persuasiveness_data,
    load_raw_results,
    load_report_md,
)


def render() -> None:
    st.header("Benchmark Results")

    raw_results = load_raw_results()
    report_md = load_report_md()

    if raw_results is None:
        st.warning("No benchmark results found. Run `python -m benchmark` first.")
        return

    # Persuasiveness chart — the centerpiece
    st.subheader("Scope Creep: Catch Rate by Reasoning Persuasiveness")
    st.caption("Does the LLM judge's catch rate drop as reasoning gets more sophisticated?")

    persp_df = extract_persuasiveness_data(raw_results)

    if persp_df.empty:
        st.info("No scope creep scenarios in benchmark results.")
    else:
        # Exclude no_gate (always 0%, not informative for this comparison)
        chart_cols = [c for c in persp_df.columns if c not in ["persuasiveness", "no_gate"]]
        chart_df = persp_df[["persuasiveness"] + chart_cols].set_index("persuasiveness")
        st.bar_chart(chart_df, stack=False)
        st.caption("Y-axis: catch rate % (0-100%). Grouped bars show LLM Judge vs GateKeeper.")

    st.divider()

    # Render report.md tables
    if report_md:
        st.subheader("Full Report")
        st.markdown(report_md)
    else:
        st.info("Report not found. Run `python -m benchmark` to generate it.")

    # Link to raw data
    st.divider()
    st.caption("Raw results: `benchmark/results/raw_results.json` — contains per-scenario, per-approach outcomes for auditability.")
