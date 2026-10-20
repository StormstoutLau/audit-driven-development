"""v3.0 T19 TDD: 跨模块契约确定性验证一致性套件（37 项）。

覆盖 T1 识别(9) / T2 图与契约求值(13) / T3 端到端与降级(9) / T4 兼容与 kill switch(6)。

运行（本机 python 无 pytest，必须用 py）:
    py -m pytest scripts/test_v30_contract_consistency.py -v

对应: 设计 spec v1.1 AC-1~AC-26 / 实施规范 v1.1 §5。
"""

import json
import os
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import contract_graph as CG  # noqa: E402
import verify_findings as VF  # noqa: E402

_REPO_ROOT = _HERE.parent


# ── Fixtures / helpers ───────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_state():
    """每个用例前后清图缓存与 kill switch，避免跨用例污染。"""
    CG._GRAPH_CACHE.clear()
    for var in ("ADD_CONTRACT_DISABLE", "ADD_TAINT_DISABLE"):
        os.environ.pop(var, None)
    yield
    CG._GRAPH_CACHE.clear()
    for var in ("ADD_CONTRACT_DISABLE", "ADD_TAINT_DISABLE"):
        os.environ.pop(var, None)


def _write(repo: Path, rel: str, body: str):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _make_repo(tmp_path, files, guards=None, guards_name="guards.yml"):
    """合成 repo。files 的键是相对 repo 根的路径。"""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        _write(repo, rel, body)
    if guards is not None:
        _write(repo, "docs/audit/" + guards_name, guards)
    return repo


def _guards_yaml(layers, root="src", allow=None, kind="layers", rid="G101"):
    allow_block = ""
    if allow:
        pairs = ", ".join("[%s, %s]" % (repr(a), repr(b)) for a, b in allow)
        allow_block = "\n      allow: [%s]" % pairs
    return (
        "version: \"1.0\"\n"
        "guards:\n"
        "  - id: \"%s\"\n"
        "    description: \"layered contract\"\n"
        "    scope: \"src/**/*.py\"\n"
        "    severity: \"critical\"\n"
        "    check: \"free text\"\n"
        "    contract:\n"
        "      root: \"%s\"\n"
        "      kind: \"%s\"\n"
        "      layers: %s%s\n"
    ) % (rid, root, kind, json.dumps(layers), allow_block)


# 违规仓库: low -> top (被禁方向且有路径); top -> mid -> low (允许方向)
_LAYERS = ["top", "mid", "low", "solo"]
_FILES_VIOLATION = {
    "src/top.py": "import mid\n",
    "src/mid.py": "import low\n",
    "src/low.py": "import top\n",
    "src/solo.py": "# no imports\n",
}
_FILES_CLEAN = {
    "src/top.py": "import mid\n",
    "src/mid.py": "import low\n",
    "src/low.py": "# no imports\n",
    "src/solo.py": "# no imports\n",
}


# ── T1 识别 (9) ──────────────────────────────────────────────────────────


class TestT1Identification:
    def test_T1_01_category_channel_hit(self):
        types = VF.classify_claim("module boundary problem", None, "contract")
        assert "contract_related" in types and "generic" not in types

    def test_T1_02_analysis_kind_channel_hit(self):
        types = VF.classify_claim("module boundary problem",
                                  {"analysis_kind": "contract"})
        assert "contract_related" in types

    def test_T1_03_text_channel_hit(self):
        types = VF.classify_claim("layer violation between a and b")
        assert "contract_related" in types

    def test_T1_04_text_channel_negative(self):
        # 4 条负样本: 含 F-4 实测的噪声子串与普通标识符
        for claim in ("SQL injection in msPostGISLayerSetTimeFilter function",
                      "dead code after return in visit_FunctionDef",
                      "file contains a licensing contract header",
                      "layered architecture looks fine"):
            assert "contract_related" not in VF.classify_claim(claim), claim

    def test_T1_05_category_none_no_structured(self):
        types = VF.classify_claim("module boundary problem", None, None)
        assert "contract_related" not in types
        types2 = VF.classify_claim("module boundary problem", {})
        assert "contract_related" not in types2

    def test_T1_06_coexist_with_import_related(self):
        types = VF.classify_claim(
            "circular dependency between ast_cfg and verify_findings; layer violation",
            None, "contract")
        assert "import_related" in types and "contract_related" in types

    def test_T1_07_kill_switch_no_hit(self):
        os.environ["ADD_CONTRACT_DISABLE"] = "1"
        assert "contract_related" not in VF.classify_claim(
            "layer violation between a and b", None, "contract")

    def test_T1_08_signature_backward_compatible(self):
        # 不传 category ⇒ 与既有行为一致（无结构化命中）
        samples = ["missing null check", "circular dependency between a and b",
                   "dead code after return", "wrong return type"]
        for s in samples:
            assert VF.classify_claim(s) == VF.classify_claim(s, None, None)

    def test_T1_09_no_false_positive_on_existing_types(self):
        assert VF.classify_claim("missing error handling") == ["missing"]
        assert "import_related" in VF.classify_claim("circular dependency between a and b")
        assert VF.classify_claim("unrelated note about widget sizes") == ["generic"]


# ── T2 图与契约求值 (13) ─────────────────────────────────────────────────


class TestT2GraphAndEvaluation:
    def test_T2_10_allowed_direction_false(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        r = CG.verify_contract(str(repo), "top imports mid")
        assert r is not None and r["verified"] is False and r["tier"] == 2

    def test_T2_11_forbidden_direction_true(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        r = CG.verify_contract(str(repo), "low imports top")
        assert r is not None and r["verified"] is True and r["tier"] == 2

    def test_T2_12_indirect_forbidden_true(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        r = CG.verify_contract(str(repo), "mid imports top")  # mid->low->top
        assert r is not None and r["verified"] is True
        assert r["path"] == ["mid", "low", "top"]

    def test_T2_13_forbidden_no_path_false(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        r = CG.verify_contract(str(repo), "solo imports top")  # solo 无出边
        assert r is not None and r["verified"] is False and r["path"] is None

    def test_T2_14_allow_exception_false(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION,
                          _guards_yaml(_LAYERS, allow=[["low", "top"]]))
        r = CG.verify_contract(str(repo), "low imports top")
        assert r is not None and r["verified"] is False

    def test_T2_15_allow_does_not_affect_allowed_direction(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION,
                          _guards_yaml(_LAYERS, allow=[["low", "top"]]))
        r = CG.verify_contract(str(repo), "top imports mid")
        assert r is not None and r["verified"] is False  # 允许方向本就为 False

    def test_T2_16_direction_and_layer_edges_none(self, tmp_path):
        files = {
            "src/pkg/__init__.py": "",
            "src/pkg/a.py": "import pkg.b\n",
            "src/pkg/b.py": "",
        }
        repo = _make_repo(tmp_path, files, _guards_yaml(["pkg", "other"], root="src"))
        # 同层 (pkg.a -> pkg.b) ⇒ None
        assert CG.verify_contract(str(repo), "pkg.a imports pkg.b") is None
        # 方向不可判定 (between / among) ⇒ None
        assert CG.verify_contract(str(repo), "layer violation between pkg.a and pkg.b") is None
        # 自环 ⇒ None (H4)
        assert CG.verify_contract(str(repo), "pkg.a imports itself") is None

    def test_T2_17_layer_prefix_mapping(self):
        assert CG.layer_of("a.b.c", ["a", "a.b"]) == "a.b"
        assert CG.layer_of("a.x", ["a", "a.b"]) == "a"
        assert CG.layer_of("z", ["a", "a.b"]) is None

    def test_T2_18_unmapped_module_ignored(self, tmp_path):
        files = dict(_FILES_VIOLATION)
        files["src/zzz.py"] = "import top\n"
        repo = _make_repo(tmp_path, files, _guards_yaml(["top", "mid"]))
        # zzz 未命中任何层 ⇒ 声明不覆盖 ⇒ None（不是 False）
        assert CG.verify_contract(str(repo), "zzz imports top") is None

    def test_T2_19_module_absent_none(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        assert CG.verify_contract(str(repo), "ghost imports top") is None

    def test_T2_20_invalid_layers_none(self, tmp_path):
        for layers, kind in ((["top"], "layers"),
                             (["top", "top"], "layers"),
                             (["top", "low"], "forbidden"),
                             ([], "layers")):
            repo = _make_repo(tmp_path, _FILES_VIOLATION,
                              _guards_yaml(layers, kind=kind))
            assert CG.verify_contract(str(repo), "low imports top") is None

    def test_T2_21_graph_sentinel_none(self, tmp_path):
        # 2 模块 / 0 边 ⇒ 哨兵 ⇒ None（绝不 False）
        files = {"src/a.py": "# none\n", "src/b.py": "# none\n"}
        repo = _make_repo(tmp_path, files, _guards_yaml(["a", "b"]))
        assert CG.verify_contract(str(repo), "b imports a") is None

    def test_T2_22_rule_id_and_path_in_evidence(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS, rid="G777"))
        r = CG.verify_contract(str(repo), "low imports top")
        assert r["rule_id"] == "G777" and r["kind"] == "layers"
        assert r["modules"] == {"src": "low", "dst": "top"}
        assert r["path"] == ["low", "top"]
        assert r["reason"] == "layer_violation_confirmed"


# ── T3 端到端与降级 (9) ──────────────────────────────────────────────────


def _finding(repo_rel_file, line=1, claim="", category=None, severity="P0"):
    f = {"id": "T19-1", "severity": severity, "claim": claim,
         "evidence": {"file": repo_rel_file, "line_start": line, "line_end": line}}
    if category:
        f["category"] = category
    return f


class TestT3EndToEnd:
    def test_T3_23_true_yields_verified(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        monkeypatch.chdir(repo)
        _write(repo, "scripts/x.py", "import top\n")
        res, action = VF.verify_single_finding(
            _finding("scripts/x.py", 1, "low imports top", category="contract"), str(repo))
        assert res["verification_level"] == 4 and action == "verified"
        assert res["contract_verified"] is True

    def test_T3_24_false_yields_unverified(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        monkeypatch.chdir(repo)
        _write(repo, "scripts/x.py", "import top\n")
        res, action = VF.verify_single_finding(
            _finding("scripts/x.py", 1, "top imports mid", category="contract"), str(repo))
        assert action == "unverified"
        assert res["unverified_reason"] == "tier12_structural_disproof"

    def test_T3_25_none_falls_back_to_generic(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, _FILES_VIOLATION)  # 无 guards ⇒ 无裁决
        monkeypatch.chdir(repo)
        _write(repo, "scripts/x.py", "import top\n")
        res, action = VF.verify_single_finding(
            _finding("scripts/x.py", 1, "layer violation between low and top"), str(repo))
        checks = res["l4"]["checks"]
        # AC-4: 无裁决 ⇒ 不落 contract check，回落 generic（后续 action 由既有路径决定）
        assert "contract" not in checks and "generic" in checks
        assert action in ("verified", "partial", "unverified")

    def test_T3_26_guards_missing_none_not_false(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION)
        assert CG.verify_contract(str(repo), "low imports top") is None

    def test_T3_27_yaml_invalid_no_raise(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, guards="{not: yaml: at: all")
        assert CG.verify_contract(str(repo), "low imports top") is None

    def test_T3_28_dynamic_import_none(self, tmp_path):
        # 静态图**无** low->top 边（只有动态导入）⇒ 本应 False；
        # 但 src 含动态 import ⇒ 图可能不完整 ⇒ 必须判 None，不得判 False
        files = {
            "src/top.py": "import mid\n",
            "src/mid.py": "import low\n",
            "src/low.py": "__import__('top')\n",
            "src/solo.py": "# none\n",
        }
        repo = _make_repo(tmp_path, files, _guards_yaml(_LAYERS))
        assert CG.verify_contract(str(repo), "low imports top") is None
        # 反向对照: 无动态导入的同形仓库 ⇒ False
        repo2 = _make_repo(tmp_path / "b", _FILES_CLEAN, _guards_yaml(_LAYERS))
        assert CG.verify_contract(str(repo2), "low imports top") is not None

    def test_T3_29_non_python_none(self, tmp_path):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        assert CG.verify_contract(str(repo), "low imports top", language="java") is None

    def test_T3_30_real_repo_contract_correct(self):
        """真实用例: ADD 自身 scripts/ 的 F-2 实边 + docs/audit/guards.yml。"""
        decls = CG.load_contract_declarations(str(_REPO_ROOT))
        if not decls:
            pytest.skip("docs/audit/guards.yml 尚未就绪（Step 9 P6 产出）")
        # 允许方向（高→低）⇒ 断言不成立 ⇒ False
        r = CG.verify_contract(str(_REPO_ROOT), "verify_findings imports _script_utils")
        assert r is not None and r["verified"] is False
        r2 = CG.verify_contract(str(_REPO_ROOT), "ast_cfg imports _script_utils")
        assert r2 is not None and r2["verified"] is False
        # 反向但无路径 ⇒ False（不得出现假 True）
        r3 = CG.verify_contract(str(_REPO_ROOT), "ast_cfg imports verify_findings")
        assert r3 is not None and r3["verified"] is False

    def test_T3_31_existing_guards_schema_compat(self, tmp_path):
        # 无 contract 字段的 guards ⇒ 声明为空 ⇒ None（等价现状）
        legacy = ("version: \"1.0\"\nguards:\n"
                  "  - id: \"G001\"\n"
                  "    description: \"d\"\n"
                  "    scope: \"src/**/*.py\"\n"
                  "    severity: \"critical\"\n"
                  "    check: \"free text\"\n")
        repo = _make_repo(tmp_path, _FILES_VIOLATION, legacy)
        assert CG.load_contract_declarations(str(repo)) is None
        assert CG.verify_contract(str(repo), "low imports top") is None


# ── T4 兼容与 kill switch (6) ────────────────────────────────────────────


class TestT4Compatibility:
    def test_T4_32_disabled_no_contract_keys(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        monkeypatch.chdir(repo)
        _write(repo, "scripts/x.py", "import top\n")
        f = _finding("scripts/x.py", 1, "layer violation between low and top")
        on, _ = VF.verify_single_finding(f, str(repo))
        assert "contract_verified" in on and "contract_kind" in on and "contract_rule_id" in on
        os.environ["ADD_CONTRACT_DISABLE"] = "1"
        off, _ = VF.verify_single_finding(f, str(repo))
        for k in ("contract_verified", "contract_kind", "contract_rule_id"):
            assert k not in off

    def test_T4_33_disabled_classify_bitwise_equal(self):
        samples = ["missing null check in foo", "circular dependency between a and b",
                   "dead code after return", "wrong return type in bar",
                   "unrelated widget note", "ambiguous generic statement"]
        enabled = [VF.classify_claim(s) for s in samples]
        os.environ["ADD_CONTRACT_DISABLE"] = "1"
        disabled = [VF.classify_claim(s) for s in samples]
        assert enabled == disabled  # 非 contract 语料在两态下逐位相等

    def test_T4_34_verification_level_within_1_4(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, _FILES_VIOLATION, _guards_yaml(_LAYERS))
        monkeypatch.chdir(repo)
        _write(repo, "scripts/x.py", "import top\n")
        levels = set()
        for claim in ("low imports top", "top imports mid", "missing null check"):
            res, _ = VF.verify_single_finding(_finding("scripts/x.py", 1, claim), str(repo))
            levels.add(res["verification_level"])
        assert levels <= {1, 2, 3, 4} and 5 not in levels

    def test_T4_35_corpus_contract_hits_zero(self):
        """882 条真实语料上 contract 命中面 = 0（支撑 AC-22 休眠披露 + 正则收紧 X-2）。"""
        root = _REPO_ROOT / "docs" / "benchmark"
        if not root.is_dir():
            pytest.skip("benchmark 语料不在本机")
        hits = 0
        total = 0
        for p in sorted(root.rglob("findings*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            items = data if isinstance(data, list) else data.get("findings", [])
            if not isinstance(items, list):
                continue
            for f in items:
                if not isinstance(f, dict):
                    continue
                total += 1
                if "contract_related" in VF.classify_claim(
                        f.get("claim") or "", f.get("evidence"), f.get("category")):
                    hits += 1
        assert total == 882, "语料规模应为 882 条（若语料变更需同步基准）"
        assert hits == 0, "收紧后的正则在真实语料上不应命中（F-4 噪声已消除）"

    def test_T4_36_contract_enabled_call_sites(self):
        src = (_HERE / "verify_findings.py").read_text(encoding="utf-8")
        assert src.count("_contract_enabled()") >= 2

    def test_T4_37_merge_guards_preserves_contract(self):
        pytest.importorskip("yaml")
        sys.path.insert(0, str(_HERE))
        import merge_guards as MG
        common = {"version": "1.0", "guards": []}
        project = {"version": "1.0", "guards": [
            {"id": "G101", "description": "d", "scope": "src/**/*.py",
             "severity": "critical", "check": "t",
             "contract": {"root": "src", "kind": "layers",
                          "layers": ["a", "b"], "allow": []}}]}
        merged = MG.merge_guards(common, project)
        entry = [g for g in merged["guards"] if g["id"] == "G101"][0]
        assert entry["contract"]["layers"] == ["a", "b"]
