"""v2.7.2 批量下载 Big-Vul/CVEfixes 源码 repo.

根据 findings.json 中的 evidence.repo_url / commit_hash / project 字段,
批量下载对应 commit 的源码 repo, 让 real_bug_no_repo 标注升级为 real_bug.

策略 (per finding):
  1. 从 evidence 提取 repo_url + commit_hash
  2. 若 repo_url 为空 (Big-Vul 无 repo_url, 只有 project) → 用 GitHub 搜索:
     git clone https://github.com/<project>/<project>
  3. git clone --depth 1 <repo_url> <dest_dir>
  4. cd <dest_dir> && git fetch --depth 1 origin <commit_hash>
  5. git checkout <commit_hash>
  6. 成功 → ground_truth 从 real_bug_no_repo 升级为 real_bug

失败处理 (不阻塞其他 finding):
  - 网络错误 → 保持 real_bug_no_repo, 记录 reason="network_error"
  - commit 不存在 → 保持 real_bug_no_repo, 记录 reason="commit_not_found"
  - repo_url 为空且 project 无法推断 → 跳过

幂等性: dest_dir 已存在且包含目标 commit → 跳过 clone, 直接 checkout.

用法:
  python scripts/download_repos.py \\
      --findings docs/benchmark/bigvul/findings.json \\
      --ground-truth docs/benchmark/bigvul/ground_truth.json \\
      --dest-dir docs/benchmark/oss-cache/bigvul-repos \\
      [--max-download N] [--dry-run]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from _script_utils import run_script


# GitHub URL 推断: project 名 → GitHub repo URL
# 真实 Big-Vul 的 project 字段通常是 GitHub 上的 owner/repo 或纯 repo 名

# v2.7.2: 已知的 project → GitHub owner/repo 映射
# 这些项目的 owner != project name, 需要显式映射
_KNOWN_GITHUB_OWNERS = {
    # 高频项目 (占 Big-Vul 67%)
    "linux": "torvalds/linux",
    # Apache 项目
    "httpd": "apache/httpd",
    # PHP 项目
    "php-src": "php/php-src",
    "php-radius": "freeradius/freeradius-server",
    # Cisco/安全项目
    "clamav-devel": "Cisco-Talos/clamav-devel",
    "ModSecurity": "SpiderLabs/ModSecurity",
    # 其他已知 owner != project 的情况
    "pacemaker": "ClusterLabs/pacemaker",
    "openssh-portable": "openssh/openssh-portable",
    "cryptopp": "weidai11/cryptopp",
    "pigz": "madler/pigz",
    "Little-CMS": "mm2/Little-CMS",
    "ArduinoJson": "bblanchon/ArduinoJson",
    "ippusbxd": "OpenPrinting/ippusbxd",
    "ppp": "paulusmack/ppp",
    "bdwgc": "ivmai/bdwgc",
    "mosh": "mobile-shell/mosh",
    "libreport": "abrt/libreport",
    "irssi-proxy": "irssi/irssi",
    "mongo": "mongodb/mongo",
    "cgminer": "ckolivas/cgminer",
    "passenger": "phusion/passenger",
    "polarssl": "ARMmbed/polarssl",
    "libtiff": "LibTiff/libtiff",
    "openvpn": "OpenVPN/openvpn",
    "ettercap": "Ettercap/ettercap",
    "tcpdump": "the-tcpdump-group/tcpdump",
    "mod_auth_mellon": "latchset/mod_auth_mellon",
    "FreeRDP": "FreeRDP/FreeRDP",
    "mapserver": "MapServer/mapserver",
    "jansson": "akheron/jansson",
    "t1utils": "kohler/t1utils",
    "rawstudio": "rawstudio/rawstudio",
    "trojita": "jktjkt/trojita",
    "znc": "znc/znc",
    "qemu": "qemu/qemu",
    "bitcoin": "bitcoin/bitcoin",
    "redis": "redis/redis",
    "memcached": "memcached/memcached",
    "inspircd": "inspircd/inspircd",
    "mumble": "mumble-voip/mumble",
    "beanstalkd": "beanstalkd/beanstalkd",
    "jabberd2": "jabberd2/jabberd2",
    "teeworlds": "teeworlds/teeworlds",
    "graphviz": "graphviz/graphviz",
    "radvd": "radvd/radvd",
    "corosync": "corosync/corosync",
    "sddm": "sddm/sddm",
    "libuv": "libuv/libuv",
    "libsndfile": "libsndfile/libsndfile",
    "libarchive": "libarchive/libarchive",
    "libmspack": "libmspack/libmspack",
    "json-c": "json-c/json-c",
    "curl": "curl/curl",
    "openssl": "openssl/openssl",
    "krb5": "krb5/krb5",
    "file": "file/file",
    "FFmpeg": "FFmpeg/FFmpeg",
    "hhvm": "hhvm/hhvm",
    "lxc": "lxc/lxc",
    "lxcfs": "lxcfs/lxcfs",
    "LibRaw": "LibRaw/LibRaw",
    "quassel": "quassel/quassel",
    "taglib": "taglib/taglib",
    "miniupnp": "miniupnp/miniupnp",
    "postgres": "postgres/postgres",
    "uzbl": "uzbl/uzbl",
    "sgminer": "sgminer-dev/sgminer",
    "libreswan": "libreswan/libreswan",
    "monkey": "monkey/monkey",
    "abrt": "abrt/abrt",
    "nbd": "NetworkBlockDevice/nbd",
    "ZRTPCPP": "wernerd/ZRTPCPP",
    "raptor": "dajobe/raptor",
    "nedmalloc": "ned14/nedmalloc",
    "tntnet": "maekitalo/tntnet",
    "torque": "adaptivecomputing/torque",
    "libfep": "uim/libfep",
    "tinc": "gslie/tinc",
    "das_watchdog": "9zap/das_watchdog",
    "suhosin": "sektioneins/suhosin",
    "pyfribidi": "eght/pyfribidi",
    "pure-ftpd": "jjsmith5/pure-ftpd",
    "nspluginwrapper": "dsboger/nspluginwrapper",
    "systemd-shim": "gmaslov/systemd-shim",
    "ots": "theparanoids/ots",
    "bootstrap-dht": "jech/bootstrap-dht",
    "webserver": "jeremyhahn/webserver",
    "php-radius": "freeradius/freeradius-server",
}


def _infer_github_url(project):
    """根据 project 名推断 GitHub repo URL.

    Big-Vul 的 project 字段示例: "pango", "php-src", "libpng".
    v2.7.2: 使用 _KNOWN_GITHUB_OWNERS 映射表处理 owner != project 的情况.

    Args:
        project: Big-Vul 的 project 字段

    Returns:
        str: 推断的 GitHub repo URL, 无法推断时返回 ""
    """
    if not project or not project.strip():
        return ""
    project = project.strip()
    # 如果 project 已是完整 URL, 直接返回
    if project.startswith("https://") or project.startswith("git@"):
        return project
    # 如果 project 含 "/" (形如 owner/repo), 直接拼 GitHub
    if "/" in project:
        return f"https://github.com/{project}"
    # v2.7.2: 查已知映射表
    if project in _KNOWN_GITHUB_OWNERS:
        return f"https://github.com/{_KNOWN_GITHUB_OWNERS[project]}"
    # 否则假设 owner == project (常见于 pango/libpng 等同名组织)
    return f"https://github.com/{project}/{project}"


def download_repo(repo_url, commit_hash, dest_dir, timeout=60):
    """下载指定 commit 的源码 repo.

    策略:
      1. 若 dest_dir 已是 git repo 且含目标 commit → 仅 checkout (幂等)
      2. 否则 git clone --depth 1 <repo_url> <dest_dir>
      3. git fetch --depth 1 origin <commit_hash>
      4. git checkout <commit_hash>

    Args:
        repo_url: git repo URL
        commit_hash: 目标 commit hash (完整或短 hash)
        dest_dir: 本地目标目录
        timeout: 每步 git 命令超时秒数

    Returns:
        dict: {"success": bool, "reason": str, "dest_dir": str}
    """
    dest = Path(dest_dir)
    short_hash = commit_hash[:12] if commit_hash else ""

    # 幂等检查: dest_dir 已存在且含目标 commit → 仅 checkout
    if dest.exists() and (dest / ".git").exists():
        try:
            # 检查目标 commit 是否已存在
            r = subprocess.run(
                ["git", "cat-file", "-t", commit_hash],
                cwd=str(dest), capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0 and r.stdout.strip() == "commit":
                # commit 已存在, 仅 checkout
                r = subprocess.run(
                    ["git", "checkout", commit_hash],
                    cwd=str(dest), capture_output=True, text=True, timeout=15,
                )
                if r.returncode == 0:
                    return {"success": True, "reason": "already_cloned",
                            "dest_dir": str(dest)}
                return {"success": False, "reason": f"checkout_failed: {r.stderr[:100]}",
                        "dest_dir": str(dest)}
            # commit 不存在 → 尝试 fetch
            r = subprocess.run(
                ["git", "fetch", "--depth", "1", "origin", commit_hash],
                cwd=str(dest), capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode == 0:
                r = subprocess.run(
                    ["git", "checkout", commit_hash],
                    cwd=str(dest), capture_output=True, text=True, timeout=15,
                )
                if r.returncode == 0:
                    return {"success": True, "reason": "fetched_and_checkedout",
                            "dest_dir": str(dest)}
                return {"success": False, "reason": f"checkout_failed: {r.stderr[:100]}",
                        "dest_dir": str(dest)}
            return {"success": False, "reason": "commit_not_found",
                    "dest_dir": str(dest)}
        except subprocess.TimeoutExpired:
            return {"success": False, "reason": "timeout",
                    "dest_dir": str(dest)}

    # 全新 clone
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(dest)],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode != 0:
            return {"success": False, "reason": f"clone_failed: {r.stderr[:100]}",
                    "dest_dir": str(dest)}

        # fetch 目标 commit
        if commit_hash:
            r = subprocess.run(
                ["git", "fetch", "--depth", "1", "origin", commit_hash],
                cwd=str(dest), capture_output=True, text=True, timeout=timeout,
            )
            if r.returncode != 0:
                return {"success": False, "reason": "commit_not_found",
                        "dest_dir": str(dest)}
            r = subprocess.run(
                ["git", "checkout", commit_hash],
                cwd=str(dest), capture_output=True, text=True, timeout=15,
            )
            if r.returncode != 0:
                return {"success": False, "reason": f"checkout_failed: {r.stderr[:100]}",
                        "dest_dir": str(dest)}

        return {"success": True, "reason": "cloned",
                "dest_dir": str(dest)}
    except subprocess.TimeoutExpired:
        return {"success": False, "reason": "timeout",
                "dest_dir": str(dest)}
    except Exception as e:
        return {"success": False, "reason": f"error: {str(e)[:100]}",
                "dest_dir": str(dest)}


def update_ground_truth(gt_path, downloaded_ids):
    """将下载成功的 finding 的 ground_truth 从 real_bug_no_repo 升级为 real_bug.

    Args:
        gt_path: ground_truth.json 路径
        downloaded_ids: set of finding id 已下载成功

    Returns:
        int: 更新的记录数
    """
    gt_path = Path(gt_path)
    if not gt_path.exists():
        return 0
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    updated = 0
    for gt in data:
        if (gt.get("ground_truth") == "real_bug_no_repo"
                and gt.get("id") in downloaded_ids):
            gt["ground_truth"] = "real_bug"
            gt["note"] = "Repo downloaded in v2.7.2"
            updated += 1
    gt_path.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    return updated


def main():
    parser = argparse.ArgumentParser(
        description="v2.7.2 batch download source repos for Big-Vul/CVEfixes findings")
    parser.add_argument("--findings", required=True,
                        help="Path to findings.json")
    parser.add_argument("--ground-truth", default=None,
                        help="Path to ground_truth.json (default: <findings dir>/ground_truth.json)")
    parser.add_argument("--dest-dir", required=True,
                        help="Destination directory for cloned repos")
    parser.add_argument("--max-download", type=int, default=0,
                        help="Max repos to download (0 = unlimited)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only print what would be downloaded, no actual clone")
    parser.add_argument("--dataset", choices=["bigvul", "cvefixes", "auto"],
                        default="auto",
                        help="Dataset type (determines repo_url inference strategy)")
    args = parser.parse_args()

    findings_path = Path(args.findings)
    gt_path = (Path(args.ground_truth) if args.ground_truth
               else findings_path.parent / "ground_truth.json")
    dest_root = Path(args.dest_dir)
    dest_root.mkdir(parents=True, exist_ok=True)

    # 加载 findings
    data = json.loads(findings_path.read_text(encoding="utf-8"))
    findings = data.get("findings", []) if isinstance(data, dict) else data

    # 自动检测 dataset 类型
    dataset = args.dataset
    if dataset == "auto":
        first_id = findings[0].get("id", "") if findings else ""
        if first_id.startswith("BV-"):
            dataset = "bigvul"
        elif first_id.startswith("CF-"):
            dataset = "cvefixes"
        else:
            dataset = "bigvul"  # 默认

    print(f"download_repos: dataset={dataset}, findings={len(findings)}")
    print(f"  findings: {findings_path}")
    print(f"  ground_truth: {gt_path}")
    print(f"  dest_dir: {dest_root}")
    print(f"  max_download: {args.max_download or 'unlimited'}")
    print(f"  dry_run: {args.dry_run}")

    success_count = 0
    fail_count = 0
    skip_count = 0
    downloaded_ids = set()
    results = []

    for f in findings:
        fid = f.get("id", "")
        evidence = f.get("evidence", {})
        repo_url = evidence.get("repo_url", "")
        commit_hash = evidence.get("commit_hash", "")
        project = evidence.get("project", "")

        # CVEfixes: repo_url 直接可用
        # Big-Vul: repo_url 为空, 用 project 推断
        if not repo_url and dataset == "bigvul":
            repo_url = _infer_github_url(project)

        if not repo_url:
            skip_count += 1
            results.append({"id": fid, "status": "skip", "reason": "no_repo_url"})
            continue

        if not commit_hash:
            skip_count += 1
            results.append({"id": fid, "status": "skip", "reason": "no_commit_hash"})
            continue

        # 目标目录: dest_root / project 或 dest_root / repo_basename
        repo_name = repo_url.rstrip("/").split("/")[-1]
        if repo_name.endswith(".git"):
            repo_name = repo_name[:-4]
        dest_dir = dest_root / f"{repo_name}_{commit_hash[:8]}"

        if args.dry_run:
            print(f"  [DRY-RUN] {fid}: {repo_url}@{commit_hash[:12]} → {dest_dir}")
            results.append({"id": fid, "status": "dry_run",
                            "repo_url": repo_url, "commit_hash": commit_hash[:12],
                            "dest_dir": str(dest_dir)})
            continue

        if args.max_download and success_count >= args.max_download:
            print(f"  Reached max_download={args.max_download}, stopping.")
            break

        print(f"  [{fid}] {repo_url}@{commit_hash[:12]} → {dest_dir.name}")
        result = download_repo(repo_url, commit_hash, dest_dir)
        results.append({"id": fid, "status": "success" if result["success"] else "fail",
                        "reason": result["reason"], "repo_url": repo_url,
                        "commit_hash": commit_hash[:12], "dest_dir": str(dest_dir)})

        if result["success"]:
            success_count += 1
            downloaded_ids.add(fid)
        else:
            fail_count += 1

    # 更新 ground_truth
    if not args.dry_run and downloaded_ids:
        updated = update_ground_truth(gt_path, downloaded_ids)
        print(f"\n  Ground truth updated: {updated} findings upgraded "
              f"from real_bug_no_repo to real_bug")

    # 写出下载报告
    report_path = dest_root / "download_report.json"
    report = {
        "dataset": dataset,
        "total_findings": len(findings),
        "success": success_count,
        "fail": fail_count,
        "skip": skip_count,
        "dry_run": args.dry_run,
        "results": results,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                           encoding="utf-8")

    print(f"\ndownload_repos: success={success_count}, fail={fail_count}, skip={skip_count}")
    print(f"  Report: {report_path}")
    return 0 if success_count > 0 or args.dry_run else 1


if __name__ == "__main__":
    run_script(main)
