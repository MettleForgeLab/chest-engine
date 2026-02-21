# POST /replay/run

Request:
{
"case_id": "replay_smoke_001",
"input_text": "Describe warmth in five words.",
"seed": 123456
}

Response:
{
"commit_hash": "sha256(canonical_json(deterministic_commit_without_event_id))",
"deterministic_commit": { ... }
}

Purpose:

- prove deterministic control-plane outputs
- token text determinism is out of scope
