"""
issues.json state machine: open → in_progress → fixed → verified

Commands:
  python scripts/issues_tracker.py init <audit_report.json>
    → Generate issues.json from AuditReport findings
    → All issues start as status="open"
    → Preserves spec_ref from AuditFinding (required for --verify)

  python scripts/issues_tracker.py status --id <finding_id> --to <status>
    → Transition an issue: open/in_progress/fixed/verified

  python scripts/issues_tracker.py verify --file <file_path> [--report <audit_output.json>]
    → Re-audit the specified file against its spec section (from issues.json's spec_ref field)
    → Each open issue in issues.json includes spec_ref for this purpose
    → Compare new findings with existing issues.json
    → If previously-open issue NOT in new findings → status → "verified"
    → If previously-open issue STILL in new findings → status remains, warn user

  python scripts/issues_tracker.py summary
    → Print: open=X, in_progress=Y, fixed=Z, verified=W
"""

import json
import sys
from pathlib import Path

ISSUES_FILE = Path("docs/audit/issues.json")


def cmd_init(report_path: str):
    """Generate issues.json from an AuditReport JSON."""
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    issues = []
    for module in report.get("module_results", []):
        for finding in module.get("findings", []):
            issues.append({
                "id": finding["id"],
                "file": finding["evidence"]["file"],
                "line": finding["evidence"]["line_start"],
                "severity": finding["severity"],
                "category": finding["category"],
                "spec_ref": finding.get("spec_ref", ""),
                "claim": finding.get("claim", ""),
                "status": "open",
                "fix_commit": None,
                "verified_at": None
            })

    for module in report.get("cross_module_results", []):
        for finding in module.get("findings", []):
            issues.append({
                "id": finding["id"],
                "file": finding["evidence"]["file"],
                "line": finding["evidence"]["line_start"],
                "severity": finding["severity"],
                "category": finding["category"],
                "spec_ref": finding.get("spec_ref", ""),
                "claim": finding.get("claim", ""),
                "status": "open",
                "fix_commit": None,
                "verified_at": None
            })

    output = {
        "audit_id": report.get("audit_metadata", {}).get("audit_date", "unknown"),
        "issues": issues
    }

    ISSUES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ISSUES_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Created {ISSUES_FILE} with {len(issues)} issues (all status=open)")


def cmd_status(finding_id: str, to_status: str):
    """Transition an issue's status."""
    valid_statuses = {"open", "in_progress", "fixed", "verified"}
    if to_status not in valid_statuses:
        print(f"ERROR: Invalid status '{to_status}'. Must be one of: {valid_statuses}")
        sys.exit(1)

    data = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))
    found = False
    for issue in data["issues"]:
        if issue["id"] == finding_id:
            old = issue["status"]
            issue["status"] = to_status
            if to_status == "verified":
                import datetime
                issue["verified_at"] = datetime.datetime.now().isoformat()
            print(f"{finding_id}: {old} → {to_status}")
            found = True
            break

    if not found:
        print(f"ERROR: Issue '{finding_id}' not found in {ISSUES_FILE}")
        sys.exit(1)

    ISSUES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def cmd_verify(file_path: str, report_path: str = None):
    """Verify that previously-open issues in a file are no longer present in a new audit report."""
    data = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))

    issues_for_file = [i for i in data["issues"] if i["file"] == file_path and i["status"] in ("open", "in_progress", "fixed")]

    if not issues_for_file:
        print(f"No open/in_progress/fixed issues found for file: {file_path}")
        return

    if report_path:
        new_report = json.loads(Path(report_path).read_text(encoding="utf-8"))
        new_finding_ids = set()
        for module in new_report.get("module_results", []):
            for f in module.get("findings", []):
                new_finding_ids.add(f["id"])
        for module in new_report.get("cross_module_results", []):
            for f in module.get("findings", []):
                new_finding_ids.add(f["id"])

        for issue in issues_for_file:
            if issue["id"] not in new_finding_ids:
                issue["status"] = "verified"
                import datetime
                issue["verified_at"] = datetime.datetime.now().isoformat()
                print(f"✅ {issue['id']}: verified (no longer found in re-audit)")
            else:
                print(f"⚠️  {issue['id']}: STILL present in re-audit — fix incomplete")

        ISSUES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        print(f"Files to verify (no --report provided, listing only):")
        for issue in issues_for_file:
            print(f"  {issue['id']}: {issue['file']}:{issue['line']} — {issue['status']} | spec_ref: {issue['spec_ref']}")


def cmd_summary():
    """Print issue status summary."""
    data = json.loads(ISSUES_FILE.read_text(encoding="utf-8"))
    counts = {"open": 0, "in_progress": 0, "fixed": 0, "verified": 0}
    for issue in data["issues"]:
        counts[issue["status"]] = counts.get(issue["status"], 0) + 1

    total = sum(counts.values())
    print(f"Audit: {data.get('audit_id', 'unknown')}")
    print(f"Total issues: {total}")
    for status, count in counts.items():
        bar = "█" * (count * 20 // max(total, 1))
        print(f"  {status:12s}: {count:3d}  {bar}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/issues_tracker.py <command> [args...]")
        print("Commands: init, status, verify, summary")
        sys.exit(1)

    command = sys.argv[1]

    if command == "init":
        if len(sys.argv) < 3:
            print("Usage: python scripts/issues_tracker.py init <audit_report.json>")
            sys.exit(1)
        cmd_init(sys.argv[2])

    elif command == "status":
        if len(sys.argv) < 6 or sys.argv[2] != "--id" or sys.argv[4] != "--to":
            print("Usage: python scripts/issues_tracker.py status --id <finding_id> --to <status>")
            sys.exit(1)
        cmd_status(sys.argv[3], sys.argv[5])

    elif command == "verify":
        file_path = None
        report_path = None
        i = 2
        while i < len(sys.argv):
            if sys.argv[i] == "--file" and i + 1 < len(sys.argv):
                file_path = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--report" and i + 1 < len(sys.argv):
                report_path = sys.argv[i + 1]
                i += 2
            else:
                i += 1
        if not file_path:
            print("Usage: python scripts/issues_tracker.py verify --file <file_path> [--report <audit_output.json>]")
            sys.exit(1)
        cmd_verify(file_path, report_path)

    elif command == "summary":
        cmd_summary()

    else:
        print(f"Unknown command: {command}")
        print("Commands: init, status, verify, summary")
        sys.exit(1)
