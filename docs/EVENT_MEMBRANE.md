# Event Membrane (Chest Engine)

Membrane spans:

- start: first token emission (decode start)
- end: atomic commit write (terminal action)

Rules:

- config/routing/gating/seed frozen pre-decode
- no mutation of control params after decode start
- one atomic commit per event
- commit is write-once and idempotent by event_id
