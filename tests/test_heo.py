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


FEED = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015"
 xmlns:media="http://search.yahoo.com/mrss/"><title>Andrew Turner Talks</title>
<entry><yt:videoId>zYSEOML_0Xo</yt:videoId><title>GeoAI and the Future of Mapping: Implications for 21st-Century Digital Resilience</title>
<author><name>National Academies</name></author><published>2023-05-22T18:00:00+00:00</published>
<media:group><media:thumbnail url="https://i.ytimg.com/vi/zYSEOML_0Xo/hqdefault.jpg"/><media:description>Workshop talk.</media:description></media:group></entry>
</feed>"""


def _talk(stem, **meta):
    return Item(path=Path(f"content/_talks/{stem}.md"), meta={"source_id": f"talk:{stem}", "date": "2020-01-01", "event": "X", **meta})


def test_youtube_feed_and_page_parsing():
    from scripts.heo.sync_youtube import parse_feed, playlist_page_ids

    (v,) = parse_feed(FEED)
    assert v["id"] == "zYSEOML_0Xo" and v["published_at"] == "2023-05-22" and v["channel"] == "National Academies"
    assert v["description"] == "Workshop talk." and v["thumbnail"].endswith("hqdefault.jpg")
    page = ('"url":"/watch?v=w3C1lRx0k44\\u0026list=PLX\\u0026index=1" href="/watch?v=DTU_jSWpQPE&amp;list=PLX" '
            '"/watch?v=w3C1lRx0k44&list=PLX" "/watch?v=zzzzzzzzzzz" "/watch?v=yyyyyyyyyyy&list=PLOTHER"')
    assert playlist_page_ids(page, "PLX") == ["w3C1lRx0k44", "DTU_jSWpQPE"]


def test_youtube_video_matches_talk_by_id_map_or_title():
    from scripts.heo.sync_youtube import match_talk, normalize

    by_id = _talk("a", title="Something Else", youtube_id="AAAAAAAAAAA")
    mapped = _talk("b", title="Where 2.0 That Matters")
    titled = _talk("c", title="Lessons Learned from Neogeography")
    short = _talk("d", title="Hub")
    talks = [by_id, mapped, titled, short]
    mapping = {"w3C1lRx0k44": "talk:b"}

    def video(vid, title):
        return {"id": vid, "title": title, "published_at": "", "channel": "", "description": "", "thumbnail": ""}

    assert match_talk(video("AAAAAAAAAAA", "Anything"), talks, mapping) is by_id
    assert match_talk(video("w3C1lRx0k44", 'Where 2.0 2010: Andrew Turner, "Crisis Mapping"'), talks, mapping) is mapped
    assert match_talk(video("Ci3R-Kx9ODw", "Lessons Learned from Neogeography Applied to GIS"), talks, mapping) is titled
    assert match_talk(video("BBBBBBBBBBB", "Hub"), talks, mapping) is None  # too short to trust
    assert match_talk(video("CCCCCCCCCCC", "An Unrelated Keynote"), talks, mapping) is None
    assert normalize('Where 09:  Andrew Turner, "Are Geospatial Tools..." #esri') == "where 09 are geospatial tools"


def test_youtube_map_points_at_existing_talks():
    from scripts.heo.content import iter_items
    from scripts.heo.sync_youtube import video_map

    ids = {i.meta["source_id"] for i in iter_items(["_talks"])}
    missing = {v: s for v, s in video_map().items() if s not in ids}
    assert missing == {}


def test_github_discovery_labels_and_drafts():
    from scripts.heo.sync_github import discovery

    def repo(name, **kw):
        return {"full_name": f"ajturner/{name}", "fork": False, "private": False, "topics": [], "pushed_at": "2020-01-01", "has_pages": False, **kw}

    covered = {"ajturner/plan-stuff-a-thon"}
    args = dict(covered=covered, cutoff="2026-01-01", recent=True, pages=True, topics=["portfolio"])
    assert discovery(repo("holocene", topics=["history", "portfolio"]), **args) == "labeled"
    assert discovery(repo("plan-stuff-a-thon", topics=["portfolio"]), **args) is None  # excluded wins
    assert discovery(repo("fieldkey", topics=["portfolio"], private=True), **args) is None
    assert discovery(repo("site", has_pages=True), **args) == "found"
    assert discovery(repo("fresh", pushed_at="2026-06-01"), **args) == "found"
    assert discovery(repo("old"), **args) is None
    assert discovery(repo("tagged", topics=["portfolio"]), **{**args, "topics": []}) is None
