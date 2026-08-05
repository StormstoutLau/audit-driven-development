"""Craft realistic findings against Python stdlib for Phase 3.5 testing."""
import os
import json

STDLIB = os.path.dirname(os.__file__)

# Read json/decoder.py to get real line numbers
json_decoder = os.path.join(STDLIB, "json", "decoder.py")
src = open(json_decoder, encoding='utf-8').read()
lines = src.split('\n')

# Read csv.py for more test cases
csv_path = os.path.join(STDLIB, "csv.py")
csv_src = open(csv_path, encoding='utf-8').read()
csv_lines = csv_src.split('\n')

findings = []

# ── L1/L2 Hallucinations (file/line level) ──

# H1: File not found
findings.append({
    "id": "OSS-H1",
    "severity": "P0",
    "claim": "dead code after return in nonexistent function",
    "evidence": {"file": "nonexistent_file.py", "line_start": 1},
    "ground_truth": "hallucination_file_not_found"
})

# H2: Line out of range (json/decoder.py has 357 lines)
findings.append({
    "id": "OSS-H2",
    "severity": "P0",
    "claim": "dead code at end of file beyond last line",
    "evidence": {"file": "json/decoder.py", "line_start": 9999},
    "ground_truth": "hallucination_line_out_of_range"
})

# ── L4 Hallucinations (structural level - file/line exist but claim is wrong) ──

# H3: Claim dead_code on a reachable line (json/decoder.py line ~20 should be import or docstring)
findings.append({
    "id": "OSS-H3",
    "severity": "P0",
    "claim": "dead code after return in decode method",
    "evidence": {"file": "json/decoder.py", "line_start": 100},
    "ground_truth": "hallucination_reachable_code_claimed_dead"
})

# H4: Claim dead_code on another reachable line
findings.append({
    "id": "OSS-H4",
    "severity": "P0",
    "claim": "unreachable code after return in raw_decode",
    "evidence": {"file": "json/decoder.py", "line_start": 200},
    "ground_truth": "hallucination_reachable_code_claimed_dead"
})

# H5: Claim circular dependency (stdlib has none)
findings.append({
    "id": "OSS-H5",
    "severity": "P0",
    "claim": "circular dependency between json.decoder and csv modules",
    "evidence": {"file": "json/decoder.py", "line_start": 1},
    "ground_truth": "hallucination_no_cycle"
})

# H6: Claim missing error handling (code actually has try/except)
findings.append({
    "id": "OSS-H6",
    "severity": "P0",
    "claim": "missing error handling in JSONDecoder.decode for invalid input",
    "evidence": {"file": "json/decoder.py", "line_start": 330},
    "ground_truth": "hallucination_error_handling_present"
})

# H7: Claim dead_code in csv.py on a reachable line
findings.append({
    "id": "OSS-H7",
    "severity": "P1",
    "claim": "dead code after return in reader.__next__",
    "evidence": {"file": "csv.py", "line_start": 100},
    "ground_truth": "hallucination_reachable_p1"
})

# H8: Wrong API claim (hallucinated function name)
findings.append({
    "id": "OSS-H8",
    "severity": "P0",
    "claim": "wrong API usage in nonexistent_function call",
    "evidence": {"file": "csv.py", "line_start": 50},
    "ground_truth": "hallucination_wrong_api"
})

# ── Real patterns (not bugs, but real code structures) ──

# R1: Real import statement (should verify as present)
findings.append({
    "id": "OSS-R1",
    "severity": "P0",
    "claim": "import statement exists in json/decoder.py",
    "evidence": {"file": "json/decoder.py", "line_start": 1},
    "ground_truth": "real_import_exists"
})

print(f"=== Crafted {len(findings)} findings ===")
hallucinations = sum(1 for f in findings if f.get("ground_truth", "").startswith("hallucination"))
real = sum(1 for f in findings if f.get("ground_truth", "").startswith("real"))
print(f"Hallucinations: {hallucinations}")
print(f"Real patterns: {real}")

# Verify line numbers exist
print("\n=== Line number verification ===")
for f in findings:
    file_path = f["evidence"]["file"]
    line = f["evidence"]["line_start"]
    abs_path = os.path.join(STDLIB, file_path)
    exists = os.path.exists(abs_path)
    if exists:
        total = len(open(abs_path, encoding='utf-8').read().split('\n'))
        in_range = 1 <= line <= total
        content = open(abs_path, encoding='utf-8').read().split('\n')[line-1] if in_range else "OUT OF RANGE"
        print(f"  {f['id']}: {file_path}:{line} exists={exists} in_range={in_range} content='{content[:60]}'")
    else:
        print(f"  {f['id']}: {file_path}:{line} exists={exists}")

# Write findings
output_path = "docs/benchmark/stdlib-oss-test/findings.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)
output_findings = [{k: v for k, v in f.items() if k != "ground_truth"} for f in findings]
with open(output_path, 'w', encoding='utf-8') as fh:
    json.dump({"project": "python-stdlib", "findings": output_findings}, fh, indent=2, ensure_ascii=False)

# Write ground truth
with open("docs/benchmark/stdlib-oss-test/ground_truth.json", 'w', encoding='utf-8') as fh:
    json.dump(findings, fh, indent=2, ensure_ascii=False)

print(f"\nFindings: {output_path}")
print(f"Ground truth: docs/benchmark/stdlib-oss-test/ground_truth.json")
print(f"Stdlib repo: {STDLIB}")
