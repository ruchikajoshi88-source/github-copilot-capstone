import os
from pathlib import Path
import subprocess
import sys


def test_separate_cli_runs_reuse_sqlite_target_and_checksum(tmp_path):
    repository_root = Path(__file__).resolve().parents[2]
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "a.md"
    source.write_text(
        "---\ntitle: A\nsource_path: a.md\nversion: v1\nlast_updated: 2026-09-07\n---\n# first\n",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({
        "SYNC_REPOSITORY_ID": "repo",
        "SYNC_SOURCE_ROOT": str(docs),
        "SYNC_DATABASE_PATH": str(tmp_path / "state.sqlite3"),
    })

    def run_cli():
        return subprocess.run(
            [sys.executable, "-m", "apps.sync_service.main"],
            cwd=repository_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    first = run_cli()
    second = run_cli()
    assert first.returncode == 0, first.stderr + first.stdout
    assert "succeeded=1" in first.stdout
    assert second.returncode == 0, second.stderr + second.stdout
    assert "skipped=1" in second.stdout

    source.write_text(source.read_text(encoding="utf-8").replace("# first", "# changed"), encoding="utf-8")
    third = run_cli()
    assert third.returncode == 0, third.stderr + third.stdout
    assert "succeeded=1" in third.stdout
