import test from 'node:test'
import assert from 'node:assert/strict'
import { createListenTracker, trackListen, resetListenAnchor, finishListen } from '../utils/today-audio-state.js'

const play = (t, id, from, to, total, step = 0.25) => {
  let hit = false
  for (let x = from; x <= to + 1e-9; x += step) hit = trackListen(t, id, x, total) || hit
  return hit
}

test('真实播放累计到 90% 即判已读，且只触发一次', () => {
  const t = createListenTracker()
  assert.equal(play(t, 'a', 0, 80, 100), false)
  assert.equal(play(t, 'a', 80.25, 91, 100), true)
  assert.equal(play(t, 'a', 91.25, 100, 100), false, '已触发过不再重复')
})

test('拖动跳过的部分不计入', () => {
  const t = createListenTracker()
  play(t, 'a', 0, 10, 100)
  trackListen(t, 'a', 95, 100) // 直接拖到结尾：差值 > 2 秒，不计
  assert.equal(finishListen(t, 'a', 100), false)
})

test('换声音按比例累计，不清零', () => {
  const t = createListenTracker()
  play(t, 'a', 0, 60, 100) // 60%
  resetListenAnchor(t)
  assert.equal(play(t, 'a', 120, 200, 200), true, '新声音时长 200s，再听 40% 达标')
})

test('ended 补齐尾部空档；各篇独立', () => {
  const t = createListenTracker()
  play(t, 'a', 0, 89.5, 100)
  assert.equal(finishListen(t, 'a', 100), true)
  assert.equal(finishListen(t, 'b', 100), false)
})

test('播放器组件没有重复的顶层选项（重复 created 会让听完判定器丢失）', async () => {
  const { readFile } = await import('node:fs/promises')
  const src = await readFile(new URL('../components/TodayAudioPlayer.vue', import.meta.url), 'utf8')
  const script = src.slice(src.indexOf('<script>'), src.indexOf('</script>'))
  const keys = [...script.matchAll(/^  (\w+)(?:\(\)\s*\{|:)/gm)].map(m => m[1])
  const dup = keys.filter((k, i) => keys.indexOf(k) !== i)
  assert.deepEqual(dup, [])
  assert.match(src, /this\.listen = createListenTracker\(\)/)
  // App 端 obeyMuteSwitch 只读，赋值会让 ensureAudio 抛错、播放按钮失效。
  assert.doesNotMatch(src, /obeyMuteSwitch\s*=/)
})
