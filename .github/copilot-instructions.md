# Agentic SDLC Guidelines: Automated Documentation Sync

## Context & Architecture
- Follow all requirements documented in requirements.md and architecture.md.
- Ensure event-driven components are idempotent, resilient, and include dead-letter/error handling.
- Never commit hardcoded secrets, credentials, or environment tokens.

## Code & Test Standards
- All application code resides in apps/ and shared/.
- Tests must reside under tests/ (unit, integration, resilience).
- Follow TDD and DRY principles across implementations.
