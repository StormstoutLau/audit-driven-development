"""Shared utility functions for rule extraction. v2.0 Knowledge Pipeline.
Used by both rule_index.py (v1.0) and spec_graph.py (v2.0).
Eliminates code duplication per P1-4 (self-audit corrective item).
"""

import re


def extract_constraints(text, source_name):
    """Extract must/shall/threshold/invariant statements from text."""
    rules = []
    lines = text.split("\n")
    patterns = [
        (r'(?i)\b(must\s+(?:not\s+)?[^.]{15,200}?\.)', "must"),
        (r'(?i)\b(shall\s+(?:not\s+)?[^.]{15,200}?\.)', "must"),
        (r'(?i)\b(threshold[^.]{15,200}?\.)', "threshold"),
        (r'(?i)\b(invariant[^.]{15,200}?\.)', "invariant"),
        (r'(?i)\b(required\s+[^.]{15,200}?\.)', "required"),
        (r'(?i)\b(never\s+[^.]{15,200}?\.)', "forbidden"),
        (r'(?i)\b(always\s+[^.]{15,200}?\.)', "always"),
    ]
    for i, line in enumerate(lines):
        for pat, cat in patterns:
            for m in re.finditer(pat, line):
                rules.append({
                    "text": m.group(1).strip(),
                    "category": cat,
                    "source": source_name,
                    "line": i + 1,
                })
    for i, line in enumerate(lines):
        if re.search(r'(?i)#+\s*(?:rule|constraint|requirement)', line):
            rules.append({
                "text": line.strip(),
                "category": "explicit_rule",
                "source": source_name,
                "line": i + 1,
            })
    return rules


def index_rules(rules):
    """Keyword→constraint index for fast lookup."""
    index = {}
    for r in rules:
        words = set(re.findall(r'\b[a-zA-Z_]\w{2,}\b', r["text"].lower()))
        for w in words:
            if w not in index:
                index[w] = []
            index[w].append(r["text"])
    return {k: v for k, v in list(index.items())[:200]}
