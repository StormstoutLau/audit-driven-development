"""MCP external knowledge query builder. v2.3 Shared Knowledge Pipeline.

Usage: python scripts/mcp_lookup.py
         --findings <issues.json>
         --output <mcp_queries.json>
         [--cache-dir .mcp_cache]

This script builds structured query descriptions for the main agent.
"""

import argparse, json, sys, hashlib, time
from pathlib import Path
from _script_utils import run_script

def cache_key(query):
    return hashlib.md5(query.encode()).hexdigest()[:12]

def check_cache(cache_dir, query):
    cache_file = Path(cache_dir) / f"{cache_key(query)}.json"
    if cache_file.exists():
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        age = time.time() - data.get("timestamp", 0)
        if age < 86400:
            return data.get("result")
    return None

def save_cache(cache_dir, query, result):
    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_file = Path(cache_dir) / f"{cache_key(query)}.json"
    cache_file.write_text(json.dumps({
        "query": query, "result": result, "timestamp": time.time()
    }, indent=2), encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", required=True)
    parser.add_argument("--output", default="docs/audit/mcp_queries.json")
    parser.add_argument("--cache-dir", default=".mcp_cache")
    args = parser.parse_args()

    data = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    findings = data.get("issues", [])

    targets = [
        f for f in findings
        if isinstance(f, dict)
        and f.get("severity") in ("P0", "P1")
        and "suggested_fix" not in f
    ][:5]

    cached_hits = 0
    queries = []
    for f in targets:
        claim = f.get("claim", "")[:150]
        query = f"Python bug fix: {claim}"
        if cached := check_cache(args.cache_dir, query):
            cached_hits += 1
            f["mcp_result"] = cached
        else:
            queries.append({
                "finding_id": f.get("id", ""),
                "severity": f.get("severity", ""),
                "query": query,
                "claim": claim,
                "file": f.get("file", ""),
                "mcp_servers": ["mcp_english-search", "mcp_stackexchange"]
            })

    output = {
        "queries_to_execute": queries,
        "cache_hits": cached_hits,
        "findings_analyzed": len(targets),
        "instructions": "Dispatch each query via run_mcp tool. "
                        "Server: mcp_english-search (search_web) or "
                        "mcp_stackexchange (search_questions). "
                        "Save results back via mcp_lookup cache."
    }

    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"mcp_lookup: {len(queries)} queries to execute, "
          f"{cached_hits} cache hits, {len(targets)} P0+P1 findings analyzed")
    return 0

if __name__ == "__main__":
    run_script(main)
