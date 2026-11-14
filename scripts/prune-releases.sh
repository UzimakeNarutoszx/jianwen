#!/usr/bin/env bash
# 只保留 latest.json 引用的 APK / WGT，删掉旧的安装包。
# 用法：scripts/prune-releases.sh [downloads目录]（默认 webpage/downloads）
set -euo pipefail
dir="${1:-webpage/downloads}"
latest="$dir/latest.json"
[ -f "$latest" ] || { echo "找不到 $latest" >&2; exit 1; }
keep_apk="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("apkUrl","").rsplit("/",1)[-1])' "$latest")"
keep_wgt="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("wgtUrl","").rsplit("/",1)[-1])' "$latest")"
echo "保留：${keep_apk:-无} ${keep_wgt:-无}"
for file in "$dir"/jianwen-*.apk "$dir"/jianwen-*.wgt; do
  [ -e "$file" ] || continue
  name="$(basename "$file")"
  if [ "$name" = "$keep_apk" ] || [ "$name" = "$keep_wgt" ]; then continue; fi
  echo "删除：$name"
  rm -f -- "$file" "$file.idsig"
done
