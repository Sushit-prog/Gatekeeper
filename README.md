# GateKeeper

Deterministic policy enforcement gate for LLM tool calls. Validates tool-call requests against configurable rules before execution.

## Architecture

```
Client (test harness / future agent)
   │  POST /gate/check
   ▼
┌─────────────────────────────────┐
│   FastAPI Gate Service          │
│  ┌───────────┐  ┌───────────┐  │
│  │   Rule    │  │   Gate    │  │
│  │  Engine   │─▶│  Decision │  │
│  └───────────┘  └─────┬─────┘  │
│                       │        │
│  ┌────────────────────▼─────┐  │
│  │     Audit Logger         │  │
│  └────────────────────┬─────┘  │
└───────────────────────┼────────┘
                        ▼
                   PostgreSQL
                   (audit_log)
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

## Testing

```bash
uv run pytest -v
```

Key test categories:
- **Rule isolation tests**: each built-in rule tested independently
- **Engine integration tests**: multiple rules on one tool, mixed severities
- **API integration tests**: full request → response → audit log verification
- **Adversarial test**: identical args with different agent_reasoning produces identical decisions
- **Latency test**: rule evaluation completes in <50ms
