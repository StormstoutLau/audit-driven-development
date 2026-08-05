"""Analyze Phase 3.5 self-audit results."""
import json, sys
from pathlib import Path

data = json.load(open('docs/benchmark/add-v2.4-self-audit/verified.json', encoding='utf-8'))

print('=== Phase 3.5 Self-Audit Summary ===')
s = data['summary']
print(f"Total findings: {s['total_findings']}")
print(f"Verified P0 (L1-L4): {s['verified_p0']}")
print(f"Verified P1 (L1+L2): {s['verified_p1_l1l2']}")
print(f"Downgraded P0->P1: {s['downgraded']}")
print(f"Removed hallucinations: {s['removed_hallucinations']}")
print()

print('=== Hallucinations (false positives removed) ===')
for h in data['hallucinations']:
    print(f"  [{h['severity']}] {h['id']}: {h['claim'][:70]}")
    print(f"    reason: {h['reason']}")
print()

print('=== Downgraded (structural verification failed) ===')
for d in data['downgraded']:
    print(f"  {d['id']}: {d['from']}->{d['to']} - {d['reason']}")
print()

print('=== Verified Findings Detail (Tier info) ===')
for f in data['verified_findings']:
    v = f.get('_phase35_verification', {})
    l4 = v.get('l4', {})
    checks = l4.get('checks', {})
    tiers = {k: c.get('tier') for k, c in checks.items() if isinstance(c, dict)}
    verified_status = {k: c.get('verified') for k, c in checks.items() if isinstance(c, dict)}
    action = f.get('_phase35_action', '?')
    sev = f.get('severity', '?')
    print(f"  {f['id']} [{sev}] action={action}")
    if tiers:
        print(f"    tiers: {tiers}")
        print(f"    verified: {verified_status}")
    elif action == 'verified_l1l2':
        print(f"    L1+L2 only (P1 lightweight)")
    elif action == 'downgraded':
        print(f"    L4 structural verification failed")
print()

# Ground truth comparison
print('=== Ground Truth Comparison ===')
# My intentional construction:
# SA-1: real dead_code (should verify) - but line 60 is docstring, not code
# SA-2: hallucination (subprocess has try/except)
# SA-3: hallucination (no circular dep)
# SA-4: real dead_code (visit_Raise alias)
# SA-5: hallucination (empty output handled)
# SA-6: hallucination (this is spec comment, not code)
# SA-7: hallucination (has try/except)
# SA-8: real scope issue (P1)

ground_truth = {
    'SA-1': ('hallucination', 'visit_FunctionDef has NO return — claim is hallucination'),
    'SA-2': ('hallucination', 'subprocess.run timeout IS caught'),
    'SA-3': ('hallucination', 'no circular dependency exists'),
    'SA-4': ('hallucination', 'line 171 is alias assignment, not dead code'),
    'SA-5': ('hallucination', 'empty output IS handled'),
    'SA-6': ('hallucination', 'spec comment, not code bug'),
    'SA-7': ('hallucination', 'has try/except OSError'),
    'SA-8': ('real_bug', 'scope issue in except handler'),
}

tp = 0  # correctly identified hallucination
fp = 0  # real bug incorrectly flagged as hallucination
fn = 0  # hallucination incorrectly kept as verified
tn = 0  # real bug correctly kept

hallucination_ids = {h['id'] for h in data['hallucinations']}
downgraded_ids = {d['id'] for d in data['downgraded']}

for fid, (truth, desc) in ground_truth.items():
    is_halluc = fid in hallucination_ids
    is_downgraded = fid in downgraded_ids
    if truth == 'hallucination':
        if is_halluc:
            tp += 1
            print(f"  TP {fid}: correctly removed as hallucination - {desc}")
        else:
            fn += 1
            status = 'downgraded' if is_downgraded else 'verified'
            print(f"  FN {fid}: hallucination kept as {status} - {desc}")
    else:  # real_bug
        if is_halluc:
            fp += 1
            print(f"  FP {fid}: real bug removed as hallucination - {desc}")
        else:
            tn += 1
            status = 'downgraded' if is_downgraded else 'verified'
            print(f"  TN {fid}: real bug kept as {status} - {desc}")

print()
print(f'Hallucination detection: TP={tp}, FP={fp}, FN={fn}, TN={tn}')
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
print(f'Precision: {precision:.1%}')
print(f'Recall: {recall:.1%}')
