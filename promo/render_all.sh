#!/bin/zsh
# 按分镜时长依次渲染全部 Blender 镜头，日志写到 output/promo-video/render/render.log
# 用法: promo/render_all.sh [--preview]
set -euo pipefail
cd "${0:A:h}/.."
B=/Applications/Blender.app/Contents/MacOS/Blender
P=promo/blender
FLAG=${1:-}
LOG=output/promo-video/render/render.log
: > $LOG

# 镜头名 时长（秒），与 promo/narration 时间点对应
SHOTS=(hook 4 today 10 article 10 ask 10 discover 9)
for name secs in $SHOTS; do
  echo "[$(date +%T)] $name ${secs}s" | tee -a $LOG
  $B -b --factory-startup --python $P/phone.py -- $name $secs $FLAG >> $LOG 2>&1
done
echo "[$(date +%T)] web 7.5s" | tee -a $LOG
$B -b --factory-startup --python $P/laptop.py -- web 7.5 $FLAG >> $LOG 2>&1
echo "[$(date +%T)] ajin 6s" | tee -a $LOG
$B -b --factory-startup --python $P/ajin.py -- 6 $FLAG >> $LOG 2>&1
echo "[$(date +%T)] done" | tee -a $LOG
grep -nE "Traceback|Error" $LOG || true
