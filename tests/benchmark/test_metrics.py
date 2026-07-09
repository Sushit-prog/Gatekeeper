"""Unit tests for benchmark metrics calculations."""

import pytest

from benchmark.metrics import compute_metrics
from benchmark.scenarios.schema import ScenarioResult


def _make_result(
    scenario_id: str,
    category: str,
    ground_truth: str,
    approach: str,
    decision: str,
    persuasiveness: str | None = None,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=scenario_id,
        category=category,
        ground_truth=ground_truth,
        persuasiveness=persuasiveness,
        approach=approach,
        decision=decision,
        correct=(decision == "BLOCK" and ground_truth == "should_block")
                or (decision == "ALLOW" and ground_truth == "should_allow"),
    )


class TestMetrics:
    def test_perfect_catch_rate(self):
        results = [
            _make_result("s1", "scope_creep", "should_block", "gatekeeper", "BLOCK"),
            _make_result("s2", "scope_creep", "should_block", "gatekeeper", "BLOCK"),
            _make_result("s3", "pii_leak", "should_block", "gatekeeper", "BLOCK"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.catch_rate == 100.0
        assert m.false_positive_rate == 0.0
        assert m.false_negative_rate == 0.0

    def test_zero_catch_rate(self):
        results = [
            _make_result("s1", "scope_creep", "should_block", "no_gate", "ALLOW"),
            _make_result("s2", "scope_creep", "should_block", "no_gate", "ALLOW"),
        ]
        m = compute_metrics(results, "no_gate")
        assert m.catch_rate == 0.0
        assert m.false_negative_rate == 100.0

    def test_false_positives(self):
        results = [
            _make_result("s1", "clean", "should_allow", "gatekeeper", "BLOCK"),
            _make_result("s2", "clean", "should_allow", "gatekeeper", "ALLOW"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.false_positive_rate == 50.0

    def test_mixed_results(self):
        results = [
            _make_result("s1", "scope_creep", "should_block", "gatekeeper", "BLOCK"),
            _make_result("s2", "scope_creep", "should_block", "gatekeeper", "ALLOW"),
            _make_result("s3", "clean", "should_allow", "gatekeeper", "ALLOW"),
            _make_result("s4", "clean", "should_allow", "gatekeeper", "BLOCK"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.catch_rate == 50.0  # 1 of 2 blocked correctly
        assert m.false_positive_rate == 50.0  # 1 of 2 allowed incorrectly blocked
        assert m.false_negative_rate == 50.0  # 1 of 2 blocked incorrectly allowed

    def test_category_breakdown(self):
        results = [
            _make_result("s1", "scope_creep", "should_block", "gatekeeper", "BLOCK"),
            _make_result("s2", "pii_leak", "should_block", "gatekeeper", "ALLOW"),
            _make_result("s3", "clean", "should_allow", "gatekeeper", "ALLOW"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.category_breakdown["scope_creep"].catch_rate == 100.0
        assert m.category_breakdown["pii_leak"].catch_rate == 0.0
        assert m.category_breakdown["clean"].false_positive_rate == 0.0

    def test_persuasiveness_breakdown(self):
        results = [
            _make_result("s1", "scope_creep", "should_block", "gatekeeper", "BLOCK", "weak"),
            _make_result("s2", "scope_creep", "should_block", "gatekeeper", "BLOCK", "moderate"),
            _make_result("s3", "scope_creep", "should_block", "gatekeeper", "BLOCK", "sophisticated"),
            _make_result("s4", "clean", "should_allow", "gatekeeper", "ALLOW"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.persuasiveness_breakdown is not None
        assert m.persuasiveness_breakdown["weak"] == 100.0
        assert m.persuasiveness_breakdown["moderate"] == 100.0
        assert m.persuasiveness_breakdown["sophisticated"] == 100.0

    def test_persuasiveness_llm_drops(self):
        """Simulate LLM judge getting worse with more persuasive reasoning."""
        results = [
            _make_result("s1", "scope_creep", "should_block", "llm_judge", "BLOCK", "weak"),
            _make_result("s2", "scope_creep", "should_block", "llm_judge", "BLOCK", "weak"),
            _make_result("s3", "scope_creep", "should_block", "llm_judge", "BLOCK", "moderate"),
            _make_result("s4", "scope_creep", "should_block", "llm_judge", "ALLOW", "moderate"),
            _make_result("s5", "scope_creep", "should_block", "llm_judge", "ALLOW", "sophisticated"),
            _make_result("s6", "scope_creep", "should_block", "llm_judge", "ALLOW", "sophisticated"),
        ]
        m = compute_metrics(results, "llm_judge")
        assert m.persuasiveness_breakdown is not None
        assert m.persuasiveness_breakdown["weak"] == 100.0
        assert m.persuasiveness_breakdown["moderate"] == 50.0
        assert m.persuasiveness_breakdown["sophisticated"] == 0.0

    def test_empty_results(self):
        results = []
        m = compute_metrics(results, "gatekeeper")
        assert m.total == 0
        assert m.catch_rate == 0.0

    def test_no_approach_match(self):
        results = [
            _make_result("s1", "clean", "should_allow", "no_gate", "ALLOW"),
        ]
        m = compute_metrics(results, "gatekeeper")
        assert m.total == 0
