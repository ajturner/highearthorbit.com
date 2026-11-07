# highearthorbit.com

Content and code for [highearthorbit.com](https://highearthorbit.com). Every article, talk, project and photo album is one file in `content/`. Jekyll builds them into a static site that GitHub Pages serves as the **staging site**. The same files can later be published to the WordPress site through its REST API.

```
content/
  _posts/      articles: 2004-2017 archive (HTML from the old WordPress export) and new posts
  _external/   articles published elsewhere; listed with writing, linked to their own URL
  _talks/      talks, with YouTube video and slides
  _projects/   software and civic projects, grouped by era (_data/eras.yml)
  _photos/     Flickr albums
_data/         homepage text (home.yml), project eras, Flickr and GitHub include/exclude lists, YouTube video map
_layouts/ _includes/ assets/css/   the site design (matches the WordPress theme)
_plugins/heo.rb                    draft visibility and base-path links
index.html articles/ projects/ talks/ photos/ about.md now.md   site pages
schemas/       JSON Schema for each content type's front matter
scripts/heo/   validate, sync_github, sync_youtube, sync_flickr, import_wordpress, publish, only_synced
scripts/ci/    check_links.py (built site), wp-test.sh (throwaway WordPress)
wordpress/     mu-plugin and block theme for the WordPress site
.github/workflows/
```

## How it works

| Workflow | When | What it does |
| --- | --- | --- |
| `ci.yml` | Every pull request and push to `master` | Validates content, runs tests, builds the site, checks internal links. The built site is attached to the run as the `site` artifact |
| `pages.yml` | Push to `master`, nightly, or by hand | Builds and deploys the staging site to GitHub Pages |
| `sync.yml` | Mondays, or by hand | Pulls GitHub repo stats and `portfolio` repositories, the YouTube talks playlist, dated Flickr albums and Notion blog posts into `content/`, opens one pull request. Changes only inside `synced:` blocks, and posts published from Notion, auto-merge |
| `import-wordpress.yml` | By hand | Copies WordPress posts missing from `content/_posts/` (matched by `wp_id`) into a pull request |
| `wordpress-test.yml` | Pull requests that change `wordpress/`, `scripts/` or `schemas/` | Publishes everything into a throwaway WordPress and checks every page type |
| `publish.yml`, `deploy-code.yml` | By hand only, for now | Publish content to WordPress; deploy the plugin and theme over SSH |

Rules:

- **Curated vs synced fields.** Sync jobs only rewrite the `synced:` block. Everything else in a file is yours.
- **Drafts.** `hidden: true` keeps an item off the live site. On staging (`heo.staging: true` in `_config.yml`) hidden items are shown with a Draft badge so you can review them, and every page has `noindex`. Hidden or excluded photo albums are never shown.
- **Portfolio projects.** Your own repositories appear on the Projects page only when they have the GitHub topic `portfolio` (repository page › About › gear icon › Topics). The weekly sync adds a project file for each new `portfolio` repository; removing the topic takes the project off the site but keeps its file. Projects from other owners (Koop, Cedar) are curated by hand and always shown.
- **Blog posts from Notion.** A page in the Notion Writing database becomes a post when its Tags include **Blog** and its Status is **Published** (or its Tags include **Published**). Edit those posts in Notion; the sync overwrites the file. Removing the tag or status hides the post rather than deleting it.
- **Never change `source_id`.** It is how the publisher finds the matching WordPress post.

## Content fields

Common to every type: `source_id` (required), `title`, `slug`, `summary`, `tags`, `featured`, `hidden`, `wp_id` (the WordPress post this file corresponds to), `format` (`markdown` or `html`), `synced` (sync jobs only).

| Type | Folder | Required | Other fields |
| --- | --- | --- | --- |
| article | `_posts` | `date` | `categories`, `banner`, `syndicate_to`, `legacy_url` |
| external_article | `_external` | `date`, `publication`, `url` | |
| talk | `_talks` | `date`, `event` | `location`, `youtube_id`, `video_url`, `slides_url`, `writeup_url` |
| project | `_projects` | `era` | `role`, `status`, `year`, `repo`, `demo`, `writeup_url`, `github` (owner/repo for sync) |
| photo_album | `_photos` | `flickr_id` | `place`, `date` |

Article file names follow Jekyll's `YYYY-MM-DD-slug.md` (or `.html`). The URL is `/articles/<slug>/`, the same as WordPress. `featured: true` puts a project or talk on the homepage.

**YouTube matching.** A playlist video is matched to a talk by its `youtube_id`, then by `_data/youtube_map.yml` (video ID to `source_id`, for recordings titled differently from the talk or second recordings of one talk), then by title. A matched talk without a video gets the `youtube_id`; an unmatched video becomes a new hidden talk file.

**Flickr selection.** Albums whose title starts with `YYYY-MM-DD` are added automatically, minus `_data/flickr_exclude.yml` (troop trips with other families' children, conferences), plus `_data/flickr_include.yml` (older trips without a date prefix). Only public photos are read.

## Setup

### Staging site (GitHub Pages)

1. Settings › Pages › Build and deployment › Source: **GitHub Actions**.
2. Same page, Custom domain: clear `highearthorbit.com` (the domain stays with WordPress). The site is then at `https://ajturner.github.io/highearthorbit.com/`. To use a subdomain such as `staging.highearthorbit.com` instead, add a CNAME DNS record pointing to `ajturner.github.io` and enter it here.
3. Settings › General › Pull Requests: enable **Allow auto-merge** (for the weekly sync).

### Sync keys (Settings › Secrets and variables › Actions)

| Secret | Value |
| --- | --- |
| `FLICKR_API_KEY` | From the Flickr App Garden |
| `YOUTUBE_API_KEY` (optional) | Google Cloud, YouTube Data API v3. Without it the sync reads the public playlist feed, the playlist page and oEmbed, which is slower but complete |
| `NOTION_TOKEN` | An internal integration from notion.so/profile/integrations with read access, connected to the Writing database (database ••• menu › Connections) |
| `SYNC_TOKEN` (optional) | Fine-grained token with contents and pull-request write access to this repository. Without it, CI does not run on the sync pull request and the merge does not redeploy the site; the nightly deploy catches up |

GitHub repo stats need no key.

### Later: publishing to WordPress

Not needed for staging. When you are ready:

1. WordPress: create a user `heo-sync` (Editor) with an application password; set Settings › Reading to a static front page with **Articles** as the posts page; make sure WP-CLI is installed on the server.
2. SSH deploy key:
   ```sh
   ssh-keygen -t ed25519 -N '' -C github-deploy -f heo_deploy
   ssh-copy-id -i heo_deploy.pub you@your-host
   ssh-keyscan -t ed25519 your-host > known_hosts
   ```
3. A `production` environment with secrets `WP_USER`, `WP_APP_PASSWORD`, `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`, `SSH_USER`, `SSH_HOST` and variables `WP_PATH`, `WP_URL`, `HEO_NEW_STATUS` (`draft` at first).
4. Run **Deploy plugin and theme**, then **Publish content** with *dry run* checked, and review.

Archive posts are matched to their WordPress posts by `wp_id` and **adopted without overwriting**: the first publish links the post and records the file's hash, leaving the WordPress copy as it is. Content is sent only when you later edit the file (or run with *force*). A `wp_id` that points at a post another file already manages is refused rather than overwritten.

Still to do before editing archive posts here: rewrite `/assets/uploads/` image paths to `/wp-content/uploads/` when sending them to WordPress.

## Local commands

```sh
bundle install && bundle exec jekyll serve   # http://localhost:4000
pip install -r requirements.txt
python -m scripts.heo.validate               # schema checks
python -m pytest                             # unit tests
python3 scripts/ci/check_links.py _site      # after a build
```
