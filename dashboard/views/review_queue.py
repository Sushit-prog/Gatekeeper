"""Review Queue tab — human review of BLOCK decisions for false-positive sampling."""

import streamlit as st

from dashboard.data.audit_queries import get_random_blocks, get_review_stats, submit_review


def render() -> None:
    st.header("Review Queue")
    st.caption("Sample BLOCK decisions for human review. This computes a real false-positive rate from actual human review — distinct from the benchmark's synthetic FP rate.")

    # Stats
    stats = get_review_stats()
    col1, col2, col3 = st.columns(3)
    col1.metric("Reviewed", stats["total_reviewed"])
    col2.metric("False Positives", stats["false_positives"])
    col3.metric("Human-Reviewed FP%", f"{stats['fp_rate']:.1f}%")

    st.divider()

    # Sample size slider
    n = st.slider("Sample size", min_value=1, max_value=20, value=10)

    blocks = get_random_blocks(n=n)

    if not blocks:
        st.info("No BLOCK decisions to review — run some gate checks first.")
        return

    st.subheader(f"Reviewing {len(blocks)} BLOCK decisions")

    for i, block in enumerate(blocks):
        audit_id = block["id"]
        key_prefix = f"review_{audit_id}"

        with st.expander(f"{block['tool_name']} — {block['created_at'][:19] if block['created_at'] else 'N/A'}", expanded=False):
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

            # Review buttons
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Confirms violation", key=f"{key_prefix}_confirm"):
                    submit_review(audit_id, marked_fp=False)
                    st.success("Recorded: confirmed violation")
                    st.rerun()
            with col_b:
                if st.button("False positive", key=f"{key_prefix}_fp"):
                    submit_review(audit_id, marked_fp=True)
                    st.warning("Recorded: false positive")
                    st.rerun()
