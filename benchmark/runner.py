"""Benchmark runner — executes all scenarios against all 3 approaches.

Results are cached by scenario ID to avoid re-running LLM calls on re-runs.
"""

import asyncio
import json
import os
from pathlib import Path

from benchmark.judges import gatekeeper_judge, llm_judge
from benchmark.scenarios.clean_cases import CLEAN_CASES
from benchmark.scenarios.pii_leak_cases import PII_LEAK_CASES
from benchmark.scenarios.rate_limit_cases import RATE_LIMIT_CASES
from benchmark.scenarios.schema import Scenario, ScenarioResult
from benchmark.scenarios.scope_creep_cases import SCOPE_CREEP_CASES

ALL_SCENARIOS: list[Scenario] = (
    SCOPE_CREEP_CASES + RATE_LIMIT_CASES + PII_LEAK_CASES + CLEAN_CASES
)

RESULTS_DIR = Path(__file__).parent / "results"
CACHE_FILE = RESULTS_DIR / "cache.json"


def _load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


async def _no_gate_judge(scenario: Scenario) -> dict:
    """No gate — everything is allowed."""
    return {"decision": "allow", "reason": "No gate configured"}


async def _llm_judge(scenario: Scenario) -> dict:
    """LLM judge via Groq."""
    history = [r.model_dump() for r in scenario.session_history]
    return await llm_judge.judge(
        tool_name=scenario.tool_call.tool_name,
        args=scenario.tool_call.args,
        agent_reasoning=scenario.agent_reasoning,
        session_history=history,
    )


async def _gatekeeper_judge(scenario: Scenario) -> dict:
    """GateKeeper API judge."""
    return await gatekeeper_judge.judge(
        tool_name=scenario.tool_call.tool_name,
        args=scenario.tool_call.args,
        agent_reasoning=scenario.agent_reasoning,
        session_history=[r.model_dump() for r in scenario.session_history],
        session_id=f"benchmark-{scenario.id}",
    )


JUDGES = {
    "no_gate": _no_gate_judge,
    "llm_judge": _llm_judge,
    "gatekeeper": _gatekeeper_judge,
}


async def run_scenario(
    scenario: Scenario,
    approach: str,
    cache: dict,
) -> ScenarioResult:
    """Run a single scenario against an approach, using cache if available."""
    cache_key = f"{scenario.id}:{approach}"

    if cache_key in cache:
        cached = cache[cache_key]
        return ScenarioResult(
            scenario_id=scenario.id,
            category=scenario.category,
            ground_truth=scenario.ground_truth,
            persuasiveness=scenario.persuasiveness,
            approach=approach,
            decision=cached["decision"],
            correct=cached["correct"],
            reasoning=cached.get("reasoning", ""),
        )

    judge_fn = JUDGES[approach]
    result = await judge_fn(scenario)

    decision = result["decision"].upper()
    correct = (
        (decision == "BLOCK" and scenario.ground_truth == "should_block")
        or (decision == "ALLOW" and scenario.ground_truth == "should_allow")
    )

    scenario_result = ScenarioResult(
        scenario_id=scenario.id,
        category=scenario.category,
        ground_truth=scenario.ground_truth,
        persuasiveness=scenario.persuasiveness,
        approach=approach,
        decision=decision,
        correct=correct,
        reasoning=result.get("reason", ""),
    )

    cache[cache_key] = {
        "decision": decision,
        "correct": correct,
        "reasoning": result.get("reason", ""),
    }

    return scenario_result


async def run_benchmark(
    scenarios: list[Scenario] | None = None,
    approaches: list[str] | None = None,
) -> list[ScenarioResult]:
    """Run the full benchmark suite."""
    if scenarios is None:
        scenarios = ALL_SCENARIOS
    if approaches is None:
        approaches = ["no_gate", "llm_judge", "gatekeeper"]

    cache = _load_cache()
    results: list[ScenarioResult] = []

    for approach in approaches:
        for scenario in scenarios:
            result = await run_scenario(scenario, approach, cache)
            results.append(result)
            _save_cache(cache)

    return results
