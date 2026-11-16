# Requirements Specification: Automated Documentation Sync

## 1. Overview

### 1.1 Purpose
Build an Automated Documentation Sync pipeline that reads Markdown documentation from repository files and synchronizes normalized documents into a target registry or mock storage. The baseline also includes SCRUM-6, a standalone static Tour Booking & Summary page whose only functional behavior is an in-browser brochure download.

### 1.2 In-Scope (Phase 1)
- Source connector: Local/repository Markdown files.
- Target connector: Registry/mock storage sink.
- Triggers: CLI-triggered sync and webhook/event-driven sync.
- Content format: Markdown (.md) with YAML frontmatter metadata.
- Reliability goals: Graceful handling of missing files, idempotent repeated runs, and rate-limit backoff behavior.
- SCRUM-6 static Tour Booking & Summary page, with no backend or network calls and only the brochure download functional.

### 1.3 Out of Scope (Phase 1)
- Bi-directional edits from target back to source.
- Rich format conversion beyond Markdown + frontmatter.
- Human approval workflow before write.
- Backend booking, payment, or tour reservation functionality.

## 2. Definitions
- Source document: A Markdown file discovered from repository paths configured for sync.
- Canonical document: The normalized representation generated from source content + validated metadata.
- Registry/mock storage: The target system that stores synced canonical documents.
- Sync run: A single execution initiated by CLI or event trigger.
- Deterministic document key: Stable ID derived from repository identity + normalized source path.
- Checksum: Hash of canonical content + selected metadata used for change detection.

## 3. Assumptions and Constraints
- All source files are .md documents.
- Metadata is supplied through YAML frontmatter at the top of each document.
- Missing required metadata fields are treated as validation failures.
- Secrets and connector credentials are provided via environment variables or secret stores, never hardcoded.

## 4. User Stories

### US-0: External Story Intake
As a requirements analyst, I want to ingest a user story from Jira, Confluence, or a Word document so that Copilot can convert the source material into a clear, traceable set of requirements.

### US-1: CLI Full Sync
As a documentation engineer, I want to run a full sync from CLI so that all repository Markdown docs are reflected in registry/mock storage.

### US-2: Event-Driven Incremental Sync
As a platform engineer, I want webhook-triggered sync so that changed docs are updated automatically after repository events.

### US-3: Metadata-Aware Sync
As a documentation owner, I want YAML frontmatter validated and synchronized so that each stored document has reliable metadata.

### US-4: Idempotent Re-Runs
As an operator, I want repeated runs to avoid duplicate writes so that retried jobs are safe.

### US-5: Graceful Failure Isolation
As an operator, I want missing or malformed files to be isolated so one bad file does not fail the entire run.

### US-6: Throttling Resilience
As a platform engineer, I want automatic backoff and retry on rate limits so sync remains stable under target throttling.

### US-7: Tour Booking & Summary Interface (SCRUM-6)
Provide a static single-page tour booking presentation with a booking form on the left and Tour Summary, Download Brochure, and Support panels on the right. Only the brochure download is functional; the form and other UI are presentation-only.

## 5. Functional Requirements

### FR-1 Source Discovery and Filtering
1. The system shall discover source Markdown files from configured repository paths.
2. The system shall support include and exclude path patterns.
3. The system shall ignore non-Markdown files.
4. The system shall read source files as UTF-8 text.

### FR-1A Story Intake and Normalization
1. The system shall accept a user story from Jira, Confluence, or a Word document source when an authorized integration or file upload is available.
2. The system shall extract the primary source reference, title, description, actors, goals, acceptance criteria, assumptions, and open questions.
3. The system shall validate that the extracted story contains enough information to produce requirements and flag missing or ambiguous details.
4. The system shall not invent missing requirements when the source is unavailable, unauthorized, or incomplete; instead it shall return a clear dependency or validation error.
5. The system shall store the normalized intake as a structured record suitable for downstream requirements engineering.
6. The system shall retain normalized intake records until explicitly deleted and shall not automatically expire them.

### FR-1B Static Tour Booking Interface (SCRUM-6)
1. The page shall present a booking form in a left column and summary panels in a right column, with a centered footer.
2. The right-column panels shall appear in DOM order as Tour Summary (`data-testid="tour-summary-card"`), Download Brochure (`data-testid="brochure-card"`), and Support (`data-testid="support-card"`).
3. At narrow viewports where the layout becomes one column, the right-column panels shall retain that DOM and visual order.
4. The booking form shall have `data-testid="booking-form"` and its submit button shall have `data-testid="book-now-btn"`.
5. Submitting the booking form shall call `event.preventDefault()` and shall not navigate or reload the page.
6. Except for the brochure download, the page UI shall remain static and shall not depend on a backend or make network calls.
7. The page shall be located at `apps/tour_booking/index.html`, as approved to comply with the repository's `apps/` and `shared/` application-code boundary.

### FR-1C In-Browser Brochure Download (SCRUM-6)
1. The brochure card shall contain the title and enabled button label "Download Brochure", with button selector `data-testid="download-brochure-btn"`.
2. The button shall be enabled without requiring booking-form completion.
3. The helper text "(Demo file generated in-browser)" shall appear below the button and remain visible when an error is shown.
4. A successful click shall create a Blob with MIME type `application/pdf`, create an object URL, and initiate a direct download using a temporary anchor with filename `tour-brochure.pdf`; it shall not open a new tab or call `window.open`.
5. After the anchor is clicked, the page shall defer revoking the object URL by 100 milliseconds.
6. When `URLSearchParams.get("simulate_error") === "true"`, a click shall bypass download and show "Unable to generate brochure (demo)" in an element with `data-testid="brochure-error"` and `role="alert"`.
7. On each click attempt, any prior inline error shall be cleared synchronously before generation logic runs. The simulated failure shall recur on every click while the query parameter remains true.

### FR-2 Frontmatter Parsing and Validation
1. The system shall parse YAML frontmatter when present.
2. The system shall parse Markdown body content separately from frontmatter.
3. The system shall validate required frontmatter fields before synchronization.
4. The system shall fail a document with a clear validation error when YAML is malformed.
5. The system shall continue processing remaining files after document-level validation failure.

### FR-3 Target Upsert Behavior
1. The system shall upsert canonical documents into registry/mock storage.
2. The system shall write by deterministic document key.
3. The system shall record target write success/failure per document.
4. The system shall not write duplicate records for repeated identical input.

### FR-4 CLI Trigger
1. The system shall provide a CLI command to run sync on demand.
2. The CLI shall support full sync and path-scoped sync modes.
3. The CLI shall return code 0 only when all processed files complete successfully.
4. The CLI shall return non-zero when one or more files fail.

### FR-5 Webhook/Event Trigger
1. The system shall support webhook/event-triggered sync execution.
2. Event-triggered sync shall process only changed or relevant files when event payload provides scope.
3. The system shall safely handle duplicate event deliveries.
4. The system shall reject invalid event payloads with structured diagnostics.
5. A version 1 event payload shall include `event_id`, `repository_id`, and `changed_paths`.
6. The system shall authenticate the raw request body using timestamped HMAC-SHA256 in the `X-DocSync-Signature` header, formatted as `t=<unix-seconds>,v1=<hex>`, with a 5-minute timestamp tolerance.
7. The system shall reject requests larger than 1 MiB and events containing more than 100 changed paths.
8. The system shall acknowledge an event with 2xx only after every requested path has a terminal outcome and each per-file failure is durably recorded.
9. The system shall return 5xx for infrastructure or persistence failures without marking the event complete; delivery retries shall reuse the same event ID. Authentication and payload/path validation failures shall return 4xx.

### FR-6 Idempotency
1. The system shall compute a checksum for each canonical document.
2. The system shall skip target update when key and checksum are unchanged.
3. Repeated runs with unchanged inputs shall produce identical target state.

### FR-7 Error Handling and Reporting
1. The system shall continue processing other documents when one document fails.
2. The system shall classify errors at minimum as validation, source access, connector/transient, and unexpected.
3. The system shall produce a run summary with total discovered, succeeded, skipped, and failed counts.
4. The system shall include per-document error details: source path, error class, and reason.

### FR-8 Rate-Limit Backoff
1. The system shall detect rate-limit/throttling responses.
2. The system shall apply exponential backoff with jitter before retry attempts.
3. The system shall retry transient connector failures up to configured maximum attempts.
4. The system shall mark operation failed with retry-exhausted reason after exceeding retry policy.

## 6. Acceptance Criteria (Functional)

### AC-0 Story Intake
1. Given a valid Jira, Confluence, or Word-based story source, when intake is initiated, then the system extracts the title, summary, actors, requirements context, and acceptance criteria into a normalized structure.
2. Given missing or ambiguous source details, when the story is reviewed, then the system identifies the gaps and asks for clarification instead of inventing a requirement.
3. Given an unauthorized or unavailable external source, when intake is attempted, then the system returns a clear configuration or access error and stops before producing unverified requirements.

### AC-0A Tour Booking Interface (SCRUM-6)
1. Given the page is loaded, then the booking form and the Tour Summary, Download Brochure, and Support panels are present, with the three panels in that DOM order.
2. Given a narrow viewport causes a single-column layout, then the three panels remain visually ordered Tour Summary, Download Brochure, Support.
3. Given the booking form is submitted, then the default navigation/reload is prevented.
4. Given the page is loaded, then the brochure button is enabled, the helper text is visible, and no inline error is shown.

### AC-0B Brochure Download (SCRUM-6)
1. Given the page is loaded without `simulate_error=true`, when the brochure button is clicked, then a direct download is initiated with suggested filename `tour-brochure.pdf` and MIME type `application/pdf`, without opening a new tab or window.
2. Given the page is loaded with `simulate_error=true`, when the brochure button is clicked, then no download is initiated and the exact error text appears under the helper text in an element with `role="alert"` and `data-testid="brochure-error"`.
3. Given a simulated error is visible, when the button is clicked again, then the error is cleared synchronously at the beginning of that attempt and is shown again when the simulated failure occurs.
4. Given a successful download attempt, then the object URL is revoked 100 milliseconds after the temporary anchor is clicked.

### AC-1 Source Discovery
1. Given configured source paths with mixed file types, when sync runs, then only .md files are selected.
2. Given include/exclude patterns, when sync runs, then only files matching effective scope are processed.

### AC-2 Frontmatter Parsing
1. Given a valid Markdown file with YAML frontmatter, when sync runs, then metadata and body are parsed successfully.
2. Given malformed YAML frontmatter, when sync runs, then file is marked failed with validation error and run continues.
3. Given a file without frontmatter, when sync runs, then it is marked failed with a validation error for missing required metadata, and the run continues.

### AC-3 CLI Trigger
1. Given operator runs full CLI sync, when command completes, then summary includes success, skipped, and failed counts.
2. Given operator runs path-scoped CLI sync, when command completes, then only scoped files are processed.

### AC-4 Event Trigger
1. Given a valid repository event for changed docs, when webhook is received, then only relevant docs are synced.
2. Given duplicate event delivery, when same event is reprocessed, then no duplicate target writes occur.
3. Given a version 1 event with `event_id`, `repository_id`, and `changed_paths`, when a valid signed request within the 5-minute tolerance is received, then the event is eligible for processing.
4. Given an invalid signature, stale timestamp, invalid schema/path, request body larger than 1 MiB, or more than 100 changed paths, when a request is received, then it is rejected with a 4xx response before sync processing.
5. Given all paths have terminal outcomes and failures are durably recorded, when processing completes, then the receiver returns 2xx; a completed duplicate is acknowledged without repeating writes.
6. Given an infrastructure or persistence failure prevents terminal completion, when the request is handled, then the receiver returns 5xx and leaves the event eligible for retry with the same event ID.

### AC-5 Idempotency
1. Given unchanged source docs across runs, when sync reruns, then target writes are skipped for unchanged docs.
2. Given changed content or metadata, when sync reruns, then target record is updated once by deterministic key.

### AC-6 Missing File Handling
1. Given an event references a missing file, when sync runs, then error is recorded as file-not-found and run continues.

### AC-7 Rate-Limit Backoff
1. Given target returns throttling/rate-limit response, when sync attempts write, then exponential backoff with jitter is applied.
2. Given retries are exhausted, when write still fails, then failure is recorded with retry-exhausted classification.

## 7. Non-Functional Requirements

### NFR-1 Reliability and Resilience
1. The pipeline shall be idempotent for repeated runs and duplicate events.
2. The pipeline shall isolate document-level failures and continue batch processing.
3. The pipeline shall support dead-letter style failure capture (at minimum persisted failure records).

### NFR-2 Performance
1. For event-triggered runs, processing should begin promptly after event reception under normal load.
2. For CLI full sync, throughput shall be configurable and bounded by connector rate limits.
3. No-change files should avoid unnecessary writes to reduce runtime and API usage.

### NFR-3 Observability
1. The system shall emit structured logs including run_id, document key, and error class.
2. The system shall produce run-level metrics: processed, succeeded, skipped, failed, retries.
3. The system shall support source-to-target traceability for each synced document.

### NFR-4 Security
1. Credentials and tokens shall be sourced from environment/secret manager only.
2. Logs shall avoid exposing secrets or sensitive tokens.
3. Webhook payloads shall be validated before processing.
4. Webhook signatures shall use timestamped HMAC-SHA256 over the exact raw request body, and requests outside the approved timestamp tolerance shall be rejected.

### NFR-5 Maintainability
1. Connector interfaces shall be modular to support replacing mock storage with production registry.
2. Transformation and validation rules shall be configurable with minimal code changes.

## 8. Edge Cases
1. Missing file in source path during run due to concurrent repository change.
2. Empty Markdown file with valid frontmatter.
3. Markdown file without frontmatter.
4. Malformed YAML frontmatter (syntax errors, invalid indentation).
5. Oversized document exceeding target payload limits.
6. Duplicate documents mapping to same deterministic key.
7. Non-UTF8 file content or encoding mismatch.
8. Webhook events arriving out of order.
9. Duplicate webhook deliveries for same commit/event.
10. Partial target outage causing intermittent 5xx responses.
11. Persistent rate-limit responses beyond retry budget.
12. Interrupted sync run and later rerun of same scope.

## 9. Open Configuration Parameters
1. Source include/exclude path patterns.
2. Required frontmatter fields and field types.
3. Checksum algorithm for idempotency.
4. Max retry attempts and retry ceiling.
5. Backoff base delay, multiplier, and jitter range.
6. Concurrency limits for read/transform/write stages.
7. Webhook signing-secret deployment/configuration mechanism.

## 10. Testability Requirements
1. Unit tests shall cover parser, validator, deterministic keying, checksumming, and retry strategy.
2. Integration tests shall cover source-to-target happy path and failure isolation.
3. Resilience tests shall cover rate limits, transient failures, and retry exhaustion.
4. Tests shall validate idempotent behavior across repeated runs and duplicate events.
5. Tests shall verify SCRUM-6 panel order at wide and narrow viewports, form-submit prevention, enabled button/helper visibility, successful download metadata/flow, and simulated failure/error-clearing behavior.

## 11. Exit Criteria for Phase 1
1. CLI and webhook triggers are both operational.
2. Markdown + YAML frontmatter sync works end-to-end to mock storage.
3. Missing files, malformed metadata, and rate limits are handled per requirements.
4. Idempotency is validated through repeated-run test cases.
5. Functional acceptance criteria are demonstrably satisfied.

## 12. SCRUM-6 Scope Assumptions and Open Decisions

- Confirmed by the user: SCRUM-6 is intentionally included in this repository's requirements scope.
- The story specifies a static UI with no backend/network dependency; the user confirmed it is an isolated companion app, independent of sync execution.
- The approved target location is `apps/tour_booking/index.html`, resolving the story's root-level path in favor of the repository's application-code boundary.
- Confirmed by the user: a Markdown file without frontmatter fails validation because required metadata is missing; processing continues for other files.
- Confirmed by the user: FR-1A/AC-0 story intake is a product runtime capability. Authorized source integration, upload handling, and normalized-record storage design remain to be defined in architecture.
- Confirmed by the user: normalized story-intake records are retained until explicitly deleted; automatic expiration is not required.
- The implementation plan should include the new static app and its tests; no implementation is included in this requirements or architecture stage.
