#!/usr/bin/env bash
# Throwaway WordPress test: install WordPress on SQLite, load this repo's plugin
# and theme, publish all content, and check that every page type renders.
# Used by CI on each pull request; also runs locally. Needs php (with pdo_sqlite), git, curl, python3.
#
# Usage: scripts/ci/wp-test.sh [workdir]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="${1:-$(mktemp -d)}"
WP_VERSION="${WP_VERSION:-7.1.4}"
PORT="${PORT:-8899}"
SITE="$WORK/site"
URL="http://127.0.0.1:$PORT"

echo "::group::Install WordPress $WP_VERSION on SQLite in $WORK"
mkdir -p "$WORK"
[ -d "$WORK/wordpress" ] || git -c advice.detachedHead=false clone -q --depth 1 --branch "$WP_VERSION" https://github.com/WordPress/WordPress "$WORK/wordpress"
[ -d "$WORK/sqlite" ] || git clone -q --depth 1 https://github.com/WordPress/sqlite-database-integration "$WORK/sqlite"
[ -f "$WORK/wp-cli.phar" ] || curl -sSL -o "$WORK/wp-cli.phar" https://github.com/wp-cli/wp-cli/releases/download/v2.12.0/wp-cli-2.12.0.phar
rm -rf "$SITE" && mkdir -p "$SITE"
(cd "$WORK/wordpress" && git archive HEAD) | tar -x -C "$SITE"
PLUGIN="$SITE/wp-content/plugins/sqlite-database-integration"
cp -R "$WORK/sqlite/packages/plugin-sqlite-database-integration" "$PLUGIN"
rm -f "$PLUGIN/wp-includes/database" && cp -R "$WORK/sqlite/packages/mysql-on-sqlite/src" "$PLUGIN/wp-includes/database"
sed "s#{SQLITE_IMPLEMENTATION_FOLDER_PATH}#$PLUGIN#; s#{SQLITE_PLUGIN}#sqlite-database-integration/load.php#" "$PLUGIN/db.copy" > "$SITE/wp-content/db.php"
cat > "$SITE/wp-config.php" <<EOF
<?php
define('DB_NAME','wp'); define('DB_USER','x'); define('DB_PASSWORD','x'); define('DB_HOST','localhost');
define('DB_DIR', __DIR__ . '/wp-content/database/'); define('DB_FILE','test.sqlite');
define('WP_HOME','$URL'); define('WP_SITEURL','$URL');
define('WP_ENVIRONMENT_TYPE','local'); define('WP_DEBUG', true); define('WP_DEBUG_LOG', true); define('WP_DEBUG_DISPLAY', false);
\$table_prefix = 'wp_';
foreach (['AUTH_KEY','SECURE_AUTH_KEY','LOGGED_IN_KEY','NONCE_KEY','AUTH_SALT','SECURE_AUTH_SALT','LOGGED_IN_SALT','NONCE_SALT'] as \$k) define(\$k, 'ci-'.\$k);
if ( ! defined('ABSPATH') ) define('ABSPATH', __DIR__ . '/');
require_once ABSPATH . 'wp-settings.php';
EOF
mkdir -p "$SITE/wp-content/database" "$SITE/wp-content/mu-plugins"
cp "$REPO/wordpress/mu-plugins/heo-content.php" "$SITE/wp-content/mu-plugins/"
cp -R "$REPO/wordpress/themes/heo" "$SITE/wp-content/themes/heo"
WP="php $WORK/wp-cli.phar --path=$SITE --allow-root --quiet"
$WP core install --url="$URL" --title="High Earth Orbit (test)" --admin_user=admin --admin_password=admin --admin_email=ci@example.com --skip-email
$WP rewrite structure '/articles/%postname%/'
$WP theme activate heo
HOME_ID=$($WP post create --post_type=page --post_title=Home --post_status=publish --porcelain)
ARTICLES_ID=$($WP post create --post_type=page --post_title=Articles --post_name=articles --post_status=publish --porcelain)
$WP option update show_on_front page
$WP option update page_on_front "$HOME_ID"
$WP option update page_for_posts "$ARTICLES_ID"
$WP user create heo-sync sync@example.com --role=editor --porcelain >/dev/null
APP_PASSWORD=$($WP user application-password create heo-sync ci --porcelain)
echo "::endgroup::"

cat > "$WORK/router.php" <<EOF
<?php
\$root = '$SITE';
\$path = parse_url(\$_SERVER['REQUEST_URI'], PHP_URL_PATH);
if (\$path !== '/' && file_exists(\$root . \$path) && !is_dir(\$root . \$path)) return false;
chdir(\$root); require \$root . '/index.php';
EOF
php -S "127.0.0.1:$PORT" -t "$SITE" "$WORK/router.php" > "$WORK/server.log" 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -s -o /dev/null --noproxy '*' "$URL/" && break; sleep 0.5; done

echo "::group::Publish content (all items, new items published)"
cd "$REPO"
export NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"
WP_URL="$URL" WP_USER=heo-sync WP_APP_PASSWORD="$APP_PASSWORD" HEO_NEW_STATUS=publish python3 -m scripts.heo.publish
echo "Second run must change nothing:"
WP_URL="$URL" WP_USER=heo-sync WP_APP_PASSWORD="$APP_PASSWORD" python3 -m scripts.heo.publish | tee "$WORK/second.txt"
grep -q "unchanged" "$WORK/second.txt" && ! grep -qE "created|updated|adopted" "$WORK/second.txt"
echo "::endgroup::"

echo "::group::Check pages"
fail=0
check() {
  local path="$1" expect="$2"
  local code body
  body="$(curl -s --noproxy '*' -w '\n%{http_code}' "$URL$path")"
  code="${body##*$'\n'}"
  if [ "$code" != "200" ]; then echo "FAIL $path -> HTTP $code"; fail=1; return; fi
  if [ -n "$expect" ] && ! grep -qF "$expect" <<<"$body"; then echo "FAIL $path: missing '$expect'"; fail=1; return; fi
  if grep -qE "(Fatal error|Warning:|Notice:)" <<<"$body"; then echo "FAIL $path: PHP error in output"; fail=1; return; fi
  echo "ok   $path"
}
check / "heo-kicker"
check /articles/ ""
check /projects/ "heo-card"
check /talks/ ""
check /photos/ ""
first_project="$(ls content/_projects/*.md 2>/dev/null | head -1)"
if [ -n "$first_project" ]; then
  slug="$(python3 -c "import sys; sys.path.insert(0,'.'); from scripts.heo.content import load, slugify; from pathlib import Path; i=load(Path('$first_project')); print(i.meta.get('slug') or slugify(i.meta['title']))")"
  check "/projects/$slug/" "heo-kicker"
fi
if [ -s "$SITE/wp-content/debug.log" ]; then
  echo "PHP debug log:"; cat "$SITE/wp-content/debug.log"
  grep -qE "PHP (Fatal|Warning|Parse)" "$SITE/wp-content/debug.log" && fail=1
fi
echo "::endgroup::"
exit $fail
