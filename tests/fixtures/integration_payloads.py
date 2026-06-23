from __future__ import annotations


def build_merge_event() -> dict:
    return {
        "event_type": "merge_completed",
        "repository": "example/repo",
        "branch": "main",
        "merge_sha": "integration-sha-001",
        "changed_files": ["docs/guide.md", "src/service.py"],
    }


def build_headers() -> dict:
    return {
        "X-Signature": "valid-signature",
        "X-Event-Id": "evt-integration-001",
    }
