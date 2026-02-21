# Deterministic Commit Record

Chest produces a deterministic_commit object for replay proof.

Deterministic hash must exclude:

- event_id
- timestamps
- durations
- latency

Required fields:

- model_ids / model_build_id
- config_hash
- param_block_hash
- seed
- routing_decision
- gating_params
- telemetry_sources
- tolerance
- bundle_context / role_context / domain_context
- determinism_profile
