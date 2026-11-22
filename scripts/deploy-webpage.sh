#!/usr/bin/env bash
# Deploy the 见闻 static site to Aliyun without ever flattening webpage/jianwen/ into
# the site root (the 2026-11-22 incident: jianwen sub-pages overwrote /webpage/index.html).
#
# Usage:
#   scripts/deploy-webpage.sh                          # dry-run all allowed paths (md5 + rsync -n)
#   scripts/deploy-webpage.sh --apply                  # write all allowed paths
#   scripts/deploy-webpage.sh --only data/weekly-videos.json --apply
#   scripts/deploy-webpage.sh --with-media             # also push assets/weekly-video/ (large)
#
# Env: DEPLOY_REMOTE=aliyun  DEPLOY_ROOT=/opt/jianwen/webpage
# This script never passes --delete; removals are manual and reviewed.
set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SRC="$REPO_ROOT/webpage"
REMOTE=${DEPLOY_REMOTE:-aliyun}
DEST=${DEPLOY_ROOT:-/opt/jianwen/webpage}
APPLY=0
WITH_MEDIA=0
ONLY=()

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --dry-run) APPLY=0; shift ;;
    --with-media) WITH_MEDIA=1; shift ;;
    --only) [ $# -ge 2 ] || { echo '--only needs a path' >&2; exit 2; }; ONLY+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "usage: $0 [--apply] [--with-media] [--only <path>]..." >&2; exit 2 ;;
  esac
done

EXPECTED_ROOT_HTML=(avatar.html changelog.html index.html intro.html weekly-video.html)
ROOT_HTML=(); while IFS= read -r file; do ROOT_HTML+=("$file"); done < <(find "$SRC" -maxdepth 1 -type f -name '*.html' -print | sort)
SUB_HTML=(); while IFS= read -r file; do SUB_HTML+=("$file"); done < <(find "$SRC/jianwen" -maxdepth 1 -type f -name '*.html' -print | sort)

fail() { echo "REFUSE: $*" >&2; exit 1; }

# 1) The local root page set is exactly the five production pages.
ROOT_NAMES=$(printf '%s\n' "${ROOT_HTML[@]}" | xargs -n1 basename | sort | tr '\n' ' ')
if [ "$ROOT_NAMES" != "$(printf '%s\n' "${EXPECTED_ROOT_HTML[@]}" | sort | tr '\n' ' ')" ]; then
  fail "unexpected root html set: $ROOT_NAMES"
fi

# 2) Every allowed source maps to the same relative destination; jianwen/ keeps its prefix.
for file in "${SUB_HTML[@]}"; do
  rel=${file#"$SRC"/}
  dst=${rel#jianwen/}
  case "$dst" in */*) fail "sub-page would land outside jianwen/: $rel" ;; esac
done
if printf '%s\n' "${SUB_HTML[@]}" | xargs -n1 basename | sort | uniq -d | grep -q .; then
  fail "duplicate sub-page basenames"
fi

selected_roots=()
selected_subs=()
want_data=0; want_js=0; want_css=0; want_media=$WITH_MEDIA
if [ ${#ONLY[@]} -eq 0 ]; then
  selected_roots=("${EXPECTED_ROOT_HTML[@]}")
  for file in "${SUB_HTML[@]}"; do selected_subs+=("${file#"$SRC"/}"); done
  want_data=1; want_js=1; want_css=1
else
  for path in "${ONLY[@]}"; do
    case "$path" in
      data/*) want_data=1 ;;
      js/*) want_js=1 ;;
      css/*) want_css=1 ;;
      assets/weekly-video/*) want_media=1 ;;
      jianwen/*.html) [ -f "$SRC/$path" ] || fail "missing $path"; selected_subs+=("$path") ;;
      *.html) [ -f "$SRC/$path" ] || fail "missing $path"; selected_roots+=("$path") ;;
      *) fail "path not allowed: $path" ;;
    esac
  done
  for path in ${selected_subs[@]+"${selected_subs[@]}"}; do
    printf 'MAP %-46s -> %s/%s\n' "webpage/$path" "$DEST" "$path"
  done
fi

local_md5() { if command -v md5 >/dev/null 2>&1; then md5 -q "$SRC/$1"; else md5sum "$SRC/$1" | cut -d' ' -f1; fi; }
remote_md5() { ssh "$REMOTE" "md5sum '$DEST/$1' 2>/dev/null | cut -d' ' -f1" || true; }

echo
echo "== target: $REMOTE:$DEST =="
echo "== mode: $([ "$APPLY" -eq 1 ] && echo APPLY || echo DRY-RUN), media: $([ "$want_media" -eq 1 ] && echo yes || echo no) =="
echo
echo '== md5 diff (html + data) =='
CHANGED=0
md5_one() {
  local rel=$1 local remote status
  local=$(local_md5 "$rel"); remote=$(remote_md5 "$rel")
  if [ "$local" = "$remote" ]; then status=same; else status=CHANGED; CHANGED=$((CHANGED + 1)); fi
  printf '%-34s %-8s %s\n' "$rel" "$status" "${remote:-<missing>} -> $local"
}
for rel in ${selected_roots[@]+"${selected_roots[@]}"}; do md5_one "$rel"; done
[ "$want_data" -eq 1 ] && md5_one data/weekly-videos.json
for rel in ${selected_subs[@]+"${selected_subs[@]}"}; do md5_one "$rel"; done
echo "changed files: $CHANGED"

RSYNC=(rsync -a --itemize-changes)
[ "$APPLY" -eq 0 ] && RSYNC+=(-n)
if [ "$APPLY" -eq 1 ]; then
  ssh "$REMOTE" "mkdir -p '$DEST/jianwen' '$DEST/data' '$DEST/js' '$DEST/css' '$DEST/assets/weekly-video'"
fi

echo
if [ ${#selected_roots[@]} -gt 0 ]; then
  echo '== rsync plan: root pages (never jianwen/) =='
  for rel in ${selected_roots[@]+"${selected_roots[@]}"}; do "${RSYNC[@]}" "$SRC/$rel" "$REMOTE:$DEST/$rel"; done
fi
if [ "$want_data" -eq 1 ]; then
  echo '== rsync plan: data/ =='
  "${RSYNC[@]}" "$SRC/data/" "$REMOTE:$DEST/data/"
fi
if [ "$want_js" -eq 1 ]; then
  echo '== rsync plan: js/ =='
  "${RSYNC[@]}" "$SRC/js/" "$REMOTE:$DEST/js/"
fi
if [ "$want_css" -eq 1 ]; then
  echo '== rsync plan: css/ =='
  "${RSYNC[@]}" "$SRC/css/" "$REMOTE:$DEST/css/"
fi
if [ ${#selected_subs[@]} -gt 0 ]; then
  echo "== rsync plan: jianwen sub-pages -> $DEST/jianwen/ (never root) =="
  for rel in ${selected_subs[@]+"${selected_subs[@]}"}; do "${RSYNC[@]}" "$SRC/$rel" "$REMOTE:$DEST/jianwen/$(basename "$rel")"; done
fi
if [ "$want_media" -eq 1 ]; then
  echo '== rsync plan: assets/weekly-video/ (large) =='
  "${RSYNC[@]}" "$SRC/assets/weekly-video/" "$REMOTE:$DEST/assets/weekly-video/"
fi

if [ "$APPLY" -eq 0 ]; then
  echo
  echo 'dry-run only; re-run with --apply to write.'
  exit 0
fi

echo
echo '== verify remote root page list (must be exactly five) =='
remote_root=$(ssh "$REMOTE" "find '$DEST' -maxdepth 1 -type f -name '*.html' -printf '%f\n' | sort | tr '\n' ' '")
expected=$(printf '%s\n' "${EXPECTED_ROOT_HTML[@]}" | sort | tr '\n' ' ')
if [ "$remote_root" != "$expected" ]; then
  fail "remote root html set is '$remote_root', expected '$expected'"
fi
echo "root html: $remote_root"
echo "jianwen sub-pages: $(ssh "$REMOTE" "find '$DEST/jianwen' -maxdepth 1 -type f -name '*.html' | wc -l | tr -d ' '")"
echo 'deployed; no --delete was used.'
