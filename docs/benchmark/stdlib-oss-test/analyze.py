"""Analyze Phase 3.5 stdlib OSS test results against ground truth."""
import json
from pathlib import Path

verified = json.load(open('docs/benchmark/stdlib-oss-test/verified.json', encoding='utf-8'))
truth_list = json.load(open('docs/benchmark/stdlib-oss-test/ground_truth.json', encoding='utf-8'))

print('=== Phase 3.5 stdlib OSS Test Summary ===')
s = verified['summary']
print(f"Total findings: {s['total_findings']}")
print(f"Verified P0 (L1-L4): {s['verified_p0']}")
print(f"Verified P1 (L1+L2): {s['verified_p1_l1l2']}")
print(f"Downgraded P0->P1: {s['downgraded']}")
print(f"Removed hallucinations: {s['removed_hallucinations']}")
print()

# Ground truth from craft_findings.py:
# H1: hallucination (nonexistent file)        — expect: removed (L1)
# H2: hallucination (line out of range)       — expect: removed (L2)
# H3: hallucination (reachable code)          — expect: removed/downgraded (L4)
# H4: hallucination (reachable code)          — expect: removed/downgraded (L4)
# H5: hallucination (no circular dep)         — expect: removed/downgraded (L4 import)
# H6: hallucination (error handling present)  — expect: downgraded (L4 missing)
# H7: hallucination (reachable code, P1)      — expect: verified_l1l2 (P1 lightweight)
# H8: hallucination (wrong API, false)        — expect: removed (L3)
# R1: real pattern (import statement exists)  — expect: verified (L4 or L3)

ground_truth = {t['id']: t['ground_truth'] for t in truth_list}

hallucination_ids = {h['id'] for h in verified['hallucinations']}
downgraded_ids = {d['id'] for d in verified['downgraded']}
verified_ids = {f['id'] for f in verified['verified_findings']}

print('=== Ground Truth Comparison ===')
tp = fp = fn = tn = 0  # hallucination detection perspective
for fid, truth_label in ground_truth.items():
    is_halluc = fid in hallucination_ids
    is_downgraded = fid in downgraded_ids
    is_verified = fid in verified_ids

    if truth_label.startswith('hallucination'):
        if is_halluc:
            tp += 1
            status = 'REMOVED'
        elif is_downgraded:
            fn += 1
            status = 'DOWNGRADED (not removed)'
        else:
            fn += 1
            status = 'VERIFIED (false positive!)'
        print(f"  [{truth_label}] {fid}: {status}")
    else:  # real pattern
        if is_halluc:
            fp += 1
            status = 'REMOVED (false negative!)'
        elif is_downgraded:
            tn += 1
            status = 'DOWNGRADED'
        else:
            tn += 1
            status = 'VERIFIED'
        print(f"  [{truth_label}] {fid}: {status}")

print()
print(f'Hallucination detection: TP={tp}, FP={fp}, FN={fn}, TN={tn}')
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
print(f'Precision: {precision:.1%}')
print(f'Recall: {recall:.1%}')

# Tier analysis
print()
print('=== Tier Usage Analysis ===')
for f in verified['verified_findings']:
    v = f.get('_phase35_verification', {})
    l4 = v.get('l4', {})
    checks = l4.get('checks', {})
    tiers = {k: c.get('tier') for k, c in checks.items() if isinstance(c, dict)}
    action = f.get('_phase35_action', '?')
    if tiers:
        print(f"  {f['id']}: action={action}, tiers={tiers}")
    elif action == 'verified_l1l2':
        print(f"  {f['id']}: action={action} (P1 lightweight, no L4)")
    else:
        print(f"  {f['id']}: action={action}")
