# GateKeeper

**A deterministic policy gate for LLM tool-calling agents — it catches sophisticated policy violations that LLM-judge verifiers miss, because it never reads the reasoning that fools them.**

---

## The Problem

Tool-using LLM agents can reason their way to a policy-compliant-sounding justification while the actual tool call they make violates policy — citing a plausible incident ticket, a governance exception, or a regulatory article to justify an action that shouldn't happen. This is a silent failure mode: the agent's stated reasoning looks fine, so an LLM-judge verifier reading that same reasoning is vulnerable to the exact same persuasion. GateKeeper is built on the idea that the fix isn't a smarter judge — it's a gate that structurally cannot see the reasoning at all, and instead evaluates only the tool name, its arguments, and session history.

This project implements that gate across five milestones, and benchmarks it directly against an LLM-judge baseline to show where the difference actually shows up.

## The Headline Result

The clearest evidence is in the scope-creep scenarios, broken out by how persuasive the agent's justification is:

| Persuasiveness Tier | LLM-Judge Catch Rate | GateKeeper Catch Rate |
|---|---|---|
| Weak | 100% | 100% |
| Moderate | 100% | 100% |
| Sophisticated | 12.5% | 100% |

When the justification is weak or moderate, the LLM judge does fine. Once the justification gets sophisticated — citing GDPR articles, incident playbooks, governance tickets — the LLM judge's catch rate collapses to 12.5%, while GateKeeper's stays at 100%, because it never reads the justification text in the first place. That's the core result this project is built around: judge accuracy is a function of how good the excuse is; a rule-based gate's accuracy isn't.

Overall, across all 50 benchmark scenarios: `no_gate` catches 0.0% of violations, `llm_judge` catches 63.0% (with a 17.4% false positive rate), and `gatekeeper` catches 100.0% (with a 13.0% false positive rate).

## Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │              Agent (LangGraph)               │
                 │        reasons about a tool call to make      │
                 └───────────────────────┬───────────────────────┘
                                          │  tool_name, args
                                          │  (reasoning NOT forwarded)
                                          ▼
                 ┌─────────────────────────────────────────────┐
                 │                 GateKeeper API                │
                 │                  (FastAPI)                    │
                 │                                                │
                 │   ┌────────────────────────────────────────┐   │
                 │   │           RuleEngine interface            │   │
                 │   │                                            │   │
                 │   │  ┌─────────────────┐  ┌──────────────────┐  │   │
                 │   │  │ PydanticRuleEngine│  │  OPARuleEngine   │  │   │
                 │   │  │  (in-process,      │  │ (OPA/Rego sidecar,│  │   │
                 │   │  │   ~0.1ms)          │  │   HTTP, ~7-15ms)  │  │   │
                 │   │  └─────────────────┘  └──────────────────┘  │   │
                 │   └────────────────────────────────────────┘   │
                 │                                                │
                 │   PII · Argument Bounds · Denylist ·           │
                 │   RateLimit · ScopeCreep                       │
                 └──────────┬──────────────────────┬───────────────┘
                             │                       │
                             ▼                       ▼
                 ┌───────────────────┐   ┌─────────────────────┐
                 │   session_state    │   │     audit_log        │
                 │  (fast, indexed,    │   │  (compliance record,  │
                 │   pruned            │   │   read by Streamlit    │
                 │   independently)    │   │   dashboard)           │
                 └───────────────────┘   └─────────────────────┘
                                          │
                                          ▼
                             ┌─────────────────────────┐
                             │   ALLOW / BLOCK decision   │
                             │   → tool executes or not   │
                             └─────────────────────────┘
```

The gate sits between the agent's decision to call a tool and the tool actually executing. It only ever receives `tool_name` and `args` — the rule evaluation function's signature has no parameter for reasoning, so there's nothing to ignore because there's nothing to pass in.

## Milestones

| # | Milestone | What was built | Why it matters |
|---|---|---|---|
| M1 | Core gate service | FastAPI + Pydantic v2, SQLAlchemy 2.0 async + asyncpg, Postgres audit log. Three stateless rules (PII detection, argument bounds, denylist), config-driven via YAML. | Establishes structural isolation from turn one: the rule function's signature only accepts `(tool_name, args)`. Default-ALLOW for unknown tools is a documented, deliberate opt-in policy tradeoff, not an oversight. |
| M2 | Stateful cross-call detection | A separate `session_state` table (fast, indexed, pruned independently from the audit log), plus `RateLimitRule` and `ScopeCreepRule`. A LangGraph + Groq (llama-3.3-70b) demo agent proves the flow end-to-end via a real HTTP call to the gate API. | `ScopeCreepRule` is the centerpiece: once an earlier call in a session tags an entity as protected, any later call touching that entity is blocked — no matter how persuasive the agent's justification for the later call is. |
| M3 | Dual rule engine | A `RuleEngine` interface with two interchangeable implementations: `PydanticRuleEngine` (in-process, ~0.1ms) and `OPARuleEngine` (OPA/Rego sidecar over HTTP, ~7-15ms). All five rule families ported to Rego, with config kept in a separate `data.json` rather than hardcoded. 25/25 parity tests. | Proves the policy logic isn't accidentally coupled to one engine's semantics — both implementations produce identical decisions, including on the scope-creep scenario. Also introduces a second deliberate tradeoff: fail-BLOCK if OPA is unreachable (infra failure) vs. fail-ALLOW for unknown tools (unconfigured policy). |
| M4 | Red-team benchmark | 50 scenarios: 21 scope_creep (weak/moderate/sophisticated tiers), 10 rate_limit, 10 pii_leak, 8 clean/false-positive-control. Compares `no_gate`, `llm_judge` (Groq, given full context including session history for fairness), and `gatekeeper`. | This is where the headline result comes from — see above. |
| M5 | Streamlit dashboard | Reads from the same Postgres `audit_log` (read-only observability, no new gate logic). Four tabs: Overview, Violation Categories, Review Queue (human Confirm/False-Positive sampling of BLOCK decisions, persisted to a `human_reviews` table), Benchmark Results. | The Review Queue produces a real, human-reviewed false-positive rate that's distinct from the benchmark's synthetic FP rate — a second, independent signal on how the gate performs. |

## Key Design Decisions

**Reasoning isolation is structural, not a filtering step.** The rule evaluation function's signature is `(tool_name, args) -> Decision`. There is no reasoning parameter to strip out or ignore — it's simply not part of the call. This matters because "we ignore the reasoning" is a much weaker claim than "the reasoning cannot reach this code path." The former can regress if someone adds a field later; the latter can't, without changing the function's contract.

**`session_state` and `audit_log` are separate tables.** `session_state` exists purely to answer "has this happened before in this session" as fast as possible, and gets pruned on its own schedule since it doesn't need to persist. `audit_log` exists for compliance and observability — every decision, kept, read by the dashboard. Conflating them would mean either compliance data getting pruned for performance, or operational lookups getting slower as compliance history grows.

**Default-ALLOW and fail-BLOCK are two different tradeoffs, not the same choice applied twice.** An unknown tool (no rule configured for it) defaults to ALLOW — the system treats an unconfigured policy as the operator's choice to make, not the gate's. An unreachable OPA sidecar (an infrastructure failure) defaults to BLOCK — the system treats an inability to evaluate policy as a reason to be conservative, not permissive. The distinction is: unconfigured policy vs. broken infrastructure get opposite defaults, deliberately.

**OPA exists in addition to the Pydantic engine, not instead of it.** The Pydantic engine is faster (~0.1ms vs ~7-15ms) and has no external dependency, which matters for latency-sensitive paths. OPA/Rego gives policy-as-data — rules and config live outside application code, in a form a security or compliance team can read and change without touching Python. The 25/25 parity tests exist specifically to make sure choosing one over the other for operational reasons doesn't silently change what's allowed and blocked.

## How to Run

Requires Docker and [uv](https://github.com/astral-sh/uv).

**1. Start infrastructure (Postgres, OPA sidecar):**
```bash
docker compose up -d
```

**2. Install dependencies:**
```bash
uv sync --all-extras
```

**3. Run the gate service:**
```bash
uv run uvicorn gatekeeper.api:app --reload
```

**4. Run the demo agent** (LangGraph + Groq, exercises the gate over a real HTTP call):
```bash
uv run python -m gatekeeper.demo.agent
```

**5. Run the red-team benchmark:**
```bash
uv run python -m gatekeeper.benchmark.run --engine pydantic
uv run python -m gatekeeper.benchmark.run --engine opa
```
Use `--report-only` to regenerate the report from a previous run's stored results without re-executing scenarios:
```bash
uv run python -m gatekeeper.benchmark.run --report-only
```

**6. Run the dashboard:**
```bash
uv run streamlit run gatekeeper/dashboard/app.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language / tooling | Python 3.11+, uv |
| API | FastAPI, Pydantic v2 |
| Data | SQLAlchemy 2.0 (async) + asyncpg, PostgreSQL |
| Policy engine | OPA / Rego |
| Demo agent | LangGraph, Groq (llama-3.3-70b) |
| Dashboard | Streamlit |
| Testing | pytest, OPA-native test framework (`opa test`) |
| Infra | Docker Compose |

## Test Coverage

151 tests total, all passing: 120 Python tests (pytest) + 31 native Rego tests (opa test).

```bash
uv run pytest
opa test ./policies -v
```

## Honest Limitations / Scope

GateKeeper is a demonstration/portfolio system, validated against a self-designed 50-scenario benchmark — it has not been run against production traffic or adaptive real-world adversaries who know the rule set and are trying to route around it. The five rule families (PII detection, argument bounds, denylist, rate limit, scope creep) are illustrative of the approach, not an exhaustive policy taxonomy for any real deployment. The LLM-judge baseline was given full session context specifically to keep the comparison fair, but it's one model (Groq llama-3.3-70b) with one prompting approach — it isn't a claim that every possible LLM-judge configuration fails the same way. The 13.0% false positive rate on synthetic scenarios and the human-reviewed rate from the dashboard's Review Queue are both useful signals, but neither substitutes for false-positive data from real usage.

## What I'd Do Next

- Expand the rule taxonomy beyond the current five families, and test coverage against violation types not represented in the 50-scenario set.
- Move from static red-team scenarios to adaptive red-teaming, where an adversarial process iterates against the gate's known behavior rather than running a fixed script.
- Extend scope-creep-style detection to multi-step chained violations, where no single call looks like a violation but the sequence does.
