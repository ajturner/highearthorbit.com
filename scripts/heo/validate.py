"""Validate every content file against its JSON Schema and check cross-file rules.

Usage: python -m scripts.heo.validate
Exits non-zero on any error, so CI blocks the merge.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import yaml
from jsonschema import Draft202012Validator

from .content import CONTENT, DATA, SCHEMAS, TYPES, iter_items


def _json_safe(meta):
    """YAML turns unquoted dates into date objects; schemas expect strings."""
    return json.loads(json.dumps(meta, default=str))


def validate() -> list[str]:
    errors: list[str] = []
    validators = {
        stem: Draft202012Validator(json.loads((SCHEMAS / f"{stem}.schema.json").read_text()))
        for _, stem in TYPES.values()
    }
    seen: dict[str, list[str]] = defaultdict(list)
    slugs: dict[tuple[str, str], list[str]] = defaultdict(list)

    for item in iter_items():
        rel = item.path.relative_to(CONTENT.parent)
        try:
            meta = _json_safe(item.meta)
        except Exception as exc:  # pragma: no cover - defensive
            errors.append(f"{rel}: {exc}")
            continue
        for err in validators[item.schema_name].iter_errors(meta):
            where = "/".join(str(p) for p in err.absolute_path) or "(root)"
            errors.append(f"{rel}: {where}: {err.message}")
        if "source_id" in meta:
            seen[meta["source_id"]].append(str(rel))
        if meta.get("slug"):
            slugs[(item.post_type, meta["slug"])].append(str(rel))

    for sid, paths in seen.items():
        if len(paths) > 1:
            errors.append(f"duplicate source_id '{sid}' in: {', '.join(paths)}")
    for (ptype, slug), paths in slugs.items():
        if len(paths) > 1:
            errors.append(f"duplicate {ptype} slug '{slug}' in: {', '.join(paths)}")

    for name in ("flickr_exclude.yml", "flickr_include.yml"):
        p = DATA / name
        if p.exists():
            data = yaml.safe_load(p.read_text()) or {}
            for entry in data.get("albums", []):
                if not str(entry.get("id", "")).isdigit():
                    errors.append(f"_data/{name}: album entry without numeric id: {entry}")
    return errors


def main() -> int:
    errors = validate()
    count = sum(1 for _ in iter_items())
    if errors:
        print(f"{len(errors)} problem(s) in {count} files:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"OK: {count} content files valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
