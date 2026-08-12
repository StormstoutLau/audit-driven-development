"""v2.7.2 选择性下载 linux kernel 特定 commit 并提取文件.

v2.8 增强: 分批下载 + 断点续传 + 重试机制.

策略 (避免 Windows aux.c 问题和空间爆炸):
  1. 用单个 git repo (linux_kernel), git init + remote add
  2. 对每个 finding 的 commit_hash:
     a. git fetch --depth 1 origin <hash> (只下载该 commit tree)
     b. git show <hash>:<file> > extracted/<hash_prefix>/<file> (只提取需要的文件)
  3. 不做 checkout (避免 Windows 保留文件名问题)
  4. 设置 evidence.repo_local_path = extracted/<hash_prefix>/

v2.8 新增:
  - --batch-size / --batch-delay: 分批下载, 批间延迟缓解网络限流
  - --retry / --retry-delay: 单 commit 失败重试
  - --progress-file: 断点续传, 跳过已下载 commit
  - 原子写入进度文件 (.tmp + replace, 避免 2026-07-04 文件损坏事件重演)

空间优化: 每处理 gc-interval 个 commit 后 git gc --prune=now 清理旧对象.

用法:
  python scripts/download_linux_commits.py --max-download 50
  python scripts/download_linux_commits.py --batch-size 50 --batch-delay 60 --retry 3
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST_BASE = ROOT / "docs/benchmark/oss-cache/bigvul-repos/linux_extracted"
LINUX_REPO = ROOT / "docs/benchmark/oss-cache/bigvul-repos/_linux_kernel"

DEFAULT_PROGRESS_FILE = ROOT / "docs/benchmark/oss-cache/bigvul-repos/linux_download_progress.json"


def init_linux_repo():
    """初始化 linux kernel git repo (如果不存在)."""
    if not LINUX_REPO.exists():
        LINUX_REPO.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=str(LINUX_REPO),
                       capture_output=True, timeout=10)
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/torvalds/linux"],
            cwd=str(LINUX_REPO), capture_output=True, timeout=10,
        )
        print(f"Initialized linux repo at {LINUX_REPO}")
    return LINUX_REPO


def fetch_commit(repo_path, commit_hash, timeout=300):
    """Fetch 单个 commit (depth=1)."""
    r = subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", commit_hash],
        cwd=str(repo_path), capture_output=True, text=True, timeout=timeout,
    )
    return r.returncode == 0, r.stderr[:200] if r.stderr else ""


def extract_file(repo_path, commit_hash, file_path, dest_dir):
    """用 git show 提取单个文件到 dest_dir.

    Returns:
        (success, content_or_error)
    """
    # 用 git show 读取文件内容
    r = subprocess.run(
        ["git", "show", f"{commit_hash}:{file_path}"],
        cwd=str(repo_path), capture_output=True, timeout=30,
    )
    if r.returncode != 0:
        return False, r.stderr.decode("utf-8", errors="replace")[:100]

    # 写入目标文件
    dest_file = dest_dir / file_path
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    dest_file.write_bytes(r.stdout)
    return True, len(r.stdout)


def gc_repo(repo_path):
    """清理 git 对象以节省空间."""
    subprocess.run(
        ["git", "gc", "--prune=now", "--quiet"],
        cwd=str(repo_path), capture_output=True, timeout=120,
    )


# ════════════════════════════════════════════════════════════
# v2.8: 断点续传 + 分批 + 重试
# ════════════════════════════════════════════════════════════


def load_progress(progress_path):
    """v2.8: 加载进度文件, 返回 {commit_hash: status} dict.

    Args:
        progress_path: Path 进度文件路径

    Returns:
        dict: {commit_hash: status} 映射. 文件不存在或损坏时返回空字典.
    """
    if not progress_path.exists():
        return {}
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
        return {item["commit"]: item["status"] for item in data.get("downloaded", [])}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def save_progress(progress_path, progress):
    """v2.8: 保存进度到文件 (原子写入).

    使用 .tmp + replace() 原子写入, 避免写入中断导致文件损坏
    (遵循 Operational Safety Rules, 见 project_memory).

    Args:
        progress_path: Path 进度文件路径
        progress: dict {commit_hash: status}
    """
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    # 原子写入: 先写 .tmp 再 rename
    tmp_path = progress_path.with_suffix(".tmp")
    data = {"downloaded": [{"commit": k, "status": v} for k, v in progress.items()]}
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(progress_path)  # 原子 rename


def process_single_finding(f, repo_path, dest_base):
    """v2.8: 处理单个 finding — fetch commit + extract file + 更新 evidence.

    从原 main() L115-L152 循环体提取, 供 batch_download() 调用.

    Args:
        f: dict, finding (会被 in-place 修改 evidence)
        repo_path: Path, linux kernel git repo
        dest_base: Path, extraction destination base

    Returns:
        tuple: (success: bool, error: str)
            - success=True 时 error 为空字符串
            - success=False 时 error 含失败原因
    """
    evidence = f.get("evidence", {})
    commit_hash = evidence.get("commit_hash", "")
    file_path = evidence.get("file", "")

    if not commit_hash or not file_path:
        return False, "missing commit_hash or file_path"

    # 1. Fetch commit
    ok, err = fetch_commit(repo_path, commit_hash)
    if not ok:
        return False, f"fetch failed: {err}"

    # 2. 提取文件
    hash_prefix = commit_hash[:12]
    dest_dir = dest_base / hash_prefix
    ok, info = extract_file(repo_path, commit_hash, file_path, dest_dir)
    if not ok:
        return False, f"extract failed: {info}"

    # 3. 更新 finding 的 repo_local_path
    evidence["repo_local_path"] = str(dest_dir.resolve())
    evidence["file_fix_status"] = "linux_extracted"
    f["evidence"] = evidence
    return True, ""


def batch_download(findings, repo_path, dest_base, batch_size=50, batch_delay=60,
                   retry=3, retry_delay=30, progress=None, gc_interval=10):
    """v2.8: 分批下载, 批间延迟, 带重试和断点续传.

    Args:
        findings: list of finding dicts
        repo_path: Path, linux kernel git repo
        dest_base: Path, extraction destination base
        batch_size: int, commits per batch (default 50)
        batch_delay: int, delay between batches in seconds (default 60)
        retry: int, max attempts per commit (default 3)
        retry_delay: int, delay between retries in seconds (default 30)
        progress: dict {commit_hash: status} for resume (None → 空字典)
        gc_interval: int, run git gc every N commits (default 10)

    Returns:
        tuple: (success_count, fail_count)
    """
    if progress is None:
        progress = {}

    total = len(findings)
    if total == 0:
        return 0, 0

    batches = [findings[i:i + batch_size] for i in range(0, total, batch_size)]
    success = 0
    fail = 0
    processed = 0

    for batch_idx, batch in enumerate(batches):
        print(f"Batch {batch_idx + 1}/{len(batches)}: {len(batch)} commits")

        for f in batch:
            processed += 1
            evidence = f.get("evidence", {})
            commit_hash = evidence.get("commit_hash", "")
            fid = f.get("id", "")

            # 断点续传: 跳过已下载 commit
            if commit_hash and progress.get(commit_hash) == "ok":
                print(f"  [{processed}/{total}] {fid}: SKIP (already downloaded)")
                success += 1
                continue

            print(f"  [{processed}/{total}] {fid}: {commit_hash[:12]}")

            # 重试逻辑
            last_error = ""
            for attempt in range(retry):
                ok, err = process_single_finding(f, repo_path, dest_base)
                if ok:
                    last_error = ""
                    break
                last_error = err
                if attempt < retry - 1:
                    time.sleep(retry_delay)

            if not last_error:
                success += 1
                progress[commit_hash] = "ok"
                print(f"    OK")
            else:
                fail += 1
                progress[commit_hash] = f"fail:{last_error[:50]}"
                print(f"    FAIL: {last_error}")

            # 定期 gc (非致命: gc 是空间优化, 失败不应中断下载)
            if processed % gc_interval == 0:
                try:
                    gc_repo(repo_path)
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
                    pass

        # 批间延迟 (最后一批不延迟)
        if batch_idx < len(batches) - 1 and batch_delay > 0:
            print(f"  Batch delay: {batch_delay}s...")
            time.sleep(batch_delay)

    return success, fail


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Download linux kernel commits and extract files")
    # v2.7.2 参数 (保留, 向后兼容)
    parser.add_argument("--max-download", type=int, default=50,
                        help="Max commits to download (default: 50)")
    parser.add_argument("--gc-interval", type=int, default=10,
                        help="Run git gc every N commits (default: 10)")
    # v2.8 新增参数
    parser.add_argument("--batch-size", type=int, default=50,
                        help="Commits per batch (default: 50)")
    parser.add_argument("--batch-delay", type=int, default=60,
                        help="Delay between batches in seconds (default: 60)")
    parser.add_argument("--retry", type=int, default=3,
                        help="Retry attempts per commit (default: 3)")
    parser.add_argument("--retry-delay", type=int, default=30,
                        help="Delay between retries in seconds (default: 30)")
    parser.add_argument("--progress-file", type=str,
                        default=str(DEFAULT_PROGRESS_FILE),
                        help="Progress file for resume")
    args = parser.parse_args()

    # 加载 findings
    findings_path = ROOT / "docs/benchmark/bigvul/findings.json"
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    findings = data.get("findings", data) if isinstance(data, dict) else data

    # 筛选 linux findings (排除 unknown.c)
    linux_findings = [
        f for f in findings
        if f.get("evidence", {}).get("project") == "linux"
        and f.get("evidence", {}).get("file", "") != "unknown.c"
        and f.get("evidence", {}).get("commit_hash", "")
    ]
    print(f"Linux findings (with file path): {len(linux_findings)}")
    print(f"Max download: {args.max_download}")
    print(f"Batch: size={args.batch_size}, delay={args.batch_delay}s")
    print(f"Retry: {args.retry} attempts, delay={args.retry_delay}s")

    # 限制下载数量 (--max-download 保留, 向后兼容)
    to_download = linux_findings[:args.max_download]

    # 初始化 repo
    repo_path = init_linux_repo()

    # v2.8: 加载进度文件 (断点续传)
    progress_path = Path(args.progress_file)
    progress = load_progress(progress_path)
    if progress:
        print(f"Resumed from progress: {len(progress)} commits already processed")

    # v2.8: 分批下载
    success, fail = batch_download(
        to_download, repo_path=repo_path, dest_base=DEST_BASE,
        batch_size=args.batch_size, batch_delay=args.batch_delay,
        retry=args.retry, retry_delay=args.retry_delay,
        progress=progress, gc_interval=args.gc_interval,
    )

    # v2.8: 保存进度
    save_progress(progress_path, progress)

    # 写回 findings.json
    if isinstance(data, dict):
        data["findings"] = findings
        findings_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    else:
        findings_path.write_text(json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")

    # 更新 ground_truth
    gt_path = ROOT / "docs/benchmark/bigvul/ground_truth.json"
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    upgraded = 0
    for g in gt:
        if g.get("id") in {f.get("id", "") for f in to_download if f.get("evidence", {}).get("file_fix_status") == "linux_extracted"}:
            if g.get("ground_truth") == "real_bug_no_repo":
                g["ground_truth"] = "real_bug"
                g["note"] = "Linux commit downloaded in v2.8"
                upgraded += 1
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")

    # 最终 gc
    gc_repo(repo_path)

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Success: {success}")
    print(f"  Fail: {fail}")
    print(f"  Ground truth upgraded: {upgraded}")
    print(f"  Total processed: {success + fail}")
    print(f"  Progress saved: {progress_path}")


if __name__ == "__main__":
    main()
