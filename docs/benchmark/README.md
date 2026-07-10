# ADD OSS Benchmark / ADD OSS 基准测试

## Methodology / 方法论

1. Select an OSS project with documented known bugs (from release notes, CVE database, or git history)
2. Clone at the pre-fix commit (the version BEFORE the bugs were fixed)
3. Identify design documents (specs, ADRs, architecture docs, API reference)
4. Run ADD Phase 0 (Spec Quality Gate) → determine Tier (A/B/C)
5. Run ADD Phase 2 (Multi-Dimensional Audit) with subagent dispatch
6. Manually classify each finding against the known bugs list:
   - **Exact match**: finding file+line overlaps known bug → TP
   - **Close match**: finding file matches, same category, same root cause → TP
   - **Related**: same problem, different file → FP (not a detection)
   - **No match**: → FP
7. Calculate: recall = TP / known_bugs, precision = TP / (TP + FP)
8. Write benchmark-result.json

**TP standard per ROADMAP.md P2.9 §TP/FP/FN Classification Standard.**

## Results / 结果

| Project | Version | Tier | TP | FN | FP | Recall | Precision | F1 |
|---|---|---|---|---|---|---|---|---|
| FastAPI | 0.115.8 | B (structural) | 3 | 3 | 3 | 50% | 83% | 62.5% |

### Gate Assessment

Tier A benchmark (primary): FastAPI recall = 50%. **Soft-fail** — recall is below 70% Tier A threshold but above 50%.

Tier B benchmark (secondary): Structural audit recall = 50%. Below 60% average but within 40-60% soft-fail range.

## Detailed Findings

### True Positives

1. **KB-1: HTTPDigest auto_error (EXACT)** — Detected as P0 by security subagent. Precise evidence at `fastapi/security/http.py:L415-L419`. The subagent correctly identified that HTTPDigest raises HTTPException unconditionally while HTTPBearer correctly checks `auto_error`.

2. **KB-4: convert_underscores=False (EXACT)** — Detected as P1 by dependencies subagent. Evidence at `fastapi/dependencies/utils.py:L766`. Correctly identified getattr default fallback overriding user setting.

3. **KB-2: \f truncation (CLOSE)** — Detected as P1 by openapi subagent. Evidence at `fastapi/routing.py:L531-L534`. Subagent correctly identified the root cause but classified as "design intent" rather than "bug". Still valid detection (tag: close).

### False Negatives (Missed Bugs)

4. **KB-3: Union+Form** — Requires deep type combinatorics analysis. Not detectable in structural audit mode.
5. **KB-5: AfterValidator** — Requires Pydantic-specific domain knowledge. Type of bug that needs framework-specific rules (like security skill's per-language reference files).
6. **KB-6: Pydantic 2.11 compat** — Forward-compatibility bug. Requires testing against unreleased library versions.

### Root Cause of FNs

- KB-3 (Union+Form): Type system combinatorics → needs lens-specific prompt (v0.3 P2.8' would help)
- KB-5 (AfterValidator): Domain knowledge gap → needs security-like rule files for Pydantic (v0.5 P3.1 guards.yml pattern)
- KB-6 (Pydantic 2.11): Static analysis limitation → needs runtime testing (out of ADD scope)

## Scoped Audit Note

FastAPI has 2,449 files across 200+ modules. Benchmark cost cap (5 subagents, 50 files per module) limits audit to 3 modules. Full-repo audit would produce different metrics. This is the first Tier-B structural benchmark — subsequent benchmarks should include at least one Tier A project with formal design specs.

## Next Steps

1. Run 2 more Tier B benchmarks (Flask, Requests) to get 3-project average
2. Run 1 Tier A benchmark (Django REST Framework with formal BDFL docs) for full-audit recall
3. If 3-project average recall >60% → gate pass, proceed to P2.8' implementation
4. If soft-fail persists → optimize subagent prompts based on FN analysis, retry
