"""Defects4J active-bugs CSV 富集器.

读取 Defects4J 真实 active-bugs.csv (列: bug.id,revision.id.buggy,
revision.id.fixed,report.id,report.url), 从 GitHub 获取 fix commit 的
diff, 提取 file_path 与 line_start, 输出为 defects4j_to_findings.py
所需的 CSV 格式:

    project,bug_id,commit_hash,commit_message,file_path,line_start

仅处理 git-based 项目 (Cli/Codec/Csv 等), Chart 等基于 SVN 的项目
无法从 GitHub 获取 diff 故跳过.

用法:
  python scripts/enrich_defects4j.py <data_dir> --output <enriched.csv> [--max-bugs 50]
"""
import csv
import json
import re
import sys
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path


# ── 项目 → GitHub 仓库映射 ──────────────────────────────────
# 仅包含 git-based 项目 (revision.id 为 40 字符 git commit hash)
PROJECT_REPOS = {
    "Cli": "apache/commons-cli",
    "Codec": "apache/commons-codec",
    "Csv": "apache/commons-csv",
    "Lang": "apache/commons-lang",
    "Math": "apache/commons-math",
    "Gson": "google/gson",
    "JacksonCore": "FasterXML/jackson-core",
    "JacksonDatabind": "FasterXML/jackson-databind",
    "JacksonXml": "FasterXML/jackson-dataformat-xml",
    "Jsoup": "jhy/jsoup",
    "Mockito": "mockito/mockito",
    "Collections": "apache/commons-collections",
    "Compress": "apache/commons-compress",
    "JxPath": "apache/commons-jxpath",
    "Time": "JodaOrg/joda-time",
}

# diff 文件路径正则: diff --git a/<path> b/<path>
_DIFF_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$")

# hunk 头正则: @@ -<start>,<count> +<start>,<count> @@
_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def extract_file_line_from_diff(diff_text):
    """从 git diff 中提取第一个文件的路径与第一个 hunk 的旧行号.

    Args:
        diff_text: git diff 文本

    Returns:
        (file_path, line_start) 或 None
    """
    if not diff_text:
        return None

    file_path = None
    for line in diff_text.splitlines():
        m = _DIFF_FILE_RE.match(line)
        if m and file_path is None:
            # 取 b/ 路径 (修改后)
            file_path = m.group(2)
            continue
        # 找到第一个 hunk 行
        hm = _HUNK_RE.match(line)
        if hm and file_path is not None:
            line_start = int(hm.group(1))
            return (file_path, line_start)

    if file_path:
        # 有文件但没找到 hunk, 返回默认行号
        return (file_path, 1)
    return None


def fetch_diff(repo, commit_hash, timeout=12):
    """从 GitHub 获取 commit 的 diff 文本.

    Args:
        repo: GitHub 仓库 (如 "apache/commons-cli")
        commit_hash: fix commit hash
        timeout: 超时秒数

    Returns:
        diff 文本字符串, 失败返回 None
    """
    url = f"https://github.com/{repo}/commit/{commit_hash}.diff"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "defects4j-enricher/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return None
    except Exception:
        return None


def is_git_hash(value):
    """判断 revision.id 是否为 git commit hash (40 字符 hex)."""
    if not value:
        return False
    if len(value) != 40:
        return False
    try:
        int(value, 16)
        return True
    except ValueError:
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Enrich Defects4J active-bugs CSV with file_path and line_start")
    parser.add_argument("data_dir",
                        help="Directory containing per-project active-bugs CSV files")
    parser.add_argument("--output", required=True,
                        help="Output enriched CSV path")
    parser.add_argument("--max-bugs", type=int, default=50,
                        help="Maximum number of bugs to enrich (default: 50)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Delay between diff fetches in seconds (default: 1.0)")
    parser.add_argument("--log", default=None,
                        help="Optional enrichment log JSON path")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 收集所有 git-based 项目的 bug
    all_bugs = []
    for csv_file in sorted(data_dir.glob("*-active-bugs.csv")):
        project = csv_file.name.replace("-active-bugs.csv", "")
        if project not in PROJECT_REPOS:
            continue
        repo = PROJECT_REPOS[project]
        with open(csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fix_hash = row.get("revision.id.fixed", "")
                if not is_git_hash(fix_hash):
                    continue
                all_bugs.append({
                    "project": project,
                    "repo": repo,
                    "bug_id": row.get("bug.id", ""),
                    "commit_hash": fix_hash,
                    "report_id": row.get("report.id", ""),
                    "report_url": row.get("report.url", ""),
                })

    print(f"Found {len(all_bugs)} git-based bugs across "
          f"{len(set(b['project'] for b in all_bugs))} projects", flush=True)

    enriched = []
    log_entries = []
    fetched = 0
    failed = 0

    for bug in all_bugs:
        if len(enriched) >= args.max_bugs:
            break

        diff_text = fetch_diff(bug["repo"], bug["commit_hash"])
        result = extract_file_line_from_diff(diff_text) if diff_text else None

        if result:
            file_path, line_start = result
            # commit_message: 报告 ID + URL
            commit_message = f"{bug['report_id']} {bug['report_url']}".strip()
            enriched.append({
                "project": bug["project"],
                "bug_id": bug["bug_id"],
                "commit_hash": bug["commit_hash"],
                "commit_message": commit_message,
                "file_path": file_path,
                "line_start": line_start,
            })
            fetched += 1
            print(f"  [{len(enriched):2d}/{args.max_bugs}] {bug['project']}/{bug['bug_id']} "
                  f"-> {file_path}:{line_start}", flush=True)
        else:
            failed += 1
            log_entries.append({
                "project": bug["project"],
                "bug_id": bug["bug_id"],
                "commit_hash": bug["commit_hash"],
                "error": "diff fetch or parse failed",
            })
            print(f"  SKIP {bug['project']}/{bug['bug_id']} (fetch/parse failed)", flush=True)

        time.sleep(args.delay)

    # 写出富集后的 CSV
    fieldnames = [
        "project", "bug_id", "commit_hash",
        "commit_message", "file_path", "line_start",
    ]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in enriched:
            writer.writerow(row)

    # 写出富集日志 (可选)
    if args.log:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            json.dumps({
                "total_git_bugs": len(all_bugs),
                "enriched": len(enriched),
                "fetch_failed": failed,
                "failures": log_entries,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    print(f"\nEnrichment complete:")
    print(f"  Output: {out_path}")
    print(f"  Enriched bugs: {len(enriched)}")
    print(f"  Failed: {failed}")

    return {"enriched": len(enriched), "failed": failed}


if __name__ == "__main__":
    main()
