from __future__ import annotations

import argparse
import logging
from pathlib import Path

from apps.sync_service.persistence.sqlite_store import SqliteSyncState
from apps.sync_service.orchestrator import SyncOrchestrator
from apps.sync_service.reliability.dlq import JsonlDlqStore
from apps.sync_service.reliability.retry import RetryConfig
from shared.config.settings import load_settings_from_env
from shared.errors.exceptions import ConfigError


def _build_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated Documentation Sync CLI")
    parser.add_argument("--path", action="append", default=[], help="relative markdown path to scope sync")
    parser.add_argument(
        "--trigger",
        default="cli",
        choices=("cli", "event"),
        help="trigger type for observability",
    )
    parser.add_argument("--event-id", default=None, help="event id for deduplication")
    parser.add_argument("--dlq-path", default=None, help="path to dead-letter JSONL file")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint for synchronized markdown ingestion."""
    args = _build_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        settings = load_settings_from_env()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    try:
        state = SqliteSyncState(settings.database_path)
        dlq_path = Path(args.dlq_path) if args.dlq_path else Path(settings.database_path).parent / "dlq.jsonl"
        orchestrator = SyncOrchestrator(
            target=state,
            idempotency_store=state,
            event_ledger=state,
            dlq_store=JsonlDlqStore(dlq_path),
            retry_config=RetryConfig(
                max_attempts=settings.retry_policy.max_attempts,
                base_delay_ms=settings.retry_policy.base_delay_ms,
                max_delay_ms=settings.retry_policy.max_delay_ms,
            ),
        )
    except Exception as exc:
        print(f"Persistence/configuration error: {exc}")
        return 2

    try:
        summary = orchestrator.run(
            repository_id=settings.repository_id,
            source_root=settings.source_root,
            include_patterns=settings.include_patterns,
            exclude_patterns=settings.exclude_patterns,
            trigger_type=args.trigger,
            event_id=args.event_id,
            path_scope=tuple(args.path) if args.path else None,
        )
    except Exception as exc:
        print(f"Sync infrastructure error: {exc}")
        return 2

    print(f"run_id={summary.run_id}")
    print(
        "summary "
        f"discovered={summary.discovered_count} "
        f"processed={summary.processed_count} "
        f"succeeded={summary.succeeded_count} "
        f"skipped={summary.skipped_count} "
        f"failed={summary.failed_count} "
        f"retries={summary.retry_count} "
        f"duration_ms={summary.duration_ms} "
        f"dlq={summary.dlq_count}"
    )

    return 0 if summary.failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
