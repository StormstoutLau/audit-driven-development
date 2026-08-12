"""v2.8 TDD test suite — T1 threshold 闭环 + T3/T4/T5/T6.

TDD 流程: 本文件先于实现编写, Red → Green → Refactor.

测试组织 (与 spec §3.1 对齐):
  T1 threshold 闭环: L8.1.1.1-L8.1.1.5 (5 tests)
  T3 Semgrep 转换:  L8.3.1.1-L8.3.1.6 (6 tests)
  T4 CodeQL 转换:   L8.4.1.1-L8.4.1.6 (6 tests)
  T5 CWE 规则:      L8.5.1.1-L8.5.1.5 (5 tests)
  T6 Linux 批量:    L8.6.1.1-L8.6.1.3 (3 tests)

总计: 25 tests
"""
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def _load_module(name, path):
    """动态加载模块, 避免 import 路径问题."""
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ════════════════════════════════════════════════════════════
# T1: L8.1.1.1-L8.1.1.5 — threshold 驱动 L3 验证
# ════════════════════════════════════════════════════════════


class TestT1ThresholdMapping:
    """L8.1.1.1-L8.1.1.4: _threshold_to_min_keywords 映射 + 边界."""

    def test_L8_1_1_1_threshold_0_85_returns_2(self):
        """L8.1.1.1: threshold=0.85 (declining) → min_keywords=2."""
        vf = _load_module("vf_t1", HERE / "verify_findings.py")
        assert vf._threshold_to_min_keywords(0.85) == 2

    def test_L8_1_1_2_threshold_0_55_returns_1(self):
        """L8.1.1.2: threshold=0.55 (improving) → min_keywords=1."""
        vf = _load_module("vf_t1", HERE / "verify_findings.py")
        assert vf._threshold_to_min_keywords(0.55) == 1

    def test_L8_1_1_3_threshold_0_85_strict(self):
        """L8.1.1.3: threshold=0.85 严格模式 (spec §4.1 验收点)."""
        vf = _load_module("vf_t1", HERE / "verify_findings.py")
        assert vf._threshold_to_min_keywords(0.85) == 2

    def test_L8_1_1_4_threshold_none_backward_compat(self):
        """L8.1.1.4: threshold=None → min_keywords=1 (向后兼容)
        + 边界 case: threshold=0.75 → min_keywords=2 (>=0.75 条件)."""
        vf = _load_module("vf_t1", HERE / "verify_findings.py")
        assert vf._threshold_to_min_keywords(None) == 1
        # 边界 case (合并到此测试, 避免超出 spec 规划的 5 个 T1 测试)
        assert vf._threshold_to_min_keywords(0.75) == 2    # >= 0.75
        assert vf._threshold_to_min_keywords(0.749) == 1   # < 0.75


class TestT1VerifyL3MinKeywords:
    """L8.1.1.5: verify_l3(min_keywords=2) 行为 (一个测试内含多 assert)."""

    def test_L8_1_1_5_min_keywords_behavior(self):
        """L8.1.1.5: verify_l3 在 min_keywords=1/2 下的行为."""
        vf = _load_module("vf_t1", HERE / "verify_findings.py")
        # 准备 20 行源码, 在第 10 行含 "subprocess", 第 15 行含 "shell=True"
        lines = [""] * 20
        lines[9] = "subprocess.call(cmd)"
        lines[14] = "shell=True"

        # assert 1: min_keywords=2, 仅 1 个 keyword 匹配 → confirmed=False
        result = vf.verify_l3(lines, 10, ["subprocess"], min_keywords=2)
        assert result["confirmed"] is False
        assert "subprocess" in result.get("matched_keywords", [])

        # assert 2: min_keywords=1, 1 个 keyword 匹配 → confirmed=True (向后兼容)
        result = vf.verify_l3(lines, 10, ["subprocess"], min_keywords=1)
        assert result["confirmed"] is True
        # 兼容字段验证: v2.7 下游读取 matched_keyword (单数)
        assert result.get("matched_keyword") == "subprocess"
        assert result.get("matched_line") == 10

        # assert 3: min_keywords=2, 2 个 keyword 都匹配 → confirmed=True
        result = vf.verify_l3(lines, 10, ["subprocess", "shell"], min_keywords=2)
        assert result["confirmed"] is True
        assert len(result["matched_keywords"]) >= 2
        # 兼容字段
        assert result.get("matched_keyword") in ("subprocess", "shell")


# ════════════════════════════════════════════════════════════
# T3: L8.3.1.1-L8.3.1.6 — Semgrep JSON 转换器
# ════════════════════════════════════════════════════════════


class TestT3SemgrepConversion:
    """L8.3.1.1-L8.3.1.6: Semgrep 转换器."""

    @pytest.fixture
    def semgrep_module(self):
        return _load_module("semgrep_t3", HERE / "semgrep_to_findings.py")

    def _make_semgrep_json(self, results):
        return {"results": results}

    def test_L8_3_1_1_check_id_to_finding_id(self, semgrep_module, tmp_path):
        """L8.3.1.1: check_id → id (前缀 SG-)."""
        data = self._make_semgrep_json([
            {"check_id": "python.dangerous-subprocess-use", "path": "src/main.py",
             "start": {"line": 42}, "extra": {"message": "test", "severity": "ERROR",
             "metadata": {}}}
        ])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert len(findings) == 1
        assert findings[0]["id"].startswith("SG-")

    def test_L8_3_1_2_severity_mapping(self, semgrep_module, tmp_path):
        """L8.3.1.2: ERROR→P0, WARNING→P1, INFO→P2."""
        data = self._make_semgrep_json([
            {"check_id": "r1", "path": "a.py", "start": {"line": 1},
             "extra": {"message": "m", "severity": "ERROR", "metadata": {}}},
            {"check_id": "r2", "path": "b.py", "start": {"line": 2},
             "extra": {"message": "m", "severity": "WARNING", "metadata": {}}},
            {"check_id": "r3", "path": "c.py", "start": {"line": 3},
             "extra": {"message": "m", "severity": "INFO", "metadata": {}}},
        ])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        severities = [f["severity"] for f in findings]
        assert severities == ["P0", "P1", "P2"]

    def test_L8_3_1_3_path_and_line(self, semgrep_module, tmp_path):
        """L8.3.1.3: path → evidence.file, start.line → evidence.line_start."""
        data = self._make_semgrep_json([
            {"check_id": "r1", "path": "src/main.py", "start": {"line": 42},
             "extra": {"message": "m", "severity": "ERROR", "metadata": {}}}
        ])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert findings[0]["evidence"]["file"] == "src/main.py"
        assert findings[0]["evidence"]["line_start"] == 42

    def test_L8_3_1_4_claim_template(self, semgrep_module, tmp_path):
        """L8.3.1.4: Claim 模板: {check_id}: {message} ({cwe}) — affects {path}:{line}."""
        data = self._make_semgrep_json([
            {"check_id": "python.dangerous-subprocess-use", "path": "src/main.py",
             "start": {"line": 42},
             "extra": {"message": "Dangerous subprocess use", "severity": "ERROR",
             "metadata": {"cwe": ["CWE-78: OS Command Injection"]}}}
        ])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        claim = findings[0]["claim"]
        assert "python.dangerous-subprocess-use" in claim
        assert "Dangerous subprocess use" in claim
        assert "CWE-78" in claim
        assert "src/main.py:42" in claim

    def test_L8_3_1_5_cwe_array_handling(self, semgrep_module, tmp_path):
        """L8.3.1.5: cwe 数组类型处理 + owasp 数组."""
        data = self._make_semgrep_json([
            {"check_id": "r1", "path": "a.py", "start": {"line": 1},
             "extra": {"message": "m", "severity": "ERROR",
             "metadata": {
                 "cwe": ["CWE-78: OS Command Injection', 'CWE-77: Command Injection"],
                 "owasp": ["A1: Injection", "A3: Injection"],
             }}}
        ])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert findings[0]["evidence"]["cwe"] == "CWE-78"
        assert findings[0]["evidence"]["owasp"] == "A1: Injection"

    def test_L8_3_1_6_empty_results_and_missing_cwe(self, semgrep_module, tmp_path):
        """L8.3.1.6: 空 results 不崩溃 + cwe 缺失时 evidence.cwe 为空."""
        # 空 results
        data = self._make_semgrep_json([])
        inp = tmp_path / "semgrep.json"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        semgrep_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert findings == []

        # cwe 缺失
        data2 = self._make_semgrep_json([
            {"check_id": "r1", "path": "a.py", "start": {"line": 1},
             "extra": {"message": "m", "severity": "ERROR", "metadata": {}}}
        ])
        inp2 = tmp_path / "semgrep2.json"
        inp2.write_text(json.dumps(data2), encoding="utf-8")
        out2 = tmp_path / "out2"
        out2.mkdir()
        semgrep_module.main([str(inp2), "--output", str(out2)])
        findings2 = json.loads((out2 / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings2, dict):
            findings2 = findings2.get("findings", [])
        assert findings2[0]["evidence"]["cwe"] == ""


# ════════════════════════════════════════════════════════════
# T4: L8.4.1.1-L8.4.1.6 — CodeQL SARIF 转换器
# ════════════════════════════════════════════════════════════


class TestT4CodeQLConversion:
    """L8.4.1.1-L8.4.1.6: CodeQL SARIF 转换器."""

    @pytest.fixture
    def codeql_module(self):
        return _load_module("codeql_t4", HERE / "codeql_to_findings.py")

    def _make_sarif(self, results, rules=None):
        return {
            "runs": [{
                "results": results,
                "tool": {"driver": {"rules": rules or []}}
            }]
        }

    def test_L8_4_1_1_rule_id_to_finding_id(self, codeql_module, tmp_path):
        """L8.4.1.1: ruleId → id (前缀 QL-) + evidence.rule_id."""
        data = self._make_sarif([
            {"ruleId": "py/command-injection", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main.py"},
             "region": {"startLine": 42}}}], "message": {"text": "test"}}
        ])
        inp = tmp_path / "codeql.sarif"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        codeql_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert len(findings) == 1
        assert findings[0]["id"].startswith("QL-")
        assert findings[0]["evidence"]["rule_id"] == "py/command-injection"

    def test_L8_4_1_2_level_mapping(self, codeql_module, tmp_path):
        """L8.4.1.2: error→P0, warning→P1, note→P2."""
        data = self._make_sarif([
            {"ruleId": "r1", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "a.py"},
             "region": {"startLine": 1}}}], "message": {"text": "m"}},
            {"ruleId": "r2", "level": "warning",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "b.py"},
             "region": {"startLine": 2}}}], "message": {"text": "m"}},
            {"ruleId": "r3", "level": "note",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "c.py"},
             "region": {"startLine": 3}}}], "message": {"text": "m"}},
        ])
        inp = tmp_path / "codeql.sarif"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        codeql_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        severities = [f["severity"] for f in findings]
        assert severities == ["P0", "P1", "P2"]

    def test_L8_4_1_3_sarif_field_mapping_and_cwe_tags(self, codeql_module, tmp_path):
        """L8.4.1.3: locations[0].physicalLocation → evidence.file/line_start + cwe tags 解析."""
        data = self._make_sarif([
            {"ruleId": "py/command-injection", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main.py"},
             "region": {"startLine": 42}}}], "message": {"text": "Command injection"}}
        ], rules=[
            {"id": "py/command-injection",
             "properties": {"tags": ["security", "external/cwe/cwe-78"]}}
        ])
        inp = tmp_path / "codeql.sarif"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        codeql_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert findings[0]["evidence"]["file"] == "src/main.py"
        assert findings[0]["evidence"]["line_start"] == 42
        assert findings[0]["evidence"]["cwe"] == "CWE-78"

    def test_L8_4_1_4_claim_template(self, codeql_module, tmp_path):
        """L8.4.1.4: Claim: {ruleId}: {message_text} ({cwe_tags}) — affects {uri}:{startLine}."""
        data = self._make_sarif([
            {"ruleId": "py/command-injection", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "src/main.py"},
             "region": {"startLine": 42}}}], "message": {"text": "Command injection"}}
        ], rules=[
            {"id": "py/command-injection",
             "properties": {"tags": ["security", "external/cwe/cwe-78"]}}
        ])
        inp = tmp_path / "codeql.sarif"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        codeql_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        claim = findings[0]["claim"]
        assert "py/command-injection" in claim
        assert "Command injection" in claim
        assert "CWE-78" in claim
        assert "src/main.py:42" in claim

    def test_L8_4_1_5_missing_cwe_tags(self, codeql_module, tmp_path):
        """L8.4.1.5: tags 中无 cwe 标签时不崩溃 + tags 字段缺失."""
        # tags 中无 cwe
        data1 = self._make_sarif([
            {"ruleId": "r1", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "a.py"},
             "region": {"startLine": 1}}}], "message": {"text": "m"}}
        ], rules=[
            {"id": "r1", "properties": {"tags": ["security", "maintainability"]}}
        ])
        inp1 = tmp_path / "c1.sarif"
        inp1.write_text(json.dumps(data1), encoding="utf-8")
        out1 = tmp_path / "o1"
        out1.mkdir()
        codeql_module.main([str(inp1), "--output", str(out1)])
        f1 = json.loads((out1 / "findings.json").read_text(encoding="utf-8"))
        if isinstance(f1, dict):
            f1 = f1.get("findings", [])
        assert f1[0]["evidence"]["cwe"] == ""

        # tags 字段缺失
        data2 = self._make_sarif([
            {"ruleId": "r2", "level": "error",
             "locations": [{"physicalLocation": {"artifactLocation": {"uri": "b.py"},
             "region": {"startLine": 2}}}], "message": {"text": "m"}}
        ], rules=[{"id": "r2", "properties": {}}])
        inp2 = tmp_path / "c2.sarif"
        inp2.write_text(json.dumps(data2), encoding="utf-8")
        out2 = tmp_path / "o2"
        out2.mkdir()
        codeql_module.main([str(inp2), "--output", str(out2)])
        f2 = json.loads((out2 / "findings.json").read_text(encoding="utf-8"))
        if isinstance(f2, dict):
            f2 = f2.get("findings", [])
        assert f2[0]["evidence"]["cwe"] == ""

    def test_L8_4_1_6_empty_results(self, codeql_module, tmp_path):
        """L8.4.1.6: runs[0].results: [] 时不崩溃, 输出空 findings.json."""
        data = self._make_sarif([])
        inp = tmp_path / "codeql.sarif"
        inp.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "out"
        out.mkdir()
        codeql_module.main([str(inp), "--output", str(out)])
        findings = json.loads((out / "findings.json").read_text(encoding="utf-8"))
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        assert findings == []


# ════════════════════════════════════════════════════════════
# T5: L8.5.1.1-L8.5.1.5 — CWE Top 25 规则映射表
# ════════════════════════════════════════════════════════════


class TestT5CWERules:
    """L8.5.1.1-L8.5.1.5: CWE Top 25 规则."""

    @pytest.fixture
    def cwe_module(self):
        return _load_module("cwe_t5", HERE / "cwe_rules.py")

    def test_L8_5_1_1_cwe_top_25_completeness(self, cwe_module):
        """L8.5.1.1: CWE_TOP_25_2023 含 25 条 + 每条含 name/rank/category + rank 值正确."""
        table = cwe_module.CWE_TOP_25_2023
        assert len(table) == 25
        for cwe_id, info in table.items():
            assert "name" in info, f"{cwe_id} missing name"
            assert "rank" in info, f"{cwe_id} missing rank"
            assert "category" in info, f"{cwe_id} missing category"
        # rank 值正确性 (H5 修正点 — 5 处)
        assert table["CWE-787"]["rank"] == 1   # Out-of-bounds Write
        assert table["CWE-416"]["rank"] == 4   # Use-After-Free
        assert table["CWE-78"]["rank"] == 5    # OS Command Injection
        assert table["CWE-125"]["rank"] == 7   # Out-of-bounds Read
        assert table["CWE-352"]["rank"] == 9   # CSRF

    def test_L8_5_1_2_enrich_finding_with_cwe(self, cwe_module):
        """L8.5.1.2: enrich_finding_with_cwe 添加 cwe_rank + cwe_category."""
        finding = {
            "id": "SG-0001", "severity": "P1",
            "claim": "subprocess injection (CWE-78)",
            "evidence": {"cwe": "CWE-78"}
        }
        cwe_module.enrich_finding_with_cwe(finding)
        assert finding["evidence"]["cwe_rank"] == 5
        assert finding["evidence"]["cwe_category"] == "injection"
        assert finding["evidence"]["cwe_name"] == "OS Command Injection"

    def test_L8_5_1_3_classify_cwe_severity(self, cwe_module):
        """L8.5.1.3: classify_cwe_severity 根据 category 调整 severity."""
        # memory/injection → P0
        f1 = {"severity": "P2", "evidence": {"cwe_category": "memory"}}
        cwe_module.classify_cwe_severity(f1)
        assert f1["severity"] == "P0"

        f2 = {"severity": "P2", "evidence": {"cwe_category": "injection"}}
        cwe_module.classify_cwe_severity(f2)
        assert f2["severity"] == "P0"

        # 其他类 → 保持原 severity
        f3 = {"severity": "P2", "evidence": {"cwe_category": "web"}}
        cwe_module.classify_cwe_severity(f3)
        assert f3["severity"] == "P2"

    def test_L8_5_1_4_get_cwe_claim_keywords(self, cwe_module):
        """L8.5.1.4: get_cwe_claim_keywords 返回关键词列表."""
        kws = cwe_module.get_cwe_claim_keywords("CWE-78")
        assert isinstance(kws, list)
        assert len(kws) > 0
        # CWE-78 是 injection 类, 应含 inject/sql/command 等关键词
        assert any(k in kws for k in ("inject", "sql", "command", "exec", "shell"))

        # 不在 Top 25 → 空列表
        assert cwe_module.get_cwe_claim_keywords("CWE-9999") == []

    def test_L8_5_1_5_enrich_no_cwe_no_crash(self, cwe_module):
        """L8.5.1.5: enrich_finding_with_cwe 对无 CWE 的 finding 不崩溃 (边界 case)."""
        finding = {"id": "X-001", "severity": "P2", "claim": "no cwe here",
                   "evidence": {}}
        # 不应抛出异常
        cwe_module.enrich_finding_with_cwe(finding)
        # 无 CWE 时不添加 cwe_rank
        assert "cwe_rank" not in finding.get("evidence", {})


# ════════════════════════════════════════════════════════════
# T6: L8.6.1.1-L8.6.1.3 — Linux kernel 批量下载 (mock)
# ════════════════════════════════════════════════════════════


class TestT6LinuxBatch:
    """L8.6.1.1-L8.6.1.3: Linux 批量下载 (mock, 不实际下载)."""

    @pytest.fixture
    def linux_module(self):
        return _load_module("linux_t6", HERE / "download_linux_commits.py")

    def test_L8_6_1_1_progress_resume(self, linux_module, tmp_path):
        """L8.6.1.1: 断点续传 — progress.json 存在时跳过已下载 commit."""
        # 构造 progress.json, 含 2 个已下载 commit
        progress_path = tmp_path / "progress.json"
        progress_data = {
            "downloaded": [
                {"commit": "abc123", "status": "ok"},
                {"commit": "def456", "status": "ok"},
            ]
        }
        progress_path.write_text(json.dumps(progress_data), encoding="utf-8")

        loaded = linux_module.load_progress(progress_path)
        assert "abc123" in loaded
        assert "def456" in loaded
        assert loaded["abc123"] == "ok"
        assert loaded["def456"] == "ok"

        # 空路径 → 空字典
        assert linux_module.load_progress(tmp_path / "nonexistent.json") == {}

    def test_L8_6_1_2_batch_logic(self, linux_module, monkeypatch):
        """L8.6.1.2: --batch-size 50 分批 + --batch-delay 60 间隔."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

        # 110 findings, batch_size=50 → 3 batches (50+50+10), 2 delays
        findings = [{"id": f"F{i:04d}", "evidence": {"commit_hash": f"c{i}"}
                     } for i in range(110)]

        # mock fetch + extract → 全部成功
        def mock_process(f, repo, dest):
            return True, ""
        monkeypatch.setattr(linux_module, "process_single_finding", mock_process)

        success, fail = linux_module.batch_download(
            findings, repo_path=tmp_path if False else Path("/tmp/test"),
            dest_base=Path("/tmp/test_dest"),
            batch_size=50, batch_delay=60, retry=1, retry_delay=0,
            progress={}
        )
        # 3 batches → 2 delays (batch_delay between batches)
        assert success == 110
        assert fail == 0
        # batch_delay 应被调用 (50 个 finding 每个会有 retry_delay=0 sleep, 加 2 个 batch_delay)
        # 这里只验证 batch_delay 被调用
        assert 60 in sleep_calls or len(sleep_calls) >= 2

    def test_L8_6_1_3_retry_mechanism(self, linux_module, monkeypatch):
        """L8.6.1.3: 单 commit 失败重试 3 次."""
        sleep_calls = []
        monkeypatch.setattr("time.sleep", lambda s: sleep_calls.append(s))

        call_count = [0]

        def mock_process_fail_then_succeed(f, repo, dest):
            call_count[0] += 1
            if call_count[0] < 3:  # 前 2 次失败
                return False, "network error"
            return True, ""  # 第 3 次成功

        monkeypatch.setattr(linux_module, "process_single_finding",
                            mock_process_fail_then_succeed)

        findings = [{"id": "F0001", "evidence": {"commit_hash": "c1"}}]
        success, fail = linux_module.batch_download(
            findings, repo_path=Path("/tmp/test"),
            dest_base=Path("/tmp/test_dest"),
            batch_size=50, batch_delay=0, retry=3, retry_delay=30,
            progress={}
        )
        # 重试 3 次, 第 3 次成功
        assert call_count[0] == 3
        assert success == 1
        assert fail == 0


if __name__ == "__main__":
    # 支持 python scripts/test_v28_consistency.py 直接运行
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
