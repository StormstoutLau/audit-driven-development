"""v3.0 T20 TDD: Findings schema 激活一致性套件（35 项）。

覆盖 T1 schema(5) / T2 校验器(13) / T3 Semgrep(5) / T4 CodeQL(3) /
      T5 消费端(4) / T6 golden case(2) / T7 兼容(3)。

运行（本机 python 无 pytest，必须用 py）:
    py -m pytest scripts/test_v30_t20_findings_schema_consistency.py -v

对应: 设计 spec v1.3 AC-1~AC-22 / 实施规范 v1.2 §7。
"""

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import validate_findings as V  # noqa: E402
import semgrep_to_findings as SG  # noqa: E402
import codeql_to_findings as QL  # noqa: E402
import issues_tracker as IT  # noqa: E402
import inter_rater as IR  # noqa: E402
import verify_findings as VF  # noqa: E402
import contract_graph as CG  # noqa: E402

_REPO_ROOT = _HERE.parent
_SAST_SCHEMA_PATH = _REPO_ROOT / "schemas" / "sast-finding.schema.json"
_AUDIT_SCHEMA_PATH = _REPO_ROOT / "schemas" / "audit-finding.schema.json"
_AUDIT_REPORT_PATH = _REPO_ROOT / "schemas" / "example-audit-report.json"

_CORPUS_FILES = [
    "docs/benchmark/bigvul/findings.json",
    "docs/benchmark/bigvul/findings_nonlinux.json",
    "docs/benchmark/bigvul/findings_test5.json",
    "docs/benchmark/cvefixes/findings.json",
    "docs/benchmark/defects4j/findings.json",
    "docs/benchmark/add-v2.4-self-audit/findings.json",
    "docs/benchmark/itsdangerous-2.2.0/findings.json",
    "docs/benchmark/stdlib-oss-test/findings.json",
]


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_state():
    """清图缓存与 kill switch，避免跨用例污染。"""
    CG._GRAPH_CACHE.clear()
    for var in ("ADD_CONTRACT_DISABLE", "ADD_TAINT_DISABLE"):
        os.environ.pop(var, None)
    yield
    CG._GRAPH_CACHE.clear()
    for var in ("ADD_CONTRACT_DISABLE", "ADD_TAINT_DISABLE"):
        os.environ.pop(var, None)


@pytest.fixture(scope="module")
def sast_schema():
    return V.load_schema(str(_SAST_SCHEMA_PATH))


def _semgrep_fixture(metadata=None, dataflow_trace=None):
    extra = {"message": "msg", "severity": "ERROR", "metadata": metadata or {}}
    if dataflow_trace is not None:
        extra["dataflow_trace"] = dataflow_trace
    return {
        "check_id": "python.lang.security.test",
        "path": "src/a.py",
        "start": {"line": 1, "col": 1},
        "extra": extra,
    }


def _codeql_fixture(rule_id="py/command-injection", code_flows=None):
    result = {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": "msg"},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": "src/a.py"},
                "region": {"startLine": 1},
            }
        }],
    }
    if code_flows is not None:
        result["codeFlows"] = code_flows
    return result


def _converter_fixtures():
    """6 个转换器的合成最小产物（synthetic，非语料）。"""
    return {
        "semgrep": SG.convert_semgrep_result(_semgrep_fixture(), 0),
        "codeql": QL.convert_codeql_result(_codeql_fixture(), 0, {}),
        "bigvul": __import__("bigvul_to_findings").convert_bigvul_row(
            {"vul": "1", "func_before": "void foo(void) {}", "lines_before": "10",
             "cwe_id": "CWE-79", "cvss": "5.0", "cve_summary": "s",
             "_file_path": "src/a.c"}, 0),
        "cvefixes": __import__("cvefixes_to_findings").convert_cvefixes_record(
            {"cwe_id": "CWE-79", "cve_summary": "s", "cvss_score": "5.0",
             "project_name": "p", "file_path": "src/a.py", "line_start": 1,
             "func_name": "f"}, 0),
        "defects4j": __import__("defects4j_to_findings").convert_defects4j_bug(
            {"file_path": "src/A.java", "line_start": "5", "project": "P",
             "commit_hash": "abc1234", "commit_message": "m"}, 0),
        "swebench": __import__("swebench_to_findings").convert_swebench_instance(
            {"patch": "--- a/src/a.py\n+++ b/src/a.py\n@@ -5,3 +5,3 @@\n-a\n+b\n",
             "problem_statement": "bug"}, 0),
    }


# ── T1 Schema（5 项）────────────────────────────────────────────────────


class TestT1Schema:
    def test_T1_01_schema_exists_and_loads(self, sast_schema):
        assert _SAST_SCHEMA_PATH.exists()
        assert isinstance(sast_schema, dict)
        assert sast_schema["$id"].endswith("sast-finding.schema.json")

    def test_T1_02_category_enum_matches_canonical(self, sast_schema):
        canonical = json.loads(_AUDIT_SCHEMA_PATH.read_text(encoding="utf-8"))
        expected = canonical["definitions"]["Category"]["enum"]
        actual = sast_schema["properties"]["category"]["enum"]
        assert actual == expected

    def test_T1_03_corpus_all_pass(self, sast_schema):
        total = 0
        errors = []
        for rel in _CORPUS_FILES:
            path = _REPO_ROOT / rel
            data = json.loads(path.read_text(encoding="utf-8"))
            total += len(data.get("findings", []))
            errors.extend(V.validate_file(str(path), sast_schema))
        assert errors == []
        assert total == 882

    def test_T1_04_converter_fixtures_pass(self, sast_schema):
        for name, finding in _converter_fixtures().items():
            assert finding is not None, name
            assert V.validate(finding, sast_schema, sast_schema) == [], name

    def test_T1_05_unknown_top_level_key_rejected(self, sast_schema):
        finding = SG.convert_semgrep_result(_semgrep_fixture(), 0)
        finding["mystery"] = 1
        errors = V.validate(finding, sast_schema, sast_schema)
        assert errors


# ── T2 Validator（13 项）────────────────────────────────────────────────


class TestT2Validator:
    def test_T2_01_required_missing(self):
        schema = {"type": "object", "required": ["a"]}
        assert V.validate({}, schema, schema)

    def test_T2_02_type_mismatch(self):
        schema = {"type": "integer"}
        assert V.validate("5", schema, schema)

    def test_T2_03_bool_is_not_integer(self):
        schema = {"type": "integer"}
        assert V.validate(True, schema, schema)

    def test_T2_04_enum_violation(self):
        schema = {"enum": ["P0", "P1"]}
        assert V.validate("HIGH", schema, schema)

    def test_T2_05_pattern_mismatch(self):
        schema = {"type": "string", "pattern": "^[A-Z]+-[0-9]+$"}
        assert V.validate("bad id", schema, schema)
        assert V.validate("OK-1", schema, schema) == []

    def test_T2_06_minimum_violation(self):
        schema = {"type": "integer", "minimum": 1}
        assert V.validate(0, schema, schema)
        assert V.validate(1, schema, schema) == []

    def test_T2_07_min_length(self):
        schema = {"type": "string", "minLength": 2}
        assert V.validate("a", schema, schema)
        assert V.validate("ab", schema, schema) == []

    def test_T2_08_ref_resolution(self):
        schema = {
            "definitions": {"S": {"type": "string", "enum": ["ok"]}},
            "$ref": "#/definitions/S",
        }
        assert V.validate("ok", schema, schema) == []
        assert V.validate("bad", schema, schema)

    def test_T2_09_broken_ref_raises(self):
        with pytest.raises(V.SchemaError):
            V.resolve_ref({"definitions": {}}, "#/definitions/Missing")
        with pytest.raises(V.SchemaError):
            V.resolve_ref({}, "#/properties/x")

    def test_T2_10_unsupported_keyword_raises(self):
        with pytest.raises(V.SchemaError):
            V.check_keywords({"type": "object", "oneOf": []})

    def test_T2_11_format_date(self):
        schema = {"type": "string", "format": "date"}
        assert V.validate("2026-10-20", schema, schema) == []
        assert V.validate("2026-13-01", schema, schema)
        assert V.validate("20261020", schema, schema)

    def test_T2_12_nested_path_in_message(self, sast_schema):
        finding = SG.convert_semgrep_result(_semgrep_fixture(), 0)
        finding["evidence"]["file"] = ""
        errors = V.validate(finding, sast_schema, sast_schema)
        assert any("$.evidence.file" in e for e in errors)

    def test_T2_13_additional_properties_schema_form(self, sast_schema):
        schema = {
            "type": "object",
            "additionalProperties": {"type": "integer"},
        }
        assert V.validate({"x": 1}, schema, schema) == []
        assert V.validate({"x": "s"}, schema, schema)
        # canonical AuditReport 的 summary.module_scores 正是 schema 形式 (G-4)
        audit_schema = V.load_schema(str(_AUDIT_SCHEMA_PATH))
        assert V.validate_file(str(_AUDIT_REPORT_PATH), audit_schema) == []


# ── T3 Semgrep（5 项）────────────────────────────────────────────────────


class TestT3Semgrep:
    def test_T3_01_add_category_passthrough(self):
        f = SG.convert_semgrep_result(
            _semgrep_fixture(metadata={"add_category": "contract"}), 0)
        assert f["category"] == "contract"

    def test_T3_02_invalid_value_omitted(self):
        f = SG.convert_semgrep_result(
            _semgrep_fixture(metadata={"add_category": "security"}), 0)
        assert "category" not in f

    def test_T3_03_missing_omitted(self):
        f = SG.convert_semgrep_result(_semgrep_fixture(), 0)
        assert "category" not in f

    def test_T3_04_dataflow_trace_marks_taint(self):
        f = SG.convert_semgrep_result(
            _semgrep_fixture(dataflow_trace=[{"a": 1}]), 0)
        assert f["evidence"]["analysis_kind"] == "taint"

    def test_T3_05_missing_dataflow_omitted(self):
        f = SG.convert_semgrep_result(_semgrep_fixture(), 0)
        assert "analysis_kind" not in f["evidence"]


# ── T4 CodeQL（3 项）─────────────────────────────────────────────────────


class TestT4CodeQL:
    def test_T4_01_code_flows_marks_taint(self):
        f = QL.convert_codeql_result(
            _codeql_fixture(code_flows=[{"threadFlows": []}]), 0, {})
        assert f["evidence"]["analysis_kind"] == "taint"

    def test_T4_02_missing_code_flows_omitted(self):
        f = QL.convert_codeql_result(_codeql_fixture(), 0, {})
        assert "analysis_kind" not in f["evidence"]

    def test_T4_03_rule_name_not_inferred(self):
        f = QL.convert_codeql_result(
            _codeql_fixture(rule_id="py/sql-injection"), 0, {})
        assert "analysis_kind" not in f["evidence"]
        assert "category" not in f


# ── T5 Consumers（4 项）─────────────────────────────────────────────────


def _report_without_category():
    return {
        "audit_metadata": {"audit_date": "2026-10-20"},
        "module_results": [{
            "findings": [{
                "id": "MOD-P0-1", "severity": "P0", "claim": "c",
                "evidence": {"file": "a.py", "line_start": 1},
            }]
        }],
    }


class TestT5Consumers:
    def test_T5_01_issues_tracker_no_exception(self, tmp_path, monkeypatch):
        report = tmp_path / "report.json"
        report.write_text(json.dumps(_report_without_category()), encoding="utf-8")
        monkeypatch.setattr(IT, "ISSUES_FILE", tmp_path / "issues.json")
        IT.cmd_init(str(report))  # 不抛异常即通过

    def test_T5_02_issues_tracker_writes_unknown(self, tmp_path, monkeypatch):
        report = tmp_path / "report.json"
        report.write_text(json.dumps(_report_without_category()), encoding="utf-8")
        out = tmp_path / "issues.json"
        monkeypatch.setattr(IT, "ISSUES_FILE", out)
        IT.cmd_init(str(report))
        issues = json.loads(out.read_text(encoding="utf-8"))["issues"]
        assert issues[0]["category"] == "unknown"

    def test_T5_03_inter_rater_unknown_bucket(self, tmp_path):
        payload = {"findings": [{
            "id": "A-P0-1", "severity": "P0", "claim": "c",
            "evidence": {"file": "a.py", "line_start": 1},
        }]}
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(payload), encoding="utf-8")
        b.write_text(json.dumps(payload), encoding="utf-8")
        result = IR.compute_per_dimension_kappa(str(a), str(b), set())
        assert "unknown" in result
        assert result["unknown"]["matrix"] is not None
        assert result["unknown"]["matrix"]["a_both"] == 1

    def test_T5_04_categorized_grouping_unchanged(self, tmp_path):
        payload = {"findings": [{
            "id": "A-P0-1", "severity": "P0", "category": "behavior",
            "claim": "c", "evidence": {"file": "a.py", "line_start": 1},
        }]}
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(payload), encoding="utf-8")
        b.write_text(json.dumps(payload), encoding="utf-8")
        result = IR.compute_per_dimension_kappa(str(a), str(b), set())
        assert result["behavior"]["matrix"]["a_both"] == 1
        assert "unknown" in result


# ── T6 Golden case（2 项）───────────────────────────────────────────────


def _golden_finding(with_category=True):
    finding = {
        "id": "T20-P0-1", "severity": "P0",
        "spec_ref": "ADR-028 §D3", "confidence": "high", "fix_cost": "1-line",
        # claim 刻意不含 CONTRACT_PATTERNS 文本 ⇒ 只有 category 通道能触发
        "claim": "verify_findings imports ast_cfg",
        "evidence": {"file": "scripts/verify_findings.py",
                     "line_start": 1, "line_end": 1},
    }
    if with_category:
        finding["category"] = "contract"
    return finding


class TestT6GoldenCase:
    def test_T6_01_category_activates_contract_channel(self):
        result, action = VF.verify_single_finding(
            _golden_finding(True), str(_REPO_ROOT))
        assert result["contract_verified"] is False
        assert action == "unverified"
        assert result["action"] == "unverified"

    def test_T6_02_no_category_no_contract_key(self):
        result, _ = VF.verify_single_finding(
            _golden_finding(False), str(_REPO_ROOT))
        assert "contract_verified" not in result


# ── T7 Compat（3 项）────────────────────────────────────────────────────


class TestT7Compat:
    def test_T7_01_legacy_fields_preserved(self):
        fixtures = _converter_fixtures()
        for name in ("semgrep", "codeql", "bigvul", "cvefixes", "defects4j"):
            assert "dimension" in fixtures[name], name
            assert "l4_eligible" in fixtures[name], name
            assert fixtures[name]["l4_eligible"] is False or name in (
                "semgrep", "codeql"), name
        assert "dimension" in fixtures["swebench"]

    def test_T7_02_l4_ineligible_still_skips(self):
        finding = {
            "id": "T20-P0-2", "severity": "P0", "l4_eligible": False,
            "claim": "verify_findings",
            "evidence": {"file": "scripts/verify_findings.py", "line_start": 1},
        }
        result, action = VF.verify_single_finding(finding, str(_REPO_ROOT))
        assert action == "partial"
        assert result["l4_skipped"] is True

    def test_T7_03_analysis_kind_only_in_evidence(self):
        f = SG.convert_semgrep_result(
            _semgrep_fixture(dataflow_trace=[{"a": 1}]), 0)
        assert "analysis_kind" not in f
        assert f["evidence"]["analysis_kind"] == "taint"
