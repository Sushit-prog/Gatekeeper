"""Violation Categories tab — breakdown by rule_id, recent BLOCK decisions."""

import streamlit as st

from dashboard.data.audit_queries import get_block_count_by_rule, get_recent_blocks


def render() -> None:
    st.header("Violation Categories")

    df = get_block_count_by_rule()

    if df.empty:
        st.info("No BLOCK decisions yet — nothing to show.")
        return

    st.subheader("Blocks by Rule")
    st.bar_chart(df.set_index("rule_id")["count"])

    st.divider()

    st.subheader("Recent BLOCK Decisions")
    blocks = get_recent_blocks(limit=20)

    if not blocks:
        st.info("No recent BLOCK decisions.")
        return

    for block in blocks:
        with st.expander(f"{block['tool_name']} — {block['created_at'][:19] if block['created_at'] else 'N/A'}"):
            st.write(f"**Tool**: `{block['tool_name']}`")
            st.write(f"**Args**: `{block['args']}`")

            matched_rules = block.get("matched_rules", [])
            if isinstance(matched_rules, str):
                import json
                matched_rules = json.loads(matched_rules)

            failed_rules = [r for r in matched_rules if isinstance(r, dict) and not r.get("passed", True)]
            if failed_rules:
                for rule in failed_rules:
                    st.write(f"**Rule**: `{rule.get('rule_id', '?')}` — {rule.get('reason', 'No reason')}")
            else:
                st.write("**Rule**: (no failed rules in record)")
