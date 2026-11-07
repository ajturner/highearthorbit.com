import base64, json, os, re, requests
h = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
out, page = [], 1
while True:
    rs = requests.get("https://api.github.com/users/ajturner/repos", params={"type": "owner", "per_page": 100, "page": page}, headers=h, timeout=30).json()
    if not rs: break
    for r in rs:
        if not r.get("has_pages"): continue
        rd = requests.get(f"https://api.github.com/repos/{r['full_name']}/readme", headers=h, timeout=30)
        text = ""
        if rd.ok:
            text = base64.b64decode(rd.json()["content"]).decode("utf-8", "replace")
            text = re.sub(r"\s+", " ", re.sub(r"!\[[^\]]*\]\([^)]*\)|<[^>]+>", " ", text))[:700]
        out.append({k: r.get(k) for k in ("name", "fork", "archived", "description", "homepage", "language", "stargazers_count", "created_at", "pushed_at", "topics")} | {"readme": text})
    page += 1
os.makedirs("ci-dump", exist_ok=True)
json.dump(out, open("ci-dump/pages-repos.json", "w"), indent=1)
print(len(out), "repos with pages")
