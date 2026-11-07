import json
import subprocess
from pathlib import Path

from scripts.heo import only_synced
from scripts.heo.content import Item, dump, parse
from scripts.heo.publish import payload
from scripts.heo.sync_flickr import select_albums
from scripts.heo.validate import validate


def test_repository_content_is_valid():
    assert validate() == []


def test_round_trip_keeps_fields_and_body():
    text = "---\nsource_id: talk:x\ntitle: A talk\ndate: '2024-01-02'\nevent: Conf\n---\n\nAbstract here.\n"
    item = parse(text, Path("content/_talks/x.md"))
    assert item.meta["event"] == "Conf"
    assert parse(dump(item), item.path).meta == item.meta
    assert parse(dump(item), item.path).body == "Abstract here."


def test_hash_ignores_nothing_published():
    a = parse("---\nsource_id: project:a\ntitle: A\nera: civic\n---\n", Path("content/_projects/a.md"))
    b = parse("---\nsource_id: project:a\ntitle: A\nera: civic\nsummary: new\n---\n", Path("content/_projects/a.md"))
    assert a.content_hash() != b.content_hash()


def _album(aid, title):
    return {"id": aid, "title": {"_content": title}}


def test_flickr_selection_rule():
    albums = [
        _album("1", "2024-10-13 Acadia"),
        _album("2", "2026-06-30 Goshen Scout Camp"),
        _album("3", "New Zealand"),
        _album("4", "2024"),
        _album("5", "Christmas 2012"),
    ]
    chosen = select_albums(albums, exclude={"2": ""}, include={"3": ""})
    assert [a["id"] for a in chosen] == ["1", "3"]


def test_payload_maps_type_fields_and_hidden():
    item = Item(
        path=Path("content/_photos/acadia-2024.md"),
        meta={"source_id": "flickr:1", "title": "Acadia", "flickr_id": "1", "hidden": True,
              "synced": {"cover_url": "https://example.com/c.jpg", "count": 3}},
    )
    body = payload(item, "draft")
    assert body["type"] == "photo_album"
    assert body["hidden"] is True
    assert body["meta"]["flickr_id"] == "1"
    assert json.loads(body["meta"]["synced"])["count"] == 3
    assert body["featured_image_url"] == "https://example.com/c.jpg"


def test_markdown_body_is_rendered_and_html_body_is_kept():
    md = Item(path=Path("content/_posts/a.md"), meta={"source_id": "a:1", "title": "A", "date": "2024-01-01"}, body="Some *text*")
    html = Item(path=Path("content/_posts/b.md"), meta={"source_id": "b:1", "title": "B", "date": "2024-01-01", "format": "html"}, body="<!-- wp:paragraph --><p>x</p>")
    assert "<em>text</em>" in payload(md, "draft")["content"]
    assert payload(html, "draft")["content"] == "<!-- wp:paragraph --><p>x</p>"


def test_only_synced_detects_curated_changes(tmp_path, monkeypatch):
    def run(*args):
        subprocess.run(args, cwd=tmp_path, check=True, capture_output=True)

    f = tmp_path / "content" / "_projects" / "a.md"
    f.parent.mkdir(parents=True)
    f.write_text("---\nsource_id: project:a\ntitle: A\nera: civic\nsynced:\n  stars: 1\n---\n")
    run("git", "init", "-q", "-b", "main")
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "init", "--allow-empty")
    run("git", "add", ".")
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    run("git", "checkout", "-qb", "sync")
    monkeypatch.chdir(tmp_path)

    f.write_text("---\nsource_id: project:a\ntitle: A\nera: civic\nsynced:\n  stars: 2\n---\n")
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "stars")
    assert only_synced.main(["main", "sync"]) == 0

    f.write_text("---\nsource_id: project:a\ntitle: A renamed\nera: civic\nsynced:\n  stars: 2\n---\n")
    run("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qam", "title")
    assert only_synced.main(["main", "sync"]) == 1


def test_import_cleans_wordpress_slugs():
    from scripts.heo.import_wordpress import clean_slug, norm_title
    assert clean_slug("professional-civic-engineering%ef%bf%bc") == "professional-civic-engineering"
    assert clean_slug("2012") == "2012"
    assert norm_title("CrisisCommons &amp; Congress") == norm_title("crisiscommons & congress")


def _page(tags, status):
    return {"properties": {
        "Tags": {"type": "multi_select", "multi_select": [{"name": t} for t in tags]},
        "Status": {"type": "status", "status": {"name": status} if status else None},
    }}


def test_notion_selection_needs_blog_and_published():
    from scripts.heo.sync_notion import is_published
    assert is_published(_page(["Blog"], "Published"))
    assert is_published(_page(["blog", "published"], "Draft"))
    assert not is_published(_page(["Blog"], "Draft"))
    assert not is_published(_page(["Journal"], "Published"))


def test_notion_blocks_to_markdown():
    from scripts.heo.sync_notion import Converter

    def rt(text, **ann):
        return [{"type": "text", "plain_text": text, "annotations": ann, "href": ann.pop("href", None)}]

    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": rt("Intro")}},
        {"type": "paragraph", "paragraph": {"rich_text": rt("Hello ") + rt("world", bold=True)}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("one")},
         "children": [{"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("nested")}}]},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("two")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("first")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("second")}},
        {"type": "code", "code": {"language": "python", "rich_text": rt("print(1)")}},
        {"id": "abc-1", "type": "image", "image": {"type": "file", "file": {"url": "https://s3/x.png"}, "caption": []}},
        {"type": "child_page", "child_page": {"title": "skip me"}},
    ]
    md = Converter(lambda url, bid: f"/assets/notion/{bid}.png").convert(blocks)
    assert md == (
        "## Intro\n\n"
        "Hello **world**\n\n"
        "- one\n\n    - nested\n- two\n\n"
        "1. first\n2. second\n\n"
        "```python\nprint(1)\n```\n\n"
        "![](/assets/notion/abc-1.png)"
    )


def test_portfolio_rule_applies_to_own_repositories_only():
    from scripts.heo.content import portfolio_excluded
    assert portfolio_excluded({"github": "ajturner/geopress", "synced": {"topics": ["wordpress"]}})
    assert not portfolio_excluded({"github": "ajturner/geopress", "synced": {"topics": ["Portfolio"]}})
    assert not portfolio_excluded({"github": "koopjs/koop", "synced": {"topics": []}})
    assert not portfolio_excluded({"title": "No repo"})
