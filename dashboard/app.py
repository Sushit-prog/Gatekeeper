"""GateKeeper Dashboard — Streamlit entrypoint."""

import sys
from pathlib import Path

# Add project root to sys.path for imports
_project_root = str(Path(__file__).parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load .env before any module reads env vars
from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from dashboard.views import benchmark_view, overview, review_queue, violation_categories

st.set_page_config(
    page_title="GateKeeper Dashboard",
    page_icon="🛡️",
    layout="wide",
)

st.title("GateKeeper Dashboard")

# Sidebar navigation
page = st.sidebar.radio(
    "Navigation",
    ["Overview", "Violation Categories", "Review Queue", "Benchmark Results"],
)

if page == "Overview":
    overview.render()
elif page == "Violation Categories":
    violation_categories.render()
elif page == "Review Queue":
    review_queue.render()
elif page == "Benchmark Results":
    benchmark_view.render()
