"""Open-source benchmark project syncer. v2.3 Detection Track.

Usage: python scripts/benchmark_syncer.py
         --project <fastapi|flask|requests|django>
         --output <new_benchmark.json>
         [--dry-run]

Performance cap: 120s (network I/O for clone/pull).
Manual trigger only — no automatic scheduling (ROADMAP constraint).
"""

import argparse, json, sys, subprocess, tempfile, shutil
from pathlib import Path
from _script_utils import run_script

OSS_PROJECTS = {
    "fastapi": "https://github.com/fastapi/fastapi.git",
    "flask": "https://github.com/pallets/flask.git",
    "requests": "https://github.com/psf/requests.git",
    "django": "https://github.com/django/django.git",
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True, choices=list(OSS_PROJECTS.keys()))
    parser.add_argument("--output", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"Would sync {args.project} from {OSS_PROJECTS[args.project]}")
        return 0

    repo_url = OSS_PROJECTS[args.project]
    tmpdir = Path(tempfile.mkdtemp(prefix="add_sync_"))
    try:
        subprocess.run(
            ["git", "clone", "--depth=100", repo_url, str(tmpdir)],
            capture_output=True, text=True, timeout=60, cwd=str(tmpdir.parent)
        )
        result = subprocess.run(
            ["git", "-C", str(tmpdir), "log", "--since=30 days ago",
             "--grep=fix|security|CVE", "--oneline"],
            capture_output=True, text=True, timeout=15
        )
        bugs = [
            {"id": f"NEW-{i+1}",
             "description": p[1][:150] if len(p := line.split(" ", 1)) > 1 else line.strip()[:150],
             "commit": p[0]}
            for i, line in enumerate(result.stdout.strip().split("\n"))
            if line.strip()
        ]
        output = {
            "project": args.project,
            "synced_date": "manual-trigger",
            "new_bugs_found": len(bugs),
            "known_bugs": bugs
        }
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"benchmark_syncer: {args.project} — {len(bugs)} new potential bugs")
    finally:
        shutil.rmtree(str(tmpdir), ignore_errors=True)
    return 0

if __name__ == "__main__":
    run_script(main)
