"""Merge common + project guard files. Project guards override common guards by id.
Implements P3.3 cross-project guard reuse: Two-layer architecture.

Usage: python scripts/merge_guards.py --common <guards.common.yml> --project <guards.project.yml> [--output <merged.yml>]
"""

import sys, yaml, json
from pathlib import Path
from _script_utils import run_script

def load_guard_file(path):
    """Load a guard YAML file."""
    if not Path(path).exists():
        return {"version": "1.0", "guards": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing {path}: {e}", file=sys.stderr)
        sys.exit(2)

def merge_guards(common, project):
    """Merge common + project guards. Project overrides common by id."""
    guard_map = {g["id"]: g for g in common.get("guards", [])}
    guard_map.update({g["id"]: g for g in project.get("guards", [])})

    merged = {
        "version": project.get("version", "1.0"),
        "description": project.get("description", "Merged guards"),
        "extends": project.get("extends", ""),
        "guards": sorted(guard_map.values(), key=lambda g: g["id"])
    }
    return merged

def main():
    if len(sys.argv) < 5:
        print("Usage: python scripts/merge_guards.py --common <common.yml> --project <project.yml> [--output <merged.yml>]")
        sys.exit(1)

    common_path = None
    project_path = None
    output_path = None
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--common" and i + 1 < len(sys.argv):
            common_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--project" and i + 1 < len(sys.argv):
            project_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == "--output" and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    if not common_path or not project_path:
        print("ERROR: --common and --project are required", file=sys.stderr)
        sys.exit(1)

    common = load_guard_file(common_path)
    project = load_guard_file(project_path)
    merged = merge_guards(common, project)

    common_count = len(common.get("guards", []))
    project_count = len(project.get("guards", []))
    merged_count = len(merged["guards"])
    overrides = common_count + project_count - merged_count

    result = yaml.dump(merged, default_flow_style=False, allow_unicode=True, sort_keys=False)

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
        print(f"Merged {common_count} common + {project_count} project = {merged_count} guards ({overrides} overrides)")
    else:
        print(result)

    return 0

if __name__ == "__main__":
    run_script(main)
