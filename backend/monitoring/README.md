# Monitoring Agent — Phase 8

SQLite stores request-level metadata and per-agent status, model/agent versions,
error **codes** and latency only. It never stores features, questions, model scores,
evidence or reports. Use synthetic data for coursework. SQLite file is saved under
`outputs/audit.sqlite3` by default (not committed; see `.gitignore`).

Use `python backend/scripts/audit_cli.py summary` to inspect statistics and
`python backend/scripts/audit_cli.py recent --limit 5` to inspect metadata.

Only `/api/assess` provides the full 6-agent trace. For compatibility,
`/api/report/generate` still returns 5 agent steps but audits the execution and
returns `payload.audit_recorded` and `payload.monitoring_status`. The historical
`/api/workflow/run` is intentionally not audited.
