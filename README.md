# GateKeeper

**A deterministic policy gate that catches what LLM judges structurally cannot — because it never reads the reasoning that fools them.**

GateKeeper intercepts LLM tool calls with rules that evaluate only the tool name, arguments, and session history. The agent's stated reasoning is never passed to any rule — not ignored, but structurally inaccessible. This means a sufficiently persuasive justification cannot talk the gate into approving a violation.

Based on the concept from "Reason Less, Verify More: Deterministic Gates Recover a Silent Policy-Violation Failure Mode in Tool-Using LLM Agents."

## The Problem

When an LLM agent wants to violate a policy, it can construct a justification that sounds legitimate: citing a plausible policy clause, claiming emergency override authority, invoking a technicality about the restriction's scope. An LLM-judge verifier reads this reasoning and is susceptible to the same failure mode — it can be persuaded by the same text that fooled the acting agent.

GateKeeper sidesteps this entirely. Rules never see the reasoning text. They evaluate what the agent wants to do (tool name + args), not why it claims to want to do it.

## The Headline Result

A red-team benchmark measured catch rates across 50 scenarios with reasoning of varying persuasiveness:

**Overall results** (50 scenarios across all categories):

| Approach | Catch Rate | False Positive Rate |
|----------|-----------|---------------------|
| No gate (baseline) | 0.0% | 0.0% |
| LLM Judge (Groq llama-3.3-70b) | 63.0% | 17.4% |
| GateKeeper | **100.0%** | 13.0% |

**Scope Creep catch rate by reasoning persuasiveness** (21 scenarios — the core failure mode):

| Persuasiveness Tier | LLM Judge | GateKeeper |
|---------------------|-----------|------------|
| Weak ("I'll just delete it anyway") | 100% | 100% |
| Moderate ("this is a different operation type") | 100% | 100% |
| Sophisticated (cites GDPR articles, incident playbooks, governance tickets) | **12.5%** | **100%** |

The LLM judge was given full context — tool call, args, session history, and the agent's reasoning — for fairness. The only variable being tested was whether persuasive reasoning can produce a wrong decision despite having the same facts GateKeeper uses to correctly block. The answer, on sophisticated reasoning, is yes. GateKeeper's accuracy is structurally unaffected because it never reads the reasoning text at all.

## Architecture

```
LLM Agent
   │  tool_name + args (+ reasoning, discarded by gate)
   ▼
┌──────────────────────────────────────────┐
│            GateKeeper Service             │
│                                          │
│  ┌──────────────┐    ┌───────────────┐  │
│  │  RuleEngine  │    │  Audit Logger │  │
│  │  interface   │───▶│  (Postgres)   │  │
│  └──────┬───────┘    └───────────────┘  │
│         │                                │
│    ┌────┴────┐                           │
│    ▼         ▼                           │
│ Pydantic   OPA/Rego                      │
│ Engine     Engine                        │
│ (~0.1ms)   (~7-15ms)                     │
└──────────────────────────────────────────┘
         │
    ┌────┴────────────────┐
    ▼                     ▼
 audit_log           session_state
 (append-only,       (indexed, pruned,
  compliance)         stateful rules)
```

## Milestones

| Milestone | What was built | Key design decision |
|-----------|---------------|---------------------|
| **M1** | Core gate service: FastAPI, 3 stateless rules (PII, argument bounds, denylist), Postgres audit log | Structural reasoning isolation — `Rule.evaluate()` signature is `(tool_name, args)` only |
| **M2** | Stateful cross-call detection: `session_state` table, RateLimitRule, ScopeCreepRule | Separate session_state from audit_log — fast indexed reads for rules, immutable compliance record for audit |
| **M3** | Dual rule engine: PydanticRuleEngine + OPARuleEngine with parity tests | OPA as swappable sidecar, not replacement — both remain fully functional |
| **M4** | Red-team benchmark: 50 scenarios, 3 approaches, persuasiveness gradient | LLM judge gets full context (session history) for fairness — the variable tested is reasoning susceptibility, not information access |
| **M5** | Streamlit dashboard: overview, violations, review queue, benchmark results | Human-reviewed FP rate (from review queue) is distinct from benchmark's synthetic FP rate — both tracked separately |

## Key Design Decisions

### Structural Reasoning Isolation

The gate doesn't "ignore" agent reasoning — the `Rule.evaluate()` method signature accepts only `(tool_name, args)`. Reasoning is never passed in, so no rule can access it even if it wanted to. This is enforced at the type level, not by convention.

### session_state vs audit_log

Two separate tables serving different purposes:
- **audit_log**: Append-only compliance record. Immutable, never pruned. What happened and when.
- **session_state**: Purpose-built for fast indexed reads by stateful rules. Pruned on a TTL schedule. Gets written on every gate check in the same transaction as audit_log, so they can't diverge.

### Default-ALLOW vs Fail-BLOCK

Two different "allow" decisions with different meanings:
- **Unknown tool → ALLOW**: No policy configured for this tool. Opt-in design — policies are added incrementally.
- **OPA unreachable → BLOCK**: Policy engine is down. Cannot verify compliance. Fail closed.

These are deliberately different tradeoffs documented in the code, not accidental inconsistencies.

### Why OPA in Addition to Pydantic

Pydantic rules work but conflate policy logic with application code — every policy change requires a code change and redeploy. OPA/Rego separates policy from code: declarative, versionable independently, testable with OPA's own framework. Both engines remain fully functional and switchable via config, proven equivalent by 25 parity tests.

## How to Run

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for Postgres + OPA)

### Quick Start

```bash
# Clone and install
git clone <repo-url> && cd gatekeeper
uv sync --extra dev

# Start Postgres + OPA
docker compose up -d

# Run the gate service
uv run uvicorn src.gatekeeper.main:app --reload

# Run the scope-creep demo (requires the gate service running)
uv run python -m agent_demo.scenarios.scope_creep_demo

# Run with OPA engine
uv run python -m agent_demo.scenarios.scope_creep_demo --engine opa
```

### Running the Benchmark

```bash
# Set your Groq API key
export GROQ_API_KEY=gsk_...

# Run the full benchmark (50 scenarios, costs Groq API calls)
uv run python -m benchmark

# Regenerate report from cached results (no API calls)
uv run python -m benchmark --report-only
```

### Running the Dashboard

```bash
# Install dashboard dependencies
pip install -r dashboard/requirements-dashboard.txt

# Launch
uv run streamlit run dashboard/app.py
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Package Manager | uv |
| Web Framework | FastAPI |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 async |
| Database | PostgreSQL (asyncpg) |
| Policy Engine | OPA/Rego |
| Agent Demo | LangGraph + Groq (llama-3.3-70b) |
| Dashboard | Streamlit |
| Testing | pytest + OPA native test framework |
| Infrastructure | Docker Compose |

## Test Coverage

**151 tests, all passing.**

```bash
# Python tests (120)
uv run pytest -v

# OPA/Rego tests (31)
opa test -b policies/rego/
```

Test categories:
- Rule isolation tests (each rule independently)
- Engine integration tests (mixed rules, stateful flow)
- API integration tests (full request → audit log)
- Parity tests (Pydantic vs OPA produce identical decisions)
- Benchmark data layer tests
- Transactional consistency tests
- Adversarial tests (reasoning independence)

## Limitations

This is a demonstration system validated against a self-designed 50-scenario benchmark, not battle-tested against production traffic or adaptive real-world adversaries. The benchmark scenarios were authored by the same person who built the system, which introduces selection bias — the scenarios test the failure modes I knew to look for.

The rule set (5 families: PII detection, argument bounds, denylist, rate limit, scope creep) is illustrative, not exhaustive. Real production policies would need additional rules for credential handling, data exfiltration patterns, resource consumption, and cross-service authorization — none of which are implemented here.

The LLM judge benchmark uses a single model (llama-3.3-70b via Groq) with a fixed prompt. Different models or prompt strategies might perform differently. The benchmark measures one specific failure mode (reasoning-based bypass) under controlled conditions, not general LLM judgment capability.

## What I'd Do Next

- **Expand the rule taxonomy**: Add credential handling, data exfiltration detection, and resource consumption rules to cover more real-world policy categories.
- **Adaptive red-teaming**: Replace static scenarios with an adversarial agent that iteratively refines its bypass strategy based on gate responses, testing against evolving rather than fixed justifications.
- **Multi-step chained violations**: Detect sequences where individual calls are each compliant but their combination violates policy (e.g., exfiltrating data across multiple API calls that each look benign in isolation).
