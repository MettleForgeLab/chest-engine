# chest-engine

**Layer:** runtime-orchestrator  
**Scope:** Runtime orchestration + event membrane enforcement + deterministic commit production.  
**Non-scope:** This repo does not define constitutional invariants, switching law, or scalar regulation math. It enforces upstream contracts only.

## What Chest Engine does

- resolves role/domain context
- freezes config/routing/gating/seed pre-decode
- calls model-serving endpoints (A/B)
- performs a non-LLM folding pass (optional; can be simple in v0.1)
- writes an atomic, write-once commit artifact per event
- appends reflection/ledger logs
- exposes replay and observability APIs

## Hard boundaries

Chest MUST NOT:

- redefine invariants (ForgeEcosystem)
- redefine switching semantics (ConditionalBoundedness)
- redefine scalar regulation math (ARIA-Regulation-Layer)
- mutate control parameters after decode start
- use persistence as readiness/gain input
- read other model internal scalar state

Chest MUST:

- enforce event membrane (first token emission → atomic commit)
- expose /replay/run for deterministic control-plane proof
- stamp events with bundle/role/domain context

Governance defines. Mechanisms compute. Domains declare. Chest orchestrates. Ops verifies.
forge-deps.yaml
