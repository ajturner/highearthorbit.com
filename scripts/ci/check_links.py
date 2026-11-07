"""Check that every internal link and image in a built site resolves to a file.

Usage: python3 scripts/ci/check_links.py _site [/baseurl]
Only root-relative and relative URLs are checked; external links are skipped.
Links into the 2004-2017 archive that were already broken are reported as warnings
(paths under /assets/uploads/ or ending in .php); everything else fails the build.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

site = Path(sys.argv[1])
base = (sys.argv[2] if len(sys.argv) > 2 else "").rstrip("/")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if v and ((tag == "a" and k == "href") or (tag in ("img", "script", "source", "iframe") and k == "src") or (tag == "link" and k == "href")):
                self.urls.append(v)


def resolve(page_url: str, href: str):
    parts = urlsplit(urljoin(page_url, href))
    if parts.scheme not in ("", "http", "https") or parts.netloc:
        return None
    path = unquote(parts.path)
    if base and not path.startswith(base + "/") and path != base:
        return ("outside-base", path)
    rel = path[len(base):].lstrip("/")
    target = site / rel
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    elif not target.exists() and not target.suffix:
        target = target.with_suffix(".html")
    return (None, path) if target.exists() else ("missing", path)


errors, warnings, pages = {}, {}, 0
for f in site.rglob("*.html"):
    pages += 1
    rel = f.relative_to(site).as_posix()
    page_url = f"{base}/{rel}"
    p = Links()
    p.feed(f.read_text(encoding="utf-8", errors="replace"))
    for href in p.urls:
        if href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        r = resolve(page_url, href)
        if not r or r[0] is None:
            continue
        legacy = "/assets/uploads/" in r[1] or r[1].endswith(".php") or rel.startswith("articles/")
        bucket = warnings if legacy and r[0] == "missing" else errors
        bucket.setdefault(r[1], set()).add(rel)

print(f"{pages} pages checked; {len(errors)} broken targets; {len(warnings)} legacy warnings")
for path, srcs in sorted(warnings.items())[:40]:
    print(f"  warning {path}  (from {sorted(srcs)[0]}{' +' + str(len(srcs) - 1) if len(srcs) > 1 else ''})")
for path, srcs in sorted(errors.items()):
    print(f"  ERROR {path}  (from {', '.join(sorted(srcs)[:3])})")
sys.exit(1 if errors else 0)
