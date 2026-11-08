#!/bin/bash
# 把当天生成的音频同步到服务器：先传音频、最后传 manifest.json（先 .tmp 再 mv，避免前端读到半个文件）。
# 然后修属主与权限，并只保留最近 7 个日期目录（名字形如 YYYY-MM-DD）。
# 用法: tts-daily/upload.sh [YYYY-MM-DD]      （环境变量 HOST 可换主机别名，默认 aliyun）
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-aliyun}"
REMOTE="/opt/jianwen/backend/uploads/tts"
DATE="${1:-$(TZ=Asia/Shanghai date +%F)}"
SRC="$HERE/out/$DATE"

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }

[[ -d "$SRC" ]] || { log "没有 ${SRC}，先跑 generate.py"; exit 1; }
[[ -f "$SRC/manifest.json" ]] || { log "$SRC/manifest.json 不存在，先跑 generate.py"; exit 1; }
grep -q "\"date\": \"$DATE\"" "$SRC/manifest.json" || { log "$SRC/manifest.json 里的 date 不是 ${DATE}，中止"; exit 1; }

log "同步 $DATE 音频 → $HOST:$REMOTE/$DATE/"
ssh "$HOST" "mkdir -p '$REMOTE/$DATE'"
rsync -az --exclude 'manifest.json' --exclude '.*.key' "$SRC/" "$HOST:$REMOTE/$DATE/"
rsync -az "$SRC/manifest.json" "$HOST:$REMOTE/$DATE/manifest.json.tmp"
ssh "$HOST" "mv -f '$REMOTE/$DATE/manifest.json.tmp' '$REMOTE/$DATE/manifest.json'"
log "manifest.json 已就位（最后上传，前端不会读到半个文件）"

log "修属主 jianwen:jianwen，目录 755 / 文件 644"
ssh "$HOST" "REMOTE='$REMOTE' bash -s" <<'EOS'
set -e
chown -R jianwen:jianwen "$REMOTE"
find "$REMOTE" -mindepth 1 -type d -exec chmod 755 {} +
find "$REMOTE" -type f -exec chmod 644 {} +
EOS

# 只保留最近 7 个日期目录：删掉名字形如 YYYY-MM-DD 且早于 DATE-6 天的目录
CUTOFF="$(TZ=Asia/Shanghai date -j -v-6d -f '%Y-%m-%d' "$DATE" +%F 2>/dev/null \
  || TZ=Asia/Shanghai date -d "$DATE -6 days" +%F)"
log "清理 $REMOTE 下早于 $CUTOFF 的日期目录"
ssh "$HOST" "REMOTE='$REMOTE' CUTOFF='$CUTOFF' bash -s" <<'EOS'
set -e
cd "$REMOTE"
for d in 20[0-9][0-9]-[0-1][0-9]-[0-3][0-9]/; do
  [ -d "$d" ] || continue
  name="${d%/}"
  if [[ "$name" < "$CUTOFF" ]]; then echo "删除 $name"; rm -rf "$name"; fi
done
EOS

log "完成：$REMOTE/$DATE/manifest.json"
