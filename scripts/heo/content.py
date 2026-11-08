"""Read and write content files: Markdown with YAML front matter.

Each file under content/_<folder>/ describes one item. The front matter holds
metadata; the body holds the item's text (an article, a talk abstract, a
project description). Fields under the `synced` key belong to sync jobs and
are rewritten on every run; every other field is curated by hand and is never
touched by a sync job.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
SCHEMAS = ROOT / "schemas"

# folder name -> (WordPress post type, schema file stem)
# Folders are Jekyll collections (collections_dir: content), hence the underscores.
TYPES: dict[str, tuple[str, str]] = {
    "_posts": ("post", "article"),
    "_external": ("external_article", "external_article"),
    "_talks": ("talk", "talk"),
    "_projects": ("project", "project"),
    "_photos": ("photo_album", "photo_album"),
}
DATA = ROOT / "_data"
SUFFIXES = (".md", ".html")

FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n?(.*)\Z", re.S)


class _Dumper(yaml.SafeDumper):
    """Keep key order and write multi-line strings as blocks."""


def _str_presenter(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_presenter)


@dataclass
class Item:
    path: Path
    meta: dict[str, Any]
    body: str = ""
    folder: str = field(init=False)

    def __post_init__(self) -> None:
        self.folder = self.path.parent.name

    @property
    def post_type(self) -> str:
        return TYPES[self.folder][0]

    @property
    def schema_name(self) -> str:
        return TYPES[self.folder][1]

    @property
    def source_id(self) -> str:
        return self.meta["source_id"]

    def content_hash(self) -> str:
        """Stable hash of everything that is published, used to skip unchanged items."""
        payload = json.dumps({"meta": self.meta, "body": self.body}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def parse(text: str, path: Path) -> Item:
    m = FRONT_MATTER.match(text)
    if not m:
        raise ValueError(f"{path}: missing '---' front matter block")
    meta = yaml.safe_load(m.group(1)) or {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: front matter must be a mapping")
    return Item(path=path, meta=meta, body=m.group(2).strip("\n"))


def load(path: Path) -> Item:
    return parse(path.read_text(encoding="utf-8"), path)


def dump(item: Item) -> str:
    fm = yaml.dump(item.meta, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)
    body = item.body.strip("\n")
    return f"---\n{fm}---\n" + (f"\n{body}\n" if body else "")


def save(item: Item) -> bool:
    """Write the item; return True if the file changed."""
    new = dump(item)
    old = item.path.read_text(encoding="utf-8") if item.path.exists() else None
    if new == old:
        return False
    item.path.parent.mkdir(parents=True, exist_ok=True)
    item.path.write_text(new, encoding="utf-8")
    return True


def iter_items(folders: list[str] | None = None):
    for folder in folders or list(TYPES):
        for path in sorted((CONTENT / folder).iterdir()) if (CONTENT / folder).is_dir() else []:
            if path.suffix in SUFFIXES and not path.name.startswith("."):
                yield load(path)


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "item"


def merge_synced(item: Item, synced: dict[str, Any]) -> None:
    """Replace only the `synced` block; curated fields stay as they are."""
    item.meta["synced"] = synced
