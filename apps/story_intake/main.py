from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from apps.story_intake.parser import parse_word_story
from apps.story_intake.store import StoryRecordStore
from shared.errors.exceptions import SyncError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local requirements story intake")
    commands = parser.add_subparsers(dest="command", required=True)
    intake = commands.add_parser("word", help="normalize a labeled Word .docx story")
    intake.add_argument("path")
    delete = commands.add_parser("delete", help="explicitly delete a retained story record")
    delete.add_argument("record_id")
    commands.add_parser("list", help="list retained normalized story records")
    for provider in ("jira", "confluence"):
        external = commands.add_parser(provider, help=f"{provider} integration (not configured)")
        external.add_argument("reference")
    args = parser.parse_args(argv)
    if args.command in {"jira", "confluence"}:
        print(json.dumps({
            "error": "integration_unavailable",
            "source": args.command,
            "message": "No authorized read-only integration is configured; no external request was made.",
        }))
        return 2

    try:
        store = StoryRecordStore(os.getenv("STORY_DATABASE_PATH", ".story-intake/records.sqlite3"))
        if args.command == "word":
            story = parse_word_story(Path(args.path))
            store.add(story)
            print(json.dumps(story.to_dict(), ensure_ascii=False))
            return 0
        if args.command == "delete":
            deleted = store.delete(args.record_id)
            print(json.dumps({"record_id": args.record_id, "deleted": deleted}))
            return 0 if deleted else 1
        print(json.dumps(store.list_records(), ensure_ascii=False))
        return 0
    except SyncError as exc:
        print(json.dumps({"error": exc.code.value, "message": exc.message}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
