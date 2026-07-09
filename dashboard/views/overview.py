"""Overview tab — block rate over time, decision counts, engine backend."""

import streamlit as st

from dashboard.data.audit_queries import (
    get_block_rate_over_time,
    get_checks_last_24h,
    get_engine_backend,
    get_total_checks,
)


def render() -> None:
    st.header("Overview")

    total = get_total_checks()
    last_24h = get_checks_last_24h()
    backend = get_engine_backend()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Gate Checks", total)
    col2.metric("Last 24h", last_24h)
    col3.metric("Engine Backend", backend.upper())

    st.divider()

    if total == 0:
        st.info("No data yet — run some gate checks or the demo script first.")
        return

    st.subheader("Block Rate Over Time")
    hours = st.slider("Time window (hours)", min_value=1, max_value=168, value=24)
    df = get_block_rate_over_time(hours=hours)

    if df.empty:
        st.info("No data in the selected time window.")
    else:
        st.bar_chart(df, stack=True)
