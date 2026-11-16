# Design Review: Automated Documentation Sync and SCRUM-6

**Review date:** 2026-11-16
**Status:** Original design findings have implementation resolutions where feasible. Broad QA completed with 42 tests passing; the code/security review is documented in `review.md`.

## Findings and Resolutions

### DR-1 — High: Cross-process idempotency and target persistence
- **Affected:** FR-3, FR-6, AC-5, US-4; architecture sections 3.4, 4.6, and 4.7.
- **Original evidence:** The CLI recreated in-memory target and checksum/event ledgers for each invocation.
- **Resolution:** The CLI now uses `SqliteSyncState`; target state and checksum share one transaction. Focused tests cover database reopen and separate subprocess CLI executions (`tests/unit/test_sqlite_sync_state.py`, `tests/integration/test_cli_persistence.py`).
- **Residual risk:** SQLite is a single-machine mock target, not a production registry. Database loss requires full resync; backups are not configured.

### DR-2 — High: Webhook execution and acknowledgement
- **Affected:** FR-5, AC-4, NFR-1, NFR-4.
- **Original evidence:** No HTTP receiver existed; `--trigger event` was only a CLI label.
- **Resolution:** `apps/sync_service/webhook.py` implements the v1 three-field event contract, raw-body timestamped HMAC, 5-minute tolerance, body/path limits, repository/path validation, durable SQLite event state, and 2xx only after terminal path outcomes and durable DLQ writes. Persistence failures release the event and produce retryable 5xx behavior. `tests/integration/test_webhook.py` exercises these cases using an ASGI transport.
- **Residual risk:** No production provider, reverse proxy, TLS termination, or public deployment is configured or tested. The service defaults to loopback; a provider-facing deployment needs approved hosting and network controls.

### DR-3 — Medium: Event-scoped missing paths
- **Affected:** FR-5, FR-7, AC-6.
- **Original evidence:** Filtering discovered files silently omitted requested files that no longer existed.
- **Resolution:** Requested scoped paths are retained and missing paths become per-file source-access failures; tests assert continuation and a DLQ record. Paths are constrained to Markdown and the configured repository/source scope.
- **Review follow-up:** Code review found that an explicit path-scoped CLI argument could bypass configured include/exclude filters. The orchestrator now rejects out-of-scope paths; `test_path_scoped_cli_request_cannot_bypass_exclude_patterns` covers the fix.

### DR-4 — Medium: Source and DLQ failure isolation
- **Affected:** FR-7, NFR-1.
- **Original evidence:** A candidate `stat()` failure or DLQ write exception could abort a batch without a reportable outcome.
- **Resolution:** Per-file stat/read failures are represented as outcomes; inability to persist a failure escapes as a persistence error and prevents webhook acknowledgement/event completion. JSONL records are flushed and `fsync`ed. Resilience tests exercise missing-path continuation and failed DLQ persistence.
- **Residual risk:** A source-root discovery failure is a run-level infrastructure failure; no per-file classification is possible when the root itself cannot be traversed.

### DR-5 — Medium: Run/document observability
- **Affected:** FR-7, NFR-3.
- **Original evidence:** Only aggregate CLI output existed; document key and retry details were missing from persisted failures.
- **Resolution:** Structured JSON document/run logs and CLI/webhook summaries include correlation, counts, duration, and retries; DLQ records include document key (when available), error class/code, and attempt count.
- **Residual risk:** No external metrics exporter is configured.

### DR-6 — Medium: Missing frontmatter policy
- **Affected:** FR-2, AC-2.
- **Original evidence:** An earlier acceptance-criteria statement conflicted with required metadata validation.
- **Resolution:** The user confirmed missing frontmatter is a validation failure; `requirements.md` and `architecture.md` align, and implementation continues with other documents.

### DR-7 — Medium: Diagnostic redaction
- **Affected:** NFR-4; architecture sections 6.2 and 8.
- **Original evidence:** Raw exception strings could be persisted without a redaction rule.
- **Resolution:** Common secret-like assignments and values from secret-named environment variables are redacted and bounded before logging/DLQ persistence. A resilience test checks a bearer-token-shaped diagnostic.
- **Residual risk:** Pattern-based redaction is not a guarantee against every secret encoding. No external connector is enabled; review exception formats again before adding one.

### DR-8 — Medium: Story-intake source access and data governance
- **Affected:** FR-1A, AC-0, NFR-4.
- **Resolution:** A local `.docx` CLI accepts only explicitly labeled story fields, rejects missing/ambiguous required values, and stores valid normalized records in a separate SQLite store. `list` and explicit `delete` commands are provided; no automatic expiration applies. Jira/Confluence commands return an unavailable-integration diagnostic and make no external request.
- **Operational assumptions:** `.docx` input limit 5 MiB (25 MiB expanded archive); `STORY_DATABASE_PATH` defaults to ignored `.story-intake/records.sqlite3`; local OS account permissions are the access boundary; no automated backup or external sharing.
- **Residual risk:** Jira/Confluence source retrieval and Word `.doc` (legacy binary) ingestion are not implemented. Local story data is not encrypted by the application; filesystem/OS account controls are assumed.

### DR-9 — Low: Static-page hosting
- **Affected:** FR-1B/FR-1C and SCRUM-6 delivery.
- **Resolution:** The browser app is implemented and tested locally; no server or network dependency was added.
- **Residual risk:** Static hosting/deployment was not specified or approved and is not included.

## Remaining Decisions
1. Provide authorized read-only Jira/Confluence access and scopes before implementing those connectors.
2. Select approved hosting/reverse-proxy/TLS controls if the webhook must be exposed to a remote event provider.
3. Decide state backup/recovery expectations beyond the documented local full-resync/manual-reintake assumption.
4. Approve a production registry connector and source-removal policy if Phase 1 must write beyond local SQLite mock storage.

## Reviewed Scope
- Compared requirements, architecture, design findings, and implementation plan for requirement and boundary consistency.
- Checked the relevant source/test locations and the focused test evidence recorded in `impl-plan.md`.
- Broad QA completed with `python -m pytest tests/unit tests/integration tests/resilience -v --cov=.` (42 passed, 87% aggregate repository coverage). The code/security review and its limited secret-pattern scan are documented separately in `review.md`; this artifact itself does not claim a comprehensive scan.
