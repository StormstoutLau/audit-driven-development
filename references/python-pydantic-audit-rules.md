# ADD Reference: Python/Pydantic Audit Rules

> **Borrowed pattern**: `security-best-practices` skill's `references/` directory (language-specific rule files)
> **Source**: MCP search of FastAPI PR #13442 + Pydantic docs + FastAPI docs
> **Purpose**: Fill domain-specific knowledge gaps that generic subagent prompts cannot cover
> **KB-5 resolved**: AfterValidator annotation propagation through FastAPI dependency analysis

---

## Rule 1: Annotated Metadata Propagation (KB-5 root cause)

### Description

FastAPI's dependency analysis pipeline (`dependencies/utils.py`) must correctly propagate
all metadata from `Annotated[type, *metadata]` annotations. Pydantic's functional validators
(`AfterValidator`, `BeforeValidator`, `PlainValidator`, `WrapValidator`) are passed as
metadata items inside the `Annotated` type and must survive the `analyze_param()` →
`get_typed_signature()` → `get_dependant()` chain.

### Detection Pattern

```python
# CORRECT: Annotated with AfterValidator — the metadata should be preserved
from typing import Annotated
from pydantic import AfterValidator

@app.get("/items/")
async def read_items(
    q: Annotated[str, AfterValidator(lambda v: v.strip())] = "default"
):
    ...

# BUG PATTERN: analyze_param() in fastapi/dependencies/utils.py strips
# Annotated metadata before passing to Pydantic's FieldInfo
# Look for calls to get_origin() or get_args() on Annotated types
# that discard the __metadata__ tuple
```

### Audit Checks

1. **Check `dependencies/utils.py:analyze_param()`**: Does it correctly handle
   `typing.Annotated[base_type, *metadata]`? Does it pass `__metadata__` through?

2. **Check `_compat.py:get_annotations()` or similar**: Any code that resolves
   forward references or strips annotations — does it preserve non-FastAPI
   metadata items (AfterValidator, BeforeValidator)?

3. **Check `_compat.py:ModelField` create path**: Pydantic V2 uses
   `pydantic.FieldInfo.from_annotated_attribute()`. FastAPI's compat
   layer must not interfere with this.

4. **Grep for `__metadata__`**: The `typing.Annotated.__metadata__` attribute
   contains the extra metadata. Any code manipulating Annotated types must
   preserve this attribute.

### Known Bug: FastAPI 0.115.8 → 0.115.11

- **Bug**: PR #13314 (Pydantic 2.11 compat) changed `_compat.py` annotation
  handling, which broke `AfterValidator` propagation → #13440
- **Fix**: PR #13442 reverted the problematic change and added docs + tests
- **Root cause**: The annotation compatibility change for Pydantic 2.11's
  internal API surface (`_internal._typing_extra`) inadvertently stripped
  non-FastAPI metadata from `Annotated` types
- **Why tests didn't catch it**: No existing tests used AfterValidator with
  query parameters — the feature existed but was untested
- **Detection window**: v0.115.8 through v0.115.10 (3 patch versions, ~2 months)

### ADD Subagent Prompt Extension

```
DIMENSION 1 extension for Pydantic/FastAPI projects:
- Check all `Annotated[type, *metadata]` processing in dependency analysis code
- For each Annotated type: verify __metadata__ tuple is preserved through
  analyze_param → get_typed_signature → get_dependant chain
- Specific check: does code call typing.get_args(annotated_type) and discard
  args[1:] (the metadata portion)?
- Check: does _compat.py's FieldInfo creation path correctly pass Pydantic
  metadata (AfterValidator, BeforeValidator, etc.) to the Pydantic engine?
```

---

## Rule 2: Pydantic V1/V2 Compat Layer Stability

### Description

FastAPI maintains Pydantic V1 backward compatibility through `_compat.py`.
This creates two independent code paths for annotation handling, field
creation, and schema generation. Any change to one path without
corresponding changes to the other creates a compatibility gap.

### Audit Checks

1. **Grep for `if PYDANTIC_V2` / `else:` blocks** in `_compat.py`:
   Each conditional branch must have equivalent behavior for annotation
   handling, field creation, and model validation.

2. **V1 path at `_compat.py:L290-L393`**: The `get_model_definitions()`
   function (V1-only) has custom `\f` truncation logic. V2 path
   uses `schema_generator.generate_definitions()` — no truncation.
   This is a known asymmetry (KB-2 related).

3. **`pydantic._internal` imports**: Any code importing from `pydantic._internal`
   is accessing private API surface. These APIs can change between Pydantic
   minor versions (e.g., 2.10 → 2.11) without deprecation warning.
   - `pydantic._internal._typing_extra` — used in `_compat.py`
   - `pydantic._internal._config` — used in `_compat.py`
   - These are DRAGONS — flag any usage in audit

### ADD Subagent Prompt Extension

```
DIMENSION 6 extension for Pydantic-compatible projects:
- Check if the project uses pydantic._internal imports
- For each _internal import: this is a forward-compat risk
- Check if there are version-specific code paths that handle Pydantic
  minor version differences (e.g., 2.10 vs 2.11 behavior changes)
- The project's pyproject.toml should declare a specific Pydantic version
  range, not just >=2.0.0 — internal API surface changes between minors
```

---

## Rule 3: Annotated Type Metadata Extraction Pattern

### The Canonical Pattern (correct)

```python
import typing

def get_field_info(annotation: type) -> FieldInfo:
    """Extract FieldInfo from Annotated metadata — CORRECT pattern."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is typing.Annotated:
        base_type = args[0]
        metadata = args[1:]  # ← PRESERVE ALL METADATA

        # FastAPI-specific: extract Query/Path/Body/Header/Depends
        fastapi_metadata = [m for m in metadata
                           if isinstance(m, (Query, Path, Body, Header, Depends))]

        # Pydantic-specific: pass remaining metadata through
        pydantic_metadata = [m for m in metadata
                            if not isinstance(m, (Query, Path, Body, Header, Depends))]
        # ↑ AfterValidator, BeforeValidator, etc. go HERE

        return FieldInfo.from_annotated(base_type, pydantic_metadata)
    ...
```

### The Bug Pattern (what to detect)

```python
# BUG: discards metadata beyond the first FastAPI-specific item
fastapi_metadata = metadata[0] if metadata else None
# ↑ AfterValidator at metadata[1] is LOST
```

```python
# BUG: only keeps FastAPI field info, drops everything else
if any(isinstance(m, FieldInfo) for m in metadata):
    field_info = next(m for m in metadata if isinstance(m, FieldInfo))
    return field_info  # AfterValidator metadata is LOST
```

### Detection Commands

```bash
# Find Annotated metadata extraction in dependencies/utils.py
grep -n "get_origin\|get_args\|__metadata__\|Annotated" dependencies/utils.py

# Find all places where Annotated args are sliced
grep -n "args\[" dependencies/utils.py

# Find _compat.py annotation handling
grep -n "get_origin\|get_args\|__metadata__\|Annotated" _compat.py
```

---

## Sources / 信息源

| Source | Type | URL |
|---|---|---|
| FastAPI PR #13442 (fix) | GitHub | https://github.com/fastapi/fastapi/pull/13442 |
| Pydantic AfterValidator docs | Doc | https://docs.pydantic.dev/latest/api/functional_validators/ |
| FastAPI Custom Validation docs | Doc | https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#custom-validation |
| FastAPI 0.115.11 release notes | GitHub | https://github.com/fastapi/fastapi/releases/tag/0.115.11 |

## Integration with ADD

This reference file is loaded when:
1. The audit target has `pydantic` or `fastapi` as a dependency
2. `--lens pydantic` is enabled (future extension lens)
3. The project uses `Annotated` types in function signatures

Format follows `security-best-practices` skill's `references/` convention:
one language-specific file with rules → audit checklist → detection patterns.
