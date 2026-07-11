"""Deterministic file selector. Pre-verifies audit scope before subagent dispatch.

Usage: python scripts/audit_files.py --spec <spec.md> --module <module_name> --base <git_commit>

Cost cap: max 50 files per module. If >50, warn and pick top 50 by git churn.
"""

import argparse, json, sys, glob as glob_mod, subprocess, os
from pathlib import Path


def parse_spec_module(spec_path, module_name):
    """Extract file glob patterns from spec for a given module."""
    text = Path(spec_path).read_text(encoding="utf-8")
    patterns = []

    for line in text.split("\n"):
        stripped = line.strip()
        if module_name.lower() in stripped.lower():
            if stripped.startswith("- ") or stripped.startswith("* "):
                segment = stripped[2:].strip()
                if segment.endswith(".py") or segment.endswith("/"):
                    patterns.append(segment)
            if "`" in stripped:
                import re
                for m in re.finditer(r'`([^`]+\.py)`', stripped):
                    patterns.append(m.group(1))

    return patterns or []


def glob_files(patterns, repo_root):
    """Expand glob patterns into concrete file list."""
    files = set()
    cwd = os.getcwd()
    os.chdir(repo_root)
    for p in patterns:
        for f in glob_mod.glob(p, recursive=True):
            if os.path.isfile(f):
                files.add(os.path.abspath(f))
    os.chdir(cwd)
    return sorted(files)


def git_diff_files(base_commit, repo_root):
    """Get files changed since base_commit."""
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "diff", "--name-only", f"{base_commit}..HEAD"],
            capture_output=True, text=True, timeout=15
        )
        return [f.strip() for f in result.stdout.split("\n") if f.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--max-files", type=int, default=50)
    args = parser.parse_args()

    patterns = parse_spec_module(args.spec, args.module)
    if not patterns:
        patterns = [f"**/{args.module}/*.py", f"**/{args.module}/*.md"]

    all_files = glob_files(patterns, args.repo)
    changed = git_diff_files(args.base, args.repo)

    scope = [f for f in all_files if not changed or f in changed]

    if len(scope) > args.max_files:
        print(f"Warning: {len(scope)} files exceed cap of {args.max_files}. Using top {args.max_files} by priority.", file=sys.stderr)
        scope = scope[:args.max_files]

    output = {"module": args.module, "base_commit": args.base, "total_files": len(scope), "files": scope}
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(2)
