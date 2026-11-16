# Implementation Plan: Automated Documentation Sync and SCRUM-6

**Status:** Approved implementation plan; implementation, broad QA, review, verification, and PR-description handoff are complete for the available local scope. Full FR-1A remote-source acceptance and external webhook deployment remain blocked by missing authorized integrations/hosting.
**Scope:** Requirements in `requirements.md` and design in `architecture.md`, including the sync CLI, durable local mock state, provider-agnostic webhook, constrained local story intake, and SCRUM-6.

## 1. Decisions and Operational Assumptions

### Confirmed
- SCRUM-6 is an isolated static HTML/CSS/Vanilla JavaScript application at `apps/tour_booking/index.html`; it has no booking backend or network calls.
- Missing Markdown frontmatter is a validation failure; processing continues for independent files.
- FR-1A is a runtime capability. Normalized records are retained until explicitly deleted; no automatic expiration applies.
- The sync mock target, checksum ledger, and event ledger use SQLite, and target/checksum changes share one transaction.
- Webhook baseline: FastAPI; version 1 `event_id`, `repository_id`, `changed_paths`; `X-DocSync-Signature: t=<unix-seconds>,v1=<hex>`; HMAC input `<timestamp>.<raw-body>`; 5-minute timestamp tolerance; 1 MiB request and 100-path limits; 4xx for auth/schema/path errors; 5xx for persistence/infrastructure errors; 2xx only after terminal path outcomes and durable DLQ failures; retries reuse the event ID.
- Python Playwright with pytest is approved for SCRUM-6 browser tests.

### Conservative operational assumptions (not additional product guarantees)
- Sync SQLite path is configured by `SYNC_DATABASE_PATH`, default `.sync/state.sqlite3`; `.sync/` is ignored. No automatic backup is configured; lost sync state requires full resync.
- Story records use a separate `STORY_DATABASE_PATH`, default `.story-intake/records.sqlite3`; `.story-intake/` is ignored. Local OS account permissions are the access boundary; records have no expiry, no external sharing, and no automated backup.
- Local Word intake is limited to labeled `.docx` files up to 5 MiB (25 MiB expanded archive). No Jira/Confluence call is made unless an authorized read-only connector is later configured; none is assumed in this delivery.
- Static hosting/deployment is out of scope. The JSONL DLQ is kept separate from SQLite and flushed to disk before an event is acknowledged.

## 2. Dependency-Ordered Milestones

### M0 — Requirements and Architecture Baseline
**Outcome:** All consequential choices are confirmed or explicitly bounded as assumptions.
- Verify frontmatter failure policy, event wire contract, local SQLite boundaries, SCRUM-6 placement/test approach, and FR-1A manual deletion.
- Keep unavailable provider credentials, hosting, and backup mechanisms as explicit limitations; do not fabricate external integrations.
- **Evidence:** requirements, architecture, and design-review findings agree; operational assumptions are recorded.

### M1 — Durable Sync State (FR-3, FR-6, AC-5)
**Outcome:** Separate CLI processes observe the same mock target and checksum state.
- **Status:** Implemented and verified.
- Add `SqliteSyncState` for target documents, checksums, and event ledger.
- Commit target upsert/checksum as one SQLite transaction; retain a configurable local path.
- Add unit tests for cross-connection persistence, unchanged/changed documents, transaction rollback, and event state.
- Add integration coverage that launches separate CLI runs against the same database.
- **Gate:** changed and unchanged consecutive process runs have demonstrable persisted results.

### M2 — Scoped Paths, Failure Isolation, and DLQ (FR-2, FR-5, FR-7, AC-2, AC-6)
**Outcome:** Missing and malformed requested files become explicit failures while independent files continue.
- **Status:** Implemented and verified, including the code-review fix enforcing include/exclude filters on explicit CLI paths.
- Validate scoped paths as safe repository-relative Markdown paths and detect candidates resolving outside the source root.
- Preserve requested event paths absent from discovery so missing files receive a per-path result.
- Persist per-file source, validation, and retry-exhaustion failures; treat DLQ persistence failure as infrastructure failure.
- Include document key, error code/class, attempt count, redacted diagnostic, and run correlation in records/logs.
- **Gate:** tests cover missing paths, missing metadata, continuation, retry exhaustion, and DLQ failure.

### M3 — Webhook Trigger (FR-5, NFR-1, NFR-4, AC-4)
**Outcome:** Signed and validated webhook requests run incremental sync safely.
- **Status:** Implemented and verified through ASGI integration tests; remote deployment/provider operation is unverified.
- Add provider-agnostic FastAPI route with timestamped raw-body HMAC verification, 5-minute tolerance, 1 MiB body cap, 100 safe paths, and repository matching.
- Use durable event claims/completion, retryable 5xx state on infrastructure/persistence error, and terminal 2xx only after per-path failures are fsynced to the DLQ.
- **Gate:** tests cover valid events, duplicate delivery, signature/stale timestamp, malformed schema/path, limits, missing files, and DLQ persistence failure.

### M4 — Run and Document Observability (FR-7, NFR-3, NFR-4)
**Outcome:** Operators can correlate per-file and run outcomes without diagnostic secrets.
- **Status:** Implemented and verified for current mock/local behavior.
- Emit structured JSON logs with run ID, source path, document key where computed, error class, retry count, and duration/aggregate counts.
- Redact common secret-like values before logs and persisted diagnostics.
- **Gate:** tests inspect outcome data and verify persisted diagnostics do not contain a test secret.

### M5 — SCRUM-6 Static Page (FR-1B, FR-1C, AC-0A, AC-0B)
**Outcome:** Deliver the independent static presentation and browser-only brochure demo.
- **Status:** Implemented and browser-tested in Chromium.
- Create required panel order, selectors, responsive layout, form submit prevention, Blob/object URL/temporary-anchor download, 100 ms revocation, and repeat simulated failure behavior.
- Add Python Playwright integration tests and dependency/browser setup.
- **Gate:** browser tests verify desktop/mobile order, form behavior, enabled button/helper, filename/MIME, direct download flow, no new tab, deferred revocation, and synchronous error clearing.

### M6 — Story Intake Runtime (FR-1A, AC-0)
**Outcome:** Provide a usable local Word intake path without unauthorized external calls.
- **Status:** Local labeled `.docx` intake, validation, retention, and deletion are implemented and tested. Jira/Confluence successful-source intake remains unimplemented.
- Parse only explicitly labeled story fields from `.docx`; reject missing/ambiguous required fields rather than inventing content.
- Persist validated records in a separate SQLite store with explicit `list`/`delete` operations and no expiry.
- Return clear unavailable-integration output for Jira/Confluence until authorized read-only credentials and scopes are configured.
- **Gate:** tests verify valid/incomplete/ambiguous Word input, retained records, explicit deletion, and no external request for unavailable integrations.

### M7 — Broad QA, Verification, and Review
**Outcome:** Produce current, evidence-based repository handoff artifacts.
- **Status:** Complete for the delivered local scope; overall product acceptance remains blocked on the FR-1A external-source gap.
- Run focused tests after each slice and full unit/integration/resilience suites with coverage.
- Verify requirements-to-design/code/test traceability and report unsupported behavior.
- Complete code/security review and document findings in `review.md`.
- Prepare `pr-description.md` from actual diff and measured evidence; do not commit, create a branch, or open a remote PR.
- **Gate:** no test, security scan, approval, or hosting/connector capability is reported without evidence.

## 3. Focused Validation Strategy
- Use `python -m pytest` from the repository root; the earlier `pytest -q` denial is not treated as evidence. The user subsequently authorized running repository tests.
- Run new persistence/webhook/story tests first, then `tests/integration/test_tour_booking.py`, then full `tests/unit tests/integration tests/resilience` with coverage.
- Install declared Python dependencies from `requirements-dev.txt`; install the Chromium browser used by Playwright with `python -m playwright install chromium`.
- Keep test code under `tests/unit/`, `tests/integration/`, and `tests/resilience/`.

## 4. Exit Criteria
- Sync target/checksum and webhook event state persist across processes and meet transactional/idempotent behavior.
- Webhook authentication, payload/path validation, limits, terminal outcomes, duplicate handling, and retryable persistence failures are covered.
- Document-level validation/source failures are isolated and durably recorded; diagnostics are secret-safe.
- SCRUM-6 required DOM, responsive behavior, static form, brochure download, and simulated errors have browser evidence.
- Story intake supports the local labeled Word boundary, manual deletion, and explicit unavailable-provider behavior; external integrations remain disabled.
- `verify.md`, `review.md`, and `pr-description.md` reflect current evidence and remaining gaps. No release/PR action is taken.

## 5. Initial Implementation Evidence (Historical)
- `python -m pytest tests/unit/test_sqlite_sync_state.py tests/integration/test_webhook.py tests/integration/test_story_intake.py tests/integration/test_cli_persistence.py -v`: **11 passed**.
- `python -m playwright install chromium`: completed successfully.
- `python -m pytest tests/integration/test_tour_booking.py -v`: **3 passed**.
- These were early focused results and are superseded by final evidence below.

## 6. Final Evidence and Handoff
- `python -m pytest tests/unit tests/integration tests/resilience -v --cov=.`: **42 passed, 0 failed, 0 skipped**, 87% aggregate repository coverage, no warnings.
- The code review identified one medium path-scope filter bypass; it was fixed and covered by a regression test before the final full-suite run.
- The security review reported no actionable vulnerabilities; its scoped text-pattern search was not a comprehensive secret scan. `review.md` records method, limitations, and residual risks.
- `verify.md` records requirement traceability, test results, and the final **BLOCKED** gate for unavailable authorized Jira/Confluence integration and remote webhook deployment.
- `pr-description.md` is prepared as a handoff artifact only. No commit, branch, remote PR, public webhook exposure, or external connector was created.
