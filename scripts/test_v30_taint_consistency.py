"""v3.0 T9' Phase 1 TDD — taint 验证能力 (Joern MVP + AST def-use + regex).

覆盖: T1 (verify_findings) / T2 (joern_cpg) / T3 (ast_cfg) / T4 (端到端)。
运行: py -m pytest scripts/test_v30_taint_consistency.py -v

TDD 流程: 本文件先于实现编写, Red -> Green -> Refactor (实施规范 §8.2)。
测试规模: 41 项 (T1 14 / T2 11 / T3 10 / T4 4 / T0.10 / T6.1)。
Mock 策略: T2 全部 mock Joern (不实际调用); T3 使用真实 ast; memo 逐测试 clear。
"""
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# 确保 scripts/ 可被直接 import (verify_findings 内部 `import joern_cpg` / `import ast_cfg`)
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ast_cfg            # noqa: E402
import joern_cpg          # noqa: E402
import verify_findings as vf  # noqa: E402


def _write(base, rel, content):
    """在 base/rel 写入内容 (自动建父目录), 返回 Path."""
    p = Path(base) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _read_lines(path):
    """读取文件为按行列表 (与 verify_l1_l2 的 split("\\n") 对齐)."""
    return Path(path).read_text(encoding="utf-8").split("\n")


@pytest.fixture(autouse=True)
def _clear_taint_memo():
    """逐测试清空 _TAINT_QUERY_MEMO, 避免跨测试污染 (实施规范 §6 Mock 策略)."""
    try:
        joern_cpg._TAINT_QUERY_MEMO.clear()
    except AttributeError:
        pass
    yield
    try:
        joern_cpg._TAINT_QUERY_MEMO.clear()
    except AttributeError:
        pass


# ── 共用样例 ──

# v2.8 既有样例文本 (不含任何 TAINT_PATTERNS 关键词)
V28_SAMPLE_CLAIMS = [
    "missing error handling in parse_config",
    "dead code after return statement",
    "circular dependency between module_a and module_b",
    "wrong default value should be 10",
    "unvalidated parameter passed to handler",
    "imports but never used os",
]

# 含 taint 关键词的 claim
TAINT_SAMPLE_CLAIMS = [
    "taint flow from request.args to sql query",
    "untrusted input reaches os.system sink",
    "attacker-controlled data used without sanitization",
    "user-controlled parameter flows into eval",
    "data flow from source to sink in handler",
    "SQL injection via unsanitized parameter",
]

# taint 争议 finding 的样例: sink 为常量实参 (Tier 2 可结构化证伪)
_TAINT_CONST_SRC = (
    "import subprocess\n"
    "\n"
    "\n"
    "def f(x):\n"
    '    subprocess.call("ls")\n'
)
_TAINT_CLAIM = "taint: user input flows to subprocess.call (CWE-78)"

# 模块级 sink (无外层函数 => Tier 2 恒 None) + claim 无 sink API 名 (Tier 3 恒 None)
_MODULE_SINK_SRC = "import subprocess\nsubprocess.call(cmd)\n"
_NO_VERDICT_CLAIM = "taint: user input flows to subprocess execution (CWE-78)"


def _taint_finding(fid="F1", severity="P0"):
    return {
        "id": fid,
        "severity": severity,
        "claim": _TAINT_CLAIM,
        "evidence": {"file": "app.py", "line_start": 5, "cwe": "CWE-78"},
    }


# ════════════════════════════════════════════════════════════
# T1: verify_findings.py — taint 识别 / 裁决接线 (14 tests)
# ════════════════════════════════════════════════════════════


class TestT1TaintIdentification:
    """T1.1-T1.6: classify_claim 双通道识别."""

    def test_T1_1_v28_samples_unchanged_without_evidence(self):
        """T1.1 (AC-1b): 6 个既有样例在 evidence=None 下分类不含 taint."""
        for claim in V28_SAMPLE_CLAIMS:
            assert "taint" not in vf.classify_claim(claim), claim
        assert "missing" in vf.classify_claim("missing error handling in parse_config")
        assert "dead_code" in vf.classify_claim("dead code after return statement")
        assert "import_related" in vf.classify_claim(
            "circular dependency between module_a and module_b")

    def test_T1_2_text_channel_positive(self):
        """T1.2 (AC-3): ≥5 条含 taint 关键词的 claim => 'taint' in types."""
        for claim in TAINT_SAMPLE_CLAIMS:
            assert "taint" in vf.classify_claim(claim), claim

    def test_T1_3_text_channel_negative(self):
        """T1.3: ≥5 条既有文本 => 不含 'taint'."""
        for claim in V28_SAMPLE_CLAIMS:
            assert "taint" not in vf.classify_claim(claim), claim

    def test_T1_4_structured_channel_analysis_kind(self):
        """T1.4 (AC-4b): evidence.analysis_kind == 'taint' 命中; evidence 必须被消费."""
        claim = "finding at app.py:10"
        assert "taint" in vf.classify_claim(claim, {"analysis_kind": "taint"})
        # 反向对照: 不传 evidence => 结构化通道不激活 (证明参数被消费)
        assert "taint" not in vf.classify_claim(claim)

    def test_T1_5_taint_cwe_set_all_and_negative(self):
        """T1.5 (AC-2): TAINT_CWE_SET 8 项逐一命中; CWE-352 (非集合) 不命中."""
        claim = "finding at app.py:10"
        assert len(vf.TAINT_CWE_SET) == 8
        for cwe in sorted(vf.TAINT_CWE_SET):
            assert "taint" in vf.classify_claim(claim, {"cwe": cwe}), cwe
        assert "taint" not in vf.classify_claim(claim, {"cwe": "CWE-352"})

    def test_T1_6_evidence_none_does_not_activate_structured(self):
        """T1.6 (D-T9'-1): evidence 省略时结构化通道不激活 (含 CWE 文本亦然)."""
        claim = "no validation of parameter (CWE-89)"
        assert "taint" not in vf.classify_claim(claim)
        assert "taint" in vf.classify_claim(claim, {"cwe": "CWE-89"})


class TestT1VerdictWiring:
    """T1.7-T1.14: L5 接线 / 落库时机 / 兼容性."""

    def test_T1_7_no_verdict_no_taint_check(self, tmp_path, monkeypatch):
        """T1.7 (AC-4): 无裁决 => checks 无 'taint' 键, 且回落 generic (E-5)."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        _write(tmp_path, "m.py", _MODULE_SINK_SRC)
        res = vf.verify_l4_structural(
            _read_lines(tmp_path / "m.py"), 2, _NO_VERDICT_CLAIM, ["taint"],
            repo_root=str(tmp_path), file_path="m.py", language="python")
        assert "taint" not in res["checks"]
        assert "generic" in res["checks"]

    def test_T1_8_taint_disproof_downgrades(self, tmp_path, monkeypatch):
        """T1.8 (AC-6): taint 证伪默认 downgrade => action='partial'."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        result, action = vf.verify_single_finding(_taint_finding(), str(tmp_path))
        assert action == "partial"
        assert result["taint_verified"] is False
        assert result["taint_disproof_action"] == "downgrade"

    def test_T1_9_taint_disproof_remove_mode(self, tmp_path, monkeypatch):
        """T1.9 (AC-7): taint_disproof='remove' => 移除 (action='unverified')."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        result, action = vf.verify_single_finding(
            _taint_finding(), str(tmp_path), taint_disproof="remove")
        assert action == "unverified"
        assert result["taint_disproof_action"] == "remove"

    def test_T1_10_sink_not_located_yields_none(self, tmp_path, monkeypatch):
        """T1.10 (AC-5): mock Joern sink_nodes=0 => taint_verified=None (不得 False)."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "0", "source_nodes": "3", "has_flow": "false"})
        _write(tmp_path, "m.py", _MODULE_SINK_SRC)
        finding = {"id": "F10", "severity": "P0", "claim": _NO_VERDICT_CLAIM,
                   "evidence": {"file": "m.py", "line_start": 2, "cwe": "CWE-78"}}
        result, _action = vf.verify_single_finding(finding, str(tmp_path))
        assert result["taint_verified"] is None
        assert "taint" not in (result.get("l4") or {}).get("checks", {})

    def test_T1_11_kill_switch_no_taint_fields(self, tmp_path, monkeypatch):
        """T1.11 (AC-1/AC-9): ADD_TAINT_DISABLE=1 => 无 taint_* 字段 + generic 回落."""
        monkeypatch.setenv("ADD_TAINT_DISABLE", "1")
        monkeypatch.setenv("JOERN_DISABLE", "1")
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        result, _action = vf.verify_single_finding(_taint_finding(), str(tmp_path))
        assert "taint_verified" not in result
        assert "taint_mode" not in result
        assert "taint_disproof_action" not in result
        assert "generic" in (result.get("l4") or {}).get("checks", {})

    def test_T1_12_verification_level_domain(self, tmp_path, monkeypatch):
        """T1.12 (AC-11): 全量结果 verification_level ∈ {1,2,3,4} (不出现 5)."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        _write(tmp_path, "a.py",
               "import subprocess\n\n\ndef f(x):\n    subprocess.call(x)\n")
        _write(tmp_path, "b.py", _MODULE_SINK_SRC)
        findings = [
            _taint_finding("A"),
            {"id": "B", "severity": "P0", "claim": "missing error handling in a.py",
             "evidence": {"file": "a.py", "line_start": 5}},
            {"id": "C", "severity": "P0", "claim": "taint: data flow from source to sink",
             "evidence": {"file": "b.py", "line_start": 2, "cwe": "CWE-78"}},
        ]
        verified, _hallucinations, _downgraded = vf.verify_all_findings(
            findings, str(tmp_path))
        seen = set()
        for f in verified:
            level = f.get("verification_level")
            if level is None:
                level = (f.get("_phase35_verification") or {}).get("verification_level")
            if level is not None:
                seen.add(level)
        assert seen <= {1, 2, 3, 4}
        assert 5 not in seen

    def test_T1_13_schema_additive_only_taint_findings(self, tmp_path, monkeypatch):
        """T1.13 (AC-12): 新增 3 字段仅出现在 taint findings; 既有键集合零变化."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        other = {"id": "O", "severity": "P0", "claim": "missing error handling in app.py",
                 "evidence": {"file": "app.py", "line_start": 5}}
        r_taint, _ = vf.verify_single_finding(_taint_finding(), str(tmp_path))
        r_other, _ = vf.verify_single_finding(other, str(tmp_path))
        new_keys = {"taint_verified", "taint_mode", "taint_disproof_action"}
        assert new_keys <= set(r_taint)
        assert not (new_keys & set(r_other))
        # kill switch 下同一非 taint finding 的键集合应与开启态一致
        monkeypatch.setenv("ADD_TAINT_DISABLE", "1")
        r_other_off, _ = vf.verify_single_finding(other, str(tmp_path))
        assert set(r_other) == set(r_other_off)

    def test_T1_14_structural_false_respects_disproof_action(self, tmp_path, monkeypatch):
        """T1.14 (AC-6/H2): structural_false 尊重 disproof_action."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        finding = _taint_finding("F14")
        fake = {"level": 3, "confirmed": False, "verified": False,
                "claim_types": ["taint"], "reason": "fake",
                "checks": {"taint": {"tier": 1, "verified": False,
                                     "disproof_action": "downgrade"}}}
        monkeypatch.setattr(vf, "verify_l4_structural", lambda *a, **k: dict(fake))
        _r1, a1 = vf.verify_single_finding(finding, str(tmp_path))
        assert a1 == "partial"

        fake["checks"]["taint"]["disproof_action"] = "remove"
        monkeypatch.setattr(vf, "verify_l4_structural", lambda *a, **k: dict(fake))
        _r2, a2 = vf.verify_single_finding(finding, str(tmp_path))
        assert a2 == "unverified"


# ════════════════════════════════════════════════════════════
# T2: joern_cpg.py — Tier 1 taint reachability (11 tests)
# ════════════════════════════════════════════════════════════


class TestT2JoernTaint:
    """T2.1-T2.11: 降级链 / 脚本形态 / memo / 三语言 / CWD 副作用."""

    def test_T2_1_joern_unavailable(self, monkeypatch):
        """T2.1 (AC-15): JOERN_DISABLE=1 => verified=None, tier=0."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        r = joern_cpg.verify_taint_flow("/nonexistent/repo", "a.py", 1)
        assert r["verified"] is None
        assert r["tier"] == 0
        assert r["evidence"] == "joern_unavailable"
        assert r["taint_mode"] is None

    def test_T2_2_force_raise_absorbed(self, tmp_path, monkeypatch):
        """T2.2 (AC-15): JOERN_FORCE_RAISE=1 => 直接抛出; 经 L5 调用被捕获降级."""
        monkeypatch.setenv("JOERN_FORCE_RAISE", "1")
        with pytest.raises(RuntimeError):
            joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)

        _write(tmp_path, "a.py",
               "import subprocess\n\n\ndef f(x):\n    subprocess.call(x)\n")
        res = vf.verify_l4_structural(
            _read_lines(tmp_path / "a.py"), 5, _TAINT_CLAIM, ["taint"],
            repo_root=str(tmp_path), file_path="a.py", language="python")
        assert res["level"] in (3, 4)  # 未崩溃

    def test_T2_3_cpg_generation_failed(self, tmp_path, monkeypatch):
        """T2.3: _generate_cpg => None => verified=None, tier=0."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: None)
        r = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)
        assert r["verified"] is None and r["tier"] == 0
        assert r["evidence"] == "cpg_generation_failed"

    def test_T2_4_joern_query_failed(self, tmp_path, monkeypatch):
        """T2.4: _run_joern_query => None => verified=None, tier=0."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        monkeypatch.setattr(joern_cpg, "_run_joern_query", lambda *a, **k: None)
        r = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)
        assert r["verified"] is None and r["tier"] == 0
        assert r["evidence"] == "joern_query_failed"

    def test_T2_5_sink_or_source_zero(self, tmp_path, monkeypatch):
        """T2.5 (AC-5): sink_nodes=0 / source_nodes=0 => verified=None."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "0", "source_nodes": "5", "has_flow": "false"})
        r1 = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)
        assert r1["verified"] is None and r1["evidence"] == "sink_not_located"
        # 换 sink_line 以避开 memo
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "2", "source_nodes": "0", "has_flow": "false"})
        r2 = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 2)
        assert r2["verified"] is None and r2["evidence"] == "no_sources"

    def test_T2_6_positive_negative_verdict(self, tmp_path, monkeypatch):
        """T2.6: has_flow=true => True; false => False (sink>0, source>0)."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "1", "source_nodes": "3", "has_flow": "true"})
        r_true = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)
        assert r_true["verified"] is True
        assert r_true["taint_mode"] == "broad"
        assert r_true["sink_nodes"] == 1 and r_true["source_nodes"] == 3
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "1", "source_nodes": "3", "has_flow": "false"})
        r_false = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 2)
        assert r_false["verified"] is False

    def test_T2_7_script_variants(self):
        """T2.7 (R1/R1b/R1c/R1d): broad + exact 双变体脚本形态."""
        broad = joern_cpg._gen_taint_flow_script(42, "app.py")
        assert "import io.joern.dataflowengineoss.language._" in broad
        assert 'sinkFile = "app.py"' in broad
        assert "sinkLine = 42" in broad
        assert "lineNumber(" in broad          # E-4: step 形式
        assert "cpg.method.parameter" in broad
        assert "@main" not in broad

        exact = joern_cpg._gen_taint_flow_script(
            42, "app.py", source_line=10, source_file="input.py")
        assert "sourceLine = 10" in exact
        assert "srcList" in exact
        assert 'srcFile = "input.py"' in exact
        assert "cpg.method.parameter" not in exact

        exact_default = joern_cpg._gen_taint_flow_script(7, "sink.py", source_line=3)
        assert 'srcFile = "sink.py"' in exact_default

    def test_T2_8_memo_reuse(self, tmp_path, monkeypatch):
        """T2.8 (§0.4): 同 memo_key 两次调用 => _run_joern_query 仅 1 次; 返回浅拷贝(G-5)."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        calls = {"n": 0}

        def _fake_run(*a, **k):
            calls["n"] += 1
            return {"sink_nodes": "1", "source_nodes": "3", "has_flow": "true"}

        monkeypatch.setattr(joern_cpg, "_run_joern_query", _fake_run)
        r1 = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 7)
        r2 = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 7)
        assert calls["n"] == 1
        assert r1 == r2
        assert r1 is not r2  # G-5: 返回副本, 防跨 finding 可变引用污染

    def test_T2_9_cache_key_shared(self, tmp_path, monkeypatch):
        """T2.9 (AC-18): taint 与 dead_code 共用同一 CPG cache key."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        _write(tmp_path, "a.py", "x = 1\n")
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        monkeypatch.setattr(joern_cpg, "_generate_cpg", lambda *a, **k: "/fake/cpg.bin")
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "1", "source_nodes": "1",
                             "has_flow": "true", "dead": "false"})
        seen_keys = []
        orig = joern_cpg._get_cache_key

        def _rec(repo_root, language="python"):
            k = orig(repo_root, language=language)
            seen_keys.append(k)
            return k

        monkeypatch.setattr(joern_cpg, "_get_cache_key", _rec)
        joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1)
        joern_cpg.verify_dead_code(str(tmp_path), "a.py", 1)
        assert len(seen_keys) == 2
        assert seen_keys[0] == seen_keys[1]
        assert seen_keys[0].startswith("py_")

    def test_T2_10_three_languages(self, tmp_path, monkeypatch):
        """T2.10 (AC-17): python/java/cpp 均正确映射 JOERN_LANGUAGE_MAP."""
        monkeypatch.delenv("JOERN_DISABLE", raising=False)
        monkeypatch.delenv("JOERN_FORCE_RAISE", raising=False)
        monkeypatch.setattr(joern_cpg, "is_available", lambda: True)
        frontends = []

        def _fake_gen(repo_root, cache_key, language="pythonsrc"):
            frontends.append(language)
            return "/fake/cpg.bin"

        monkeypatch.setattr(joern_cpg, "_generate_cpg", _fake_gen)
        monkeypatch.setattr(
            joern_cpg, "_run_joern_query",
            lambda *a, **k: {"sink_nodes": "1", "source_nodes": "1", "has_flow": "true"})
        for lang in ("python", "java", "cpp"):
            r = joern_cpg.verify_taint_flow(str(tmp_path), "a.py", 1, language=lang)
            assert r["verified"] is True, lang
        assert frontends == ["pythonsrc", "javasrc2cpg", "c2cpg"]
        assert set(joern_cpg.JOERN_LANGUAGE_MAP) == {"python", "java", "cpp"}

    def test_T2_11_query_uses_cache_cwd(self, monkeypatch):
        """T2.11 (N-1): _run_joern_query 显式传 cwd=joern 缓存目录 (防 CWD 污染)."""
        captured = {}

        class _FakeProc:
            returncode = 0
            stdout = "sink_nodes=1\nsource_nodes=1\nhas_flow=true\n"

        def _fake_subprocess_run(cmd, **kwargs):
            captured["cmd"] = cmd
            captured.update(kwargs)
            return _FakeProc()

        monkeypatch.setattr(joern_cpg.subprocess, "run", _fake_subprocess_run)
        monkeypatch.setattr(joern_cpg, "_build_clean_env", lambda: {})
        joern_cpg._run_joern_query("/fake/cpg.bin", "println(1)", script_name="probe")
        assert captured.get("cwd") == str(joern_cpg._get_cache_dir())


# ════════════════════════════════════════════════════════════
# T3: ast_cfg.py — 过程内 def-use (10 tests)
# ════════════════════════════════════════════════════════════


class TestT3AstTaintFlow:
    """T3.1-T3.9: 过程内 def-use 污点追踪语义."""

    def test_T3_1_param_direct_to_sink(self):
        """T3.1 (AC-13): 函数参数直达 sink => True."""
        src = "import os\ndef f(cmd):\n    os.system(cmd)\n"
        r = ast_cfg.verify_taint_flow_in_source(src, 3)
        assert r["verified"] is True
        assert r["tier"] == 2
        # AC-14: Tier 2 预算 50ms (估计值); 250ms 为稳健上限 (含 CI 抖动余量), 无重试
        assert r["latency_ms"] <= 250

    def test_T3_2_assignment_chain_propagation(self):
        """T3.2: 赋值链传播 y = x; call(y) => True."""
        src = ("import subprocess\ndef f(x):\n    y = x\n    subprocess.call(y)\n")
        r = ast_cfg.verify_taint_flow_in_source(src, 4)
        assert r["verified"] is True

    def test_T3_3_constant_argument_disproof(self):
        """T3.3: 常量实参 => False (结构化证伪)."""
        src = 'import subprocess\ndef f(x):\n    subprocess.call("ls")\n'
        r = ast_cfg.verify_taint_flow_in_source(src, 3)
        assert r["verified"] is False

    def test_T3_4_input_api_assignment(self):
        """T3.4: q = input(); cursor.execute(q) => True."""
        src = "def f():\n    q = input()\n    cursor.execute(q)\n"
        r = ast_cfg.verify_taint_flow_in_source(src, 3)
        assert r["verified"] is True

    def test_T3_5_attr_subscript_base_name(self):
        """T3.5: a = os.environ['X']; subprocess.run(a) => True."""
        src = ('import os, subprocess\ndef f():\n'
               '    a = os.environ["X"]\n    subprocess.run(a)\n')
        r = ast_cfg.verify_taint_flow_in_source(src, 4)
        assert r["verified"] is True

    def test_T3_6_sanitizer_not_modelled(self):
        """T3.6 (设计边界): sanitizer 不建模 => 仍 True (方向偏保留)."""
        src = ("import html, subprocess\ndef f(x):\n"
               "    y = html.escape(x)\n    subprocess.call(y)\n")
        r = ast_cfg.verify_taint_flow_in_source(src, 4)
        assert r["verified"] is True

    def test_T3_7_module_level_sink_none(self):
        """T3.7: 模块级 sink (无外层函数) => None."""
        src = "import os\nos.system(cmd)\n"
        r = ast_cfg.verify_taint_flow_in_source(src, 2)
        assert r["verified"] is None

    def test_T3_8_syntax_error_none(self):
        """T3.8 (AC-15): 非法源码 => None."""
        r = ast_cfg.verify_taint_flow_in_source("def f(:\n", 1)
        assert r["verified"] is None

    def test_T3_9_file_not_found_none(self):
        """T3.9: 不存在路径 => None."""
        r = ast_cfg.verify_taint_flow(str(ROOT), "no/such/file_xyz.py", 1)
        assert r["verified"] is None


class TestT3LanguageGate:
    """T3.10: Tier 2 仅对 python 启用 (在 verify_l4_structural 层断言)."""

    def test_T3_10_tier2_language_gate(self, tmp_path, monkeypatch):
        """T3.10 (AC-13): java/cpp 跳过 Tier 2; python 调用 Tier 2."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        _write(tmp_path, "a.py",
               "import subprocess\n\n\ndef f(x):\n    subprocess.call(x)\n")
        lines = _read_lines(tmp_path / "a.py")
        calls = []

        def _spy(*a, **k):
            calls.append(a)
            return {"verified": True, "evidence": "spy", "tier": 2}

        monkeypatch.setattr(ast_cfg, "verify_taint_flow", _spy)
        for lang in ("java", "cpp"):
            vf.verify_l4_structural(lines, 5, _TAINT_CLAIM, ["taint"],
                                    repo_root=str(tmp_path), file_path="a.py",
                                    language=lang)
        assert calls == []
        vf.verify_l4_structural(lines, 5, _TAINT_CLAIM, ["taint"],
                                repo_root=str(tmp_path), file_path="a.py",
                                language="python")
        assert len(calls) == 1


# ════════════════════════════════════════════════════════════
# T4: 端到端 (4 tests)
# ════════════════════════════════════════════════════════════


class TestT4EndToEnd:

    def test_T4_1_degrade_and_generic_fallback(self, tmp_path, monkeypatch):
        """T4.1 (AC-4/E-5): Joern 关闭 + 无裁决 => 回落 generic, 无 taint check."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "m.py", _MODULE_SINK_SRC)
        finding = {"id": "E1", "severity": "P0", "claim": _NO_VERDICT_CLAIM,
                   "evidence": {"file": "m.py", "line_start": 2, "cwe": "CWE-78"}}
        result, _action = vf.verify_single_finding(finding, str(tmp_path))
        checks = (result.get("l4") or {}).get("checks", {})
        assert "taint" not in checks
        assert "generic" in checks

    def test_T4_2_tier2_disproof_partial(self, tmp_path, monkeypatch):
        """T4.2 (AC-6): Tier 2 证伪 (常量实参) => action='partial' (默认)."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        result, action = vf.verify_single_finding(_taint_finding("E2"), str(tmp_path))
        assert action == "partial"
        assert result["taint_verified"] is False

    def test_T4_3_p1_l4_path_partial(self, tmp_path, monkeypatch):
        """T4.3 (AC-6): verify_p1_l4=True + taint P1 => partial, 不误进 hallucination."""
        monkeypatch.setenv("JOERN_DISABLE", "1")
        monkeypatch.delenv("ADD_TAINT_DISABLE", raising=False)
        _write(tmp_path, "app.py", _TAINT_CONST_SRC)
        verified, hallucinations, _downgraded = vf.verify_all_findings(
            [_taint_finding("E3", severity="P1")], str(tmp_path), verify_p1_l4=True)
        assert len(verified) == 1
        assert verified[0]["_phase35_action"] == "downgraded_l1l2_l4"
        assert all(h["id"] != "E3" for h in hallucinations)

    def test_T4_4_existing_suites_no_regression(self):
        """T4.4 (AC-10): 既有测试套件零回归 (v24 / v27 / v28 / e2e).

        调用方式说明 (Step 9 实测): test_v24 / test_v27 / test_e2e_v24_integration 是
        **脚本式**套件 (模块级 `sys.exit`), 必须以 `python <script>` 直接运行 ——
        `py -m pytest` 会因模块级 SystemExit 触发 pytest INTERNALERROR。
        test_v28 是 pytest 模块 (与之对齐)。故本测试按套件实际形态选择调用方式。
        """
        cases = [
            (["scripts/test_v24_consistency.py"], "153 passed, 0 failed"),
            (["scripts/test_v27_consistency.py"], "68 passed, 0 failed"),
            (["-m", "pytest", "scripts/test_v28_consistency.py", "-q"], "25 passed"),
            (["scripts/test_e2e_v24_integration.py"], "0 FAIL"),
        ]
        for argv, marker in cases:
            proc = subprocess.run([sys.executable] + argv, capture_output=True,
                                  text=True, cwd=str(ROOT), timeout=900)
            assert proc.returncode == 0, f"{argv} non-zero rc:\n{proc.stdout[-3000:]}"
            assert marker in proc.stdout, \
                f"{argv} missing {marker!r}:\n{proc.stdout[-1500:]}"


# ════════════════════════════════════════════════════════════
# T0.10 / T6.1: 产物与文档校验
# ════════════════════════════════════════════════════════════


class TestArtifactsAndDocs:

    def test_T0_10_t0_validation_artifact(self):
        """T0.10 (AC-16): T0 实测产物存在且含 R1/R1b/R1c/R1d 四项结论."""
        path = ROOT / "docs" / "audit-log" / "2026-10-20-T9prime-joern-api-validation.md"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        for token in ("R1", "R1b", "R1c", "R1d"):
            assert token in text, token

    def test_T6_1_docs_sync(self):
        """T6.1: ARCHITECTURE.md / DEVLOG.md / ROADMAP.md 含 T9' Phase 1 交付条目."""
        for doc, tokens in (
                ("ARCHITECTURE.md", ["taint_verified", "taint"]),
                ("DEVLOG.md", ["T9' Phase 1"]),
                ("ROADMAP.md", ["T9' Phase 1"])):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            for token in tokens:
                assert token in text, f"{doc} missing {token!r}"
