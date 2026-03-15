---
name: matverse-governance
description: Use this skill to assess repository governance using MatVerse-style metrics (Ψ coherence, Θ efficiency, CVaR risk, Ω decision), produce PASS/ESCALATE/BLOCK decisions, and output auditable ledger records for dashboards and CI workflows.
---

# MatVerse Governance

Use this skill when the user wants governance automation for repositories, pull requests, or CI pipelines.

## Inputs to collect

- Repository identifier (`owner/repo`)
- Change scope (commit, PR, branch, or release)
- Available evidence (diff, lint/typecheck/test logs, security scan results)

If evidence is missing, state assumptions explicitly before scoring.

## Scoring model

Compute:

- `Ψ` (coherence): structure/readability/consistency of the change
- `Θ` (efficiency): delivery quality (performance, CI stability, throughput)
- `CVaR` (risk): tail-risk from vulnerabilities, secrets, or fragile changes
- `PoLE` (optional): latent improvement potential from refactors/docs/tests

Decision score:

`Ω = 0.4*Ψ + 0.3*Θ + 0.2*(1 - CVaR) + 0.1*PoLE`

Default `PoLE = 0.5` if absent.

## Governance thresholds

- `PASS` when `Ω >= 0.80`
- `ESCALATE` when `0.50 <= Ω < 0.80`
- `BLOCK` when `Ω < 0.50`

## Workflow

1. **Ingest event**: normalize event metadata (repo, SHA/PR, actor, timestamp).
2. **Extract MNB**: create a deterministic record hash from the normalized payload.
3. **Evaluate metrics**: assign Ψ, Θ, CVaR, PoLE with concise rationale.
4. **Apply Ω gate**: compute final decision.
5. **Emit ledger record**: output a structured, immutable-style log entry.
6. **Report**: summarize action items to move from BLOCK→ESCALATE→PASS.

## Output contract

Return both human summary and machine-friendly JSON.

```json
{
  "repository": "owner/repo",
  "target": "pr#123",
  "metrics": {
    "psi": 0.82,
    "theta": 0.74,
    "cvar": 0.12,
    "pole": 0.60,
    "omega": 0.81
  },
  "decision": "PASS",
  "reasons": [
    "Coherent module boundaries and tests updated",
    "No critical findings in scans"
  ],
  "actions": [
    "Monitor flaky integration test for next 3 runs"
  ],
  "ledger": {
    "mnb_hash": "sha256:...",
    "timestamp": "2026-03-15T12:00:00Z"
  }
}
```

## Practical guidance

- Prefer evidence-backed scoring over intuition.
- Penalize unknown security posture via higher `CVaR`.
- Keep rationale short and auditable.
- Never claim certainty when telemetry is incomplete.
- When blocking, provide the fastest remediation path.
