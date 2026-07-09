# GateKeeper Benchmark Results

## Overview

This benchmark compares three approaches to catching policy violations:
1. **No gate** — baseline, everything executes
2. **LLM judge** — Groq llama-3.3-70b evaluates each tool call
3. **GateKeeper** — deterministic policy engine (Pydantic backend)

**Total scenarios**: 50

## Overall Results

| Approach | Catch Rate | False Positive Rate | False Negative Rate |
|----------|-----------|--------------------|--------------------|
| no_gate | 0.0% | 0.0% | 100.0% |
| llm_judge | 63.0% | 17.4% | 37.0% |
| gatekeeper | 100.0% | 13.0% | 0.0% |

## Results by Category

### Clean

| Approach | Catch Rate | False Positive Rate | False Negative Rate |
|----------|-----------|--------------------|--------------------|
| no_gate | N/A | 0.0% | N/A |
| llm_judge | N/A | 15.8% | N/A |
| gatekeeper | N/A | 5.3% | N/A |

### Pii Leak

| Approach | Catch Rate | False Positive Rate | False Negative Rate |
|----------|-----------|--------------------|--------------------|
| no_gate | 0.0% | N/A | 100.0% |
| llm_judge | 85.7% | N/A | 14.3% |
| gatekeeper | 100.0% | N/A | 0.0% |

### Rate Limit

| Approach | Catch Rate | False Positive Rate | False Negative Rate |
|----------|-----------|--------------------|--------------------|
| no_gate | 0.0% | 0.0% | 100.0% |
| llm_judge | 33.3% | 25.0% | 66.7% |
| gatekeeper | 100.0% | 50.0% | 0.0% |

### Scope Creep

| Approach | Catch Rate | False Positive Rate | False Negative Rate |
|----------|-----------|--------------------|--------------------|
| no_gate | 0.0% | N/A | 100.0% |
| llm_judge | 58.8% | N/A | 41.2% |
| gatekeeper | 100.0% | N/A | 0.0% |

## Scope Creep: Catch Rate by Reasoning Persuasiveness

This is the key result — does the LLM judge's catch rate drop as reasoning gets more persuasive?

| Persuasiveness Tier | No Gate | LLM Judge | GateKeeper |
|---------------------|---------|-----------|------------|
| **Weak** | 0.0% | 100.0% | 100.0% |
| **Moderate** | 0.0% | 100.0% | 100.0% |
| **Sophisticated** | 0.0% | 12.5% | 100.0% |

## Interpretation

**GateKeeper** catches 100.0% of violations with 13.0% false positives.
**LLM Judge** catches 63.0% of violations with 17.4% false positives.

GateKeeper outperforms the LLM judge by 37.0 percentage points on catch rate. This suggests the deterministic approach is more reliable at catching policy violations, particularly when agents provide sophisticated justifications.

### Persuasiveness Impact

- **Weak** reasoning: GateKeeper 100.0%, LLM Judge 100.0%
- **Moderate** reasoning: GateKeeper 100.0%, LLM Judge 100.0%
- **Sophisticated** reasoning: GateKeeper 100.0%, LLM Judge 12.5%
