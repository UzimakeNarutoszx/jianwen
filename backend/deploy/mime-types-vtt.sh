#!/usr/bin/env bash
# Ensure `.vtt` subtitles are served as text/vtt by the live 1Panel OpenResty container.
#
# Why this exists: the live MIME table is the host file
#   /opt/1panel/apps/openresty/openresty/conf/mime.types
# mounted into the container as conf/mime.types. A rebuild/reinstall resets it, and
# without this entry browsers reject the weekly-video <track> with
# "application/octet-stream". The 2026-11-22 fix lived only on the server, so this
# script makes it reproducible. Safe to run repeatedly (idempotent).
#
# Env: REMOTE_HOST=aliyun CONTAINER=1Panel-openresty-7PTV
#      MIME_FILE=/opt/1panel/apps/openresty/openresty/conf/mime.types
#      CHECK_URL=https://jianwen.xin/assets/weekly-video/2026-W47/captions.vtt
set -euo pipefail

REMOTE_HOST=${REMOTE_HOST:-aliyun}
MIME_FILE=${MIME_FILE:-/opt/1panel/apps/openresty/openresty/conf/mime.types}
CONTAINER=${CONTAINER:-1Panel-openresty-7PTV}
CHECK_URL=${CHECK_URL:-https://jianwen.xin/assets/weekly-video/2026-W47/captions.vtt}

ssh "$REMOTE_HOST" bash -s -- "$MIME_FILE" "$CONTAINER" <<'REMOTE'
set -euo pipefail
MIME_FILE=$1
CONTAINER=$2

if grep -qE '^[[:space:]]*text/vtt[[:space:]]+vtt;' "$MIME_FILE"; then
  echo "mime: text/vtt already present in $MIME_FILE (no change)"
  backup=''
else
  backup="$MIME_FILE.bak-$(date +%Y%m%d%H%M%S)"
  cp -a "$MIME_FILE" "$backup"
  printf 'text/vtt vtt;\n' >> "$MIME_FILE"
  echo "mime: appended 'text/vtt vtt;' to $MIME_FILE (backup: $backup)"
fi

# The mounted copy inside the container is what nginx actually reads.
docker exec "$CONTAINER" grep -qE '^[[:space:]]*text/vtt[[:space:]]+vtt;' /usr/local/openresty/nginx/conf/mime.types \
  || { echo 'mime: container does not see text/vtt' >&2; [ -n "$backup" ] && cp -a "$backup" "$MIME_FILE"; exit 1; }

if ! docker exec "$CONTAINER" openresty -t; then
  echo 'mime: openresty -t failed; rolling back' >&2
  [ -n "$backup" ] && cp -a "$backup" "$MIME_FILE"
  exit 1
fi
docker exec "$CONTAINER" openresty -s reload
echo 'mime: openresty config ok and reloaded'
REMOTE

echo "mime: live check $CHECK_URL"
curl -fsSI "$CHECK_URL" | grep -i '^content-type:' || {
  echo 'mime: live check failed (expected content-type: text/vtt)' >&2
  exit 1
}
