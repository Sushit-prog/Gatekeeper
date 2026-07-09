# GateKeeper

Deterministic policy enforcement gate for LLM tool calls. Validates tool-call requests against configurable rules before execution.

## Architecture

```
Client (test harness / agent)
   │  POST /gate/check
   ▼
┌──────────────────────────────────────┐
│   FastAPI Gate Service               │
│  ┌─────────────┐  ┌──────────────┐  │
│  │ Rule Engine │  │  Gate        │  │
│  │ (stateless  │─▶│  Decision    │  │
│  │  + stateful)│  └──────┬───────┘  │
│  └──────┬──────┘         │          │
│         │ reads          │          │
│  ┌──────▼──────┐  ┌──────▼───────┐  │
│  │session_state│  │ Audit Logger │  │
│  │  (indexed)  │  └──────┬───────┘  │
│  └─────────────┘         │          │
└──────────────────────────┼──────────┘
                           ▼
                      PostgreSQL
                  (audit_log + session_state)
```

## Quick Start

```bash
# Start Postgres
docker-compose up -d

# Install dependencies
uv sync

# Run the service
uv run uvicorn src.gatekeeper.main:app --reload
```

The service starts at `http://localhost:8000`.

## API Endpoints

### POST /gate/check

Validate a tool call against policy rules.

```bash
# Clean request — ALLOW
curl -X POST http://localhost:8000/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","tool_name":"send_email","args":{"recipient":"user@gmail.com","body":"Hello"}}'

# PII in args — BLOCK
curl -X POST http://localhost:8000/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s2","tool_name":"send_email","args":{"recipient":"user@blocked-domain.com","body":"Hello"}}'

# Denylisted domain — BLOCK
curl -X POST http://localhost:8000/gate/check \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s3","tool_name":"send_email","args":{"recipient":"admin@blocked-domain.com","body":"Hi"}}'
```

Response:
```json
{
  "decision": "ALLOW|BLOCK",
  "matched_rules": [
    {"rule_id": "pii_detection", "passed": true, "reason": "No PII detected", "severity": "block"}
  ],
  "latency_ms": 0.12,
  "audit_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### GET /gate/rules

Return the currently loaded policy configuration.

```bash
curl http://localhost:8000/gate/rules
```

### GET /audit/query

Query audit log records with optional filters.

```bash
# All records
curl http://localhost:8000/audit/query

# Filter by session
curl "http://localhost:8000/audit/query?session_id=s1"

# Filter by tool and decision
curl "http://localhost:8000/audit/query?tool_name=send_email&decision=BLOCK&limit=10"
```

### GET /health

Liveness check including DB connectivity.

```bash
curl http://localhost:8000/health
```

## Design Decisions

### Agent Reasoning Isolation

The `agent_reasoning` field is stored in the audit log but **never evaluated** by the rule engine. This is enforced structurally: the `Rule.evaluate()` method signature accepts only `tool_name` and `args`. The reasoning string is not passed to any rule — it's not ignored, it's inaccessible. This ensures the gate makes decisions purely on what the agent wants to do, not why it claims to want to do it.

### Default Allow for Unknown Tools

When a `tool_name` has no policy defined in `policy_registry.yaml`, the engine returns `ALLOW` with an empty `matched_rules` list. This is a deliberate opt-in design: policies are added incrementally, and tools without rules pass through. This trades off comprehensive coverage for operational simplicity — you can roll out policies gradually without blocking everything by default.

### No Short-Circuit Evaluation

All applicable rules are evaluated for every request, even if an earlier rule already failed. This produces a complete audit trail showing every rule's verdict, which is essential for debugging policy issues and tuning false-positive rates.

### Warn Severity

Rules can have severity `"warn"` or `"block"`. Warn-severity failures are logged but do not cause a BLOCK decision. This enables flagging suspicious-but-allowed behavior for future review without disrupting the workflow.

## Stateful Rules (M2)

GateKeeper extends beyond per-request evaluation with **stateful cross-call constraint checking**. This catches failures that only emerge across a sequence of calls within a session.

### Session State vs Audit Log

| Table | Purpose | Mutability | Query Pattern |
|-------|---------|------------|---------------|
| `audit_log` | Append-only compliance record | Write-once | By time range, session, tool |
| `session_state` | Indexed lookups for stateful rules | TTL-pruned | By `(session_id, tool_name, created_at)` |

The split is deliberate: `audit_log` is the immutable compliance record; `session_state` is a purpose-built index for fast cross-call queries. They're written in the same transaction so they can't diverge, but they serve different needs.

### Built-in Stateful Rules

**RateLimitRule** — blocks if more than N calls to a tool occur within a time window per session. Configured per-tool in `policy_registry.yaml`:
```yaml
rate_limit:
  max_calls: 3
  window_seconds: 300
```

**ScopeCreepRule** — the core failure mode this project exists to catch. Blocks if a tool call references an entity that was explicitly marked as protected in an earlier call within the same session. The agent's reasoning for why it should be allowed is never evaluated — only the protection tag matters.

### Protection Tagging

Tools can "tag" entities as protected via the `tag_tools` config:
```yaml
check_permissions:
  tag_tools:
    protected_field: "record_id"
    protected_tag: "protected_record_ids"
```

When `check_permissions(record_id=X)` is ALLOW'd, the engine automatically writes a session_state record with `tags: {"protected_record_ids": ["X"]}`. ScopeCreepRule then blocks any subsequent call referencing X.

### Session State Pruning

Session state records are automatically pruned. Run manually or via cron:
```bash
# Prune records older than 24h (default)
uv run python scripts/prune_session_state.py

# Custom TTL
SESSION_STATE_TTL_HOURS=12 uv run python scripts/prune_session_state.py
```

## Agent Demo

The `agent_demo/` module demonstrates GateKeeper with a LangGraph agent. It requires optional dependencies:
```bash
uv sync --extra agent
```

### Scope Creep Demo

Run the standalone scope-creep demonstration:
```bash
# Start the service first
docker-compose up -d
uv run uvicorn src.gatekeeper.main:app

# In another terminal, run the demo with Pydantic engine (default)
uv run python -m agent_demo.scenarios.scope_creep_demo

# Or run with OPA engine (requires OPA sidecar)
uv run python -m agent_demo.scenarios.scope_creep_demo --engine opa
```

This reproduces the exact failure mode:
1. Agent calls `check_permissions(record_id=X)` → ALLOW (X tagged as protected)
2. Agent calls `delete_record(record_id=X)` with reasoning "deletion is a special case" → BLOCKED

The output clearly shows the before/after with and without GateKeeper.

## Rule Engines (M3)

GateKeeper supports two swappable rule engine backends via the `ENGINE_BACKEND` environment variable:

| Engine | Default | Description |
|--------|---------|-------------|
| `pydantic` | Yes | Python-native rules using Pydantic validation. Good for development and single-developer projects. |
| `opa` | No | OPA/Rego sidecar. Declarative policies, versionable independently, testable with OPA's own framework. Industry standard for multi-team policy management. |

### Why OPA?

Pydantic rules conflate policy logic with application code — every policy change requires a code change and redeploy. OPA/Rego separates policy from code:

- **Declarative**: Policies are data, not code. Easier to review, audit, and reason about.
- **Independent versioning**: Policy files can be versioned and deployed separately from the service.
- **Built-in testing**: OPA has its own test framework (`opa test`) for policy-level validation.
- **Industry standard**: Used by Netflix, Pinterest, Chef, and others for exactly this use case.

### Switching Engines

```bash
# Use Pydantic engine (default)
ENGINE_BACKEND=pydantic uv run uvicorn src.gatekeeper.main:app

# Use OPA engine (requires OPA sidecar)
docker-compose up -d opa
ENGINE_BACKEND=opa uv run uvicorn src.gatekeeper.main:app
```

### OPA Architecture

```
FastAPI Gate Service
    │
    ├─ RuleEngine interface (strategy pattern)
    │    ├─ PydanticRuleEngine   (M1/M2, unchanged)
    │    └─ OPARuleEngine        (queries OPA over HTTP)
    │
    └─ ENGINE_BACKEND env var selects implementation

OPA Server (Docker sidecar)
    │  POST /v1/data/gatekeeper/decision
    │  Input: { tool_name, args, session_history }
    │  Output: { decision, matched_rules }
    └  Policies loaded from ./policies/rego/
```

Session history is fetched in Python and passed to OPA as input — OPA does not talk to Postgres directly.

### Fail-BLOCK on OPA Unreachable

If the OPA server is unreachable, `OPARuleEngine` returns **BLOCK**. This is an infrastructure failure, distinct from the M1 default-ALLOW for unknown tools:

- **Unknown tool → ALLOW**: Policy is opt-in. No rule configured means no restriction.
- **OPA unreachable → BLOCK**: Policy engine is down. Cannot verify compliance. Fail closed.

This distinction is deliberate: an unreachable policy engine is a system failure that must be detected and resolved, not silently bypassed.

### Rego Policies

Policies live in `policies/rego/`:

```
policies/rego/
├── data.json                  # Policy config (bounds, denylists, rate limits)
├── decision.rego              # Top-level decision combiner
├── pii_detection.rego         # PII regex matching
├── argument_bounds.rego       # Type/pattern/range validation
├── denylist.rego              # Value denylist checks
├── rate_limit.rego            # Cross-call rate limiting
├── scope_creep.rego           # Protected entity tracking
└── *_test.rego                # OPA-native tests
```

Run OPA tests:
```bash
docker-compose up -d opa
docker compose exec opa opa test /policies -v
```

### Parity Testing

The parity test suite (`tests/test_parity.py`) runs the same test cases against both engines and asserts identical decisions:

```bash
# Pydantic parity tests (always run)
uv run pytest tests/test_parity.py::TestParity -v

# OPA parity tests (require OPA server)
docker-compose up -d opa
uv run pytest tests/test_parity.py::TestOPAParity -v
```

Both engines are proven equivalent on the full test suite, including the scope-creep scenario. Any behavioral mismatch is surfaced as a test failure, not hidden.

## Testing

```bash
uv run pytest -v
```

Key test categories:
- **Rule isolation tests**: each built-in rule tested independently (stateless + stateful)
- **Engine integration tests**: multiple rules on one tool, mixed severities, stateful flow
- **API integration tests**: full request → response → audit log verification
- **Scope creep integration test**: check_permissions → delete_record → BLOCK via API
- **Rate limit integration test**: N calls within window → BLOCK on N+1
- **Transactional consistency**: both tables written per check, matching row counts
- **Adversarial test**: identical args with different agent_reasoning produces identical decisions
- **Latency tests**: stateless <50ms, stateful <100ms
- **Parity tests**: both engines produce identical decisions on shared test cases
- **OPA tests**: Rego policies validated with OPA's built-in test framework
