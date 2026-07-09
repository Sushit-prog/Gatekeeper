"""Pydantic models for benchmark scenarios."""

from typing import Any, Literal

from pydantic import BaseModel


class ToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any]


class SessionRecord(BaseModel):
    tool_name: str
    args: dict[str, Any]
    decision: str  # "ALLOW" or "BLOCK"
    tags: dict[str, Any] | None = None


class Scenario(BaseModel):
    id: str
    category: Literal["scope_creep", "rate_limit", "pii_leak", "clean"]
    session_history: list[SessionRecord]
    tool_call: ToolCall
    agent_reasoning: str
    ground_truth: Literal["should_block", "should_allow"]
    persuasiveness: Literal["weak", "moderate", "sophisticated"] | None = None
    description: str = ""


class ScenarioResult(BaseModel):
    scenario_id: str
    category: str
    ground_truth: str
    persuasiveness: str | None = None
    approach: Literal["no_gate", "llm_judge", "gatekeeper"]
    decision: Literal["ALLOW", "BLOCK"]
    correct: bool
    reasoning: str = ""


class CategoryMetric(BaseModel):
    total: int
    catch_rate: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None


class BenchmarkMetrics(BaseModel):
    approach: str
    total: int
    catch_rate: float  # % of should_block correctly blocked
    false_positive_rate: float  # % of should_allow incorrectly blocked
    false_negative_rate: float  # % of should_block incorrectly allowed
    category_breakdown: dict[str, CategoryMetric]
    persuasiveness_breakdown: dict[str, float] | None = None
