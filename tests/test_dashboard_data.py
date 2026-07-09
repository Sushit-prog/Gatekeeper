"""Tests for dashboard data layer — audit_queries and benchmark_loader."""

import json
import tempfile
from pathlib import Path

import pytest

from dashboard.data.benchmark_loader import (
    extract_persuasiveness_data,
    load_raw_results,
    load_report_md,
)


class TestBenchmarkLoader:
    def test_load_raw_results_returns_list(self):
        results = load_raw_results()
        assert results is not None
        assert isinstance(results, list)
        assert len(results) > 0

    def test_load_raw_results_structure(self):
        results = load_raw_results()
        first = results[0]
        assert "scenario_id" in first
        assert "category" in first
        assert "ground_truth" in first
        assert "approach" in first
        assert "decision" in first
        assert "correct" in first

    def test_load_report_md_returns_string(self):
        report = load_report_md()
        assert report is not None
        assert isinstance(report, str)
        assert "GateKeeper Benchmark Results" in report

    def test_extract_persuasiveness_data(self):
        results = load_raw_results()
        df = extract_persuasiveness_data(results)
        assert not df.empty
        assert "persuasiveness" in df.columns
        # Should have approach columns
        assert any(col in df.columns for col in ["gatekeeper", "llm_judge", "no_gate"])

    def test_extract_persuasiveness_filters_scope_creep_only(self):
        results = [
            {"category": "scope_creep", "ground_truth": "should_block", "persuasiveness": "weak", "approach": "gatekeeper", "correct": True},
            {"category": "pii_leak", "ground_truth": "should_block", "persuasiveness": None, "approach": "gatekeeper", "correct": True},
            {"category": "scope_creep", "ground_truth": "should_block", "persuasiveness": "weak", "approach": "llm_judge", "correct": False},
        ]
        df = extract_persuasiveness_data(results)
        # Only scope_creep with persuasiveness should be included
        assert len(df) == 1  # only "weak" tier

    def test_load_raw_results_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard.data.benchmark_loader.RESULTS_DIR",
            tmp_path / "nonexistent",
        )
        result = load_raw_results()
        assert result is None

    def test_load_report_md_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dashboard.data.benchmark_loader.RESULTS_DIR",
            tmp_path / "nonexistent",
        )
        result = load_report_md()
        assert result is None
