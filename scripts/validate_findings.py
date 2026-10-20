#!/usr/bin/env python3
"""v3.0 T20: Findings schema 校验器（纯 stdlib，零新增依赖）。

解释 JSON Schema draft-07 的受限子集；遇到不支持的关键字必须报错（退出码 2），
不得静默忽略 —— 否则 schema 会退化为装饰品。

用法:
    python scripts/validate_findings.py --findings <path> [<path> ...] \
        [--schema sast|audit|<path>] [--json] [--quiet]

退出码:
    0 = 全部通过 · 1 = 存在违规 · 2 = 用法/schema 加载/不支持的关键字
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SUPPORTED_KEYWORDS = frozenset({
    "$schema", "$id", "title", "description",
    "type", "required", "enum", "pattern", "format",
    "minimum", "maximum", "minLength", "maxLength",
    "minItems", "maxItems", "items",
    "properties", "additionalProperties", "definitions", "$ref",
})
SUPPORTED_FORMATS = frozenset({"date"})

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_SCHEMA_SHORTCUTS = {
    "sast": _SCHEMA_DIR / "sast-finding.schema.json",
    "audit": _SCHEMA_DIR / "audit-finding.schema.json",
}

_MAX_REF_DEPTH = 100
_PATTERN_CACHE = {}


class SchemaError(Exception):
    """schema 加载 / 解释失败（对应退出码 2）。"""


# ── schema 加载与关键字检查 ─────────────────────────────────────────────


def load_schema(path):
    """读取 schema JSON；非 dict 或解析失败 ⇒ SchemaError。"""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SchemaError("cannot read schema %s: %s" % (path, exc))
    except json.JSONDecodeError as exc:
        raise SchemaError("invalid schema JSON %s: %s" % (path, exc))
    if not isinstance(data, dict):
        raise SchemaError("schema root must be a JSON object: %s" % path)
    check_keywords(data)
    return data


def check_keywords(schema, _path="$"):
    """递归扫描不支持的关键字 ⇒ SchemaError（不静默忽略）。"""
    if isinstance(schema, list):
        for i, item in enumerate(schema):
            check_keywords(item, "%s[%d]" % (_path, i))
        return
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key in ("properties", "definitions"):
            if not isinstance(value, dict):
                raise SchemaError("%s.%s must be an object" % (_path, key))
            for name, sub in value.items():
                check_keywords(sub, "%s.%s.%s" % (_path, key, name))
            continue
        if key not in SUPPORTED_KEYWORDS:
            raise SchemaError("unsupported keyword '%s' at %s" % (key, _path))
        if key == "format" and value not in SUPPORTED_FORMATS:
            raise SchemaError("unsupported format '%s' at %s" % (value, _path))
        if key in ("items", "additionalProperties") and isinstance(value, (dict, list)):
            check_keywords(value, "%s.%s" % (_path, key))


def resolve_ref(root, ref):
    """仅支持 `#` 与 `#/definitions/<name>`；其余 ⇒ SchemaError。"""
    if ref == "#":
        return root
    prefix = "#/definitions/"
    if isinstance(ref, str) and ref.startswith(prefix):
        name = ref[len(prefix):]
        definitions = root.get("definitions", {}) if isinstance(root, dict) else {}
        if name in definitions:
            return definitions[name]
    raise SchemaError("unsupported or broken $ref: %s" % ref)


# ── 校验语义（draft-07 受限子集）───────────────────────────────────────


def _type_name(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(value, expected):
    """bool 不算 integer / number（Python 陷阱，必须显式排除）。"""
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise SchemaError("unsupported type '%s'" % expected)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def validate(value, schema, root=None, path="$"):
    """递归校验，返回错误消息列表（空 = 通过）。"""
    if not isinstance(schema, dict):
        raise SchemaError("schema at %s must be an object" % path)
    if root is None:
        root = schema

    if "$ref" in schema:
        return validate(value, resolve_ref(root, schema["$ref"]), root, path)

    errors = []

    expected_type = schema.get("type")
    if expected_type is not None and not _type_ok(value, expected_type):
        return ["%s: expected %s, got %s" % (path, expected_type, _type_name(value))]

    if "enum" in schema and value not in schema["enum"]:
        errors.append("%s: value %r not in enum %r" % (path, value, schema["enum"]))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing required property '%s'" % (path, key))
        properties = schema.get("properties", {})
        for key, sub in properties.items():
            if key in value:
                errors.extend(validate(value[key], sub, root, "%s.%s" % (path, key)))
        extra = schema.get("additionalProperties", True)
        if extra is False:
            for key in value:
                if key not in properties:
                    errors.append("%s: unexpected property '%s'" % (path, key))
        elif isinstance(extra, dict):
            for key in value:
                if key not in properties:
                    errors.extend(validate(value[key], extra, root, "%s.%s" % (path, key)))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: expected at least %d items, got %d"
                          % (path, schema["minItems"], len(value)))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: expected at most %d items, got %d"
                          % (path, schema["maxItems"], len(value)))
        if isinstance(schema.get("items"), dict):
            for i, item in enumerate(value):
                errors.extend(validate(item, schema["items"], root, "%s[%d]" % (path, i)))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: length %d < minLength %d"
                          % (path, len(value), schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: length %d > maxLength %d"
                          % (path, len(value), schema["maxLength"]))
        if "pattern" in schema:
            regex = _PATTERN_CACHE.get(schema["pattern"])
            if regex is None:
                regex = re.compile(schema["pattern"])
                _PATTERN_CACHE[schema["pattern"]] = regex
            if not regex.search(value):
                errors.append("%s: value %r does not match pattern %r"
                              % (path, value, schema["pattern"]))
        if "format" in schema:
            fmt = schema["format"]
            if fmt == "date" and not _valid_date(value):
                errors.append("%s: value %r is not a valid date (YYYY-MM-DD)" % (path, value))
            elif fmt not in SUPPORTED_FORMATS:
                raise SchemaError("unsupported format '%s'" % fmt)

    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: value %r < minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: value %r > maximum %r" % (path, value, schema["maximum"]))

    return errors


# ── findings 文件解析与批量校验 ─────────────────────────────────────────


def _extract_findings(data):
    """三种形态：list / {"findings": [...]} / AuditReport（展平 module arrays）。

    Returns:
        list[tuple[dict, str]]: (finding, 来源标签)
    """
    if isinstance(data, list):
        return [(item, "") for item in data]
    if isinstance(data, dict):
        if isinstance(data.get("findings"), list):
            return [(item, "") for item in data["findings"]]
        extracted = []
        found_container = False
        for key in ("module_results", "cross_module_results"):
            modules = data.get(key)
            if not isinstance(modules, list):
                continue
            found_container = True
            for i, module in enumerate(modules):
                if not isinstance(module, dict):
                    continue
                for finding in module.get("findings", []) or []:
                    extracted.append((finding, "#%s[%d]" % (key, i)))
        if found_container:
            return extracted
    raise SchemaError(
        "unsupported findings container: expected list, "
        "{'findings': [...]}, or AuditReport")


def validate_file(findings_path, schema):
    """逐条校验 findings 文件，返回错误消息列表（空 = 通过）。"""
    try:
        data = json.loads(Path(findings_path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise SchemaError("cannot read findings %s: %s" % (findings_path, exc))
    except json.JSONDecodeError as exc:
        raise SchemaError("invalid findings JSON %s: %s" % (findings_path, exc))

    errors = []
    for index, (finding, label) in enumerate(_extract_findings(data)):
        source = "%s%s" % (findings_path, label)
        if not isinstance(finding, dict):
            errors.append("%s:%d: finding must be an object, got %s"
                          % (source, index, _type_name(finding)))
            continue
        fid = finding.get("id", "<no-id>")
        for message in validate(finding, schema):
            errors.append("%s:%d %s %s" % (source, index, fid, message))
    return errors


def _resolve_schema_path(value):
    shortcut = _SCHEMA_SHORTCUTS.get(value)
    return shortcut if shortcut is not None else Path(value)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate ADD findings against a JSON Schema (draft-07 subset)")
    parser.add_argument("--findings", nargs="+", required=True,
                        help="One or more findings JSON files")
    parser.add_argument("--schema", default="sast",
                        help="'sast' | 'audit' | path to schema JSON")
    parser.add_argument("--json", action="store_true",
                        help="Emit structured JSON report")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-error lines (summary only)")
    args = parser.parse_args(argv)

    try:
        schema = load_schema(_resolve_schema_path(args.schema))
        report = []
        total_errors = 0
        for path in args.findings:
            errors = validate_file(path, schema)
            total_errors += len(errors)
            report.append({
                "file": path,
                "findings": len(_extract_findings(
                    json.loads(Path(path).read_text(encoding="utf-8")))),
                "errors": errors,
            })
    except SchemaError as exc:
        print("schema error: %s" % exc, file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"schema": str(_resolve_schema_path(args.schema)),
                          "total_errors": total_errors,
                          "files": report}, indent=2, ensure_ascii=False))
    else:
        if not args.quiet:
            for item in report:
                for message in item["errors"]:
                    print(message)
        checked = sum(item["findings"] for item in report)
        print("checked %d finding(s) in %d file(s): %d error(s)"
              % (checked, len(report), total_errors))

    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
