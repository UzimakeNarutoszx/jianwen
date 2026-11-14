import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
// uni-app 源码按 ESM 打包，但 frontend 没有 package type:module，因此用 data URL 载入。
const source = readFileSync(new URL('../utils/today-audio-state.js', import.meta.url))
const {
  DEFAULT_VOICES, VOICE_STORAGE_KEY, PENDING_TEXT, normalizeManifest, resolveVoice, createTodayAudioState, setIndex, step,
  canPrev, canNext, selectVoice, currentTrack, hasTrack, voiceOptions, afterEnded, formatTime, progressRatio, ratioToSeconds, statusLabel
} = await import(`data:text/javascript;base64,${source.toString('base64')}`)

const audio = (suffix, duration) => ({ url: `/uploads/tts/2026-11-08/${suffix}/${suffix}.mp3`, duration })
const manifest = (overrides = {}) => Object.assign({
  date: '2026-11-08',
  generated_at: '2026-11-08T06:31:02+08:00',
  ready: true,
  voices: [
    { id: 'jianwen', label: '见闻' },
    { id: 'vivian', label: '周报' },
    { id: 'uncle_fu', label: '男声·沉稳' },
    { id: 'dylan', label: '男声·京味' }
  ],
  articles: [
    { article_id: 'a', title: '第一篇', position: 0, audio: { jianwen: audio('a', 182.4), vivian: { url: '/uploads/tts/2026-11-08/a/vivian.mp3', duration: 180.2 } } },
    { article_id: 'b', title: '第二篇', position: 1, audio: { jianwen: audio('b', 90), dylan: { url: '/uploads/tts/2026-11-08/b/dylan.mp3', duration: 91 } } },
    { article_id: 'c', title: '第三篇', position: 2, audio: { vivian: { url: '/uploads/tts/2026-11-08/c/vivian.mp3', duration: 120 } } }
  ]
}, overrides)

test('切换边界：第一篇禁用上一篇，最后一篇禁用下一篇，越界收敛', () => {
  let state = createTodayAudioState(manifest(), '')
  assert.equal(canPrev(state), false)
  assert.equal(canNext(state), true)
  assert.equal(step(state, -1), state)
  state = setIndex(state, 99)
  assert.equal(state.index, 2)
  assert.equal(canNext(state), false)
  assert.equal(canPrev(state), true)
  assert.equal(step(state, 3), state)
  assert.equal(setIndex(state, -5).index, 0)
  const only = createTodayAudioState(manifest({ articles: [manifest().articles[0]] }), '')
  assert.equal(canNext(only), false)
  assert.equal(canPrev(only), false)
  const empty = createTodayAudioState(manifest({ articles: [] }), '')
  assert.equal(empty.index, 0)
  assert.equal(canPrev(empty), false)
  assert.equal(canNext(empty), false)
})

test('自动续播只限当日清单，最后一篇播完即停', () => {
  let state = createTodayAudioState(manifest(), '')
  const one = afterEnded(state)
  assert.equal(one.play, true)
  assert.equal(one.finished, false)
  assert.equal(one.state.index, 1)
  const two = afterEnded(one.state)
  assert.equal(two.play, true)
  assert.equal(two.state.index, 2)
  const three = afterEnded(two.state)
  assert.equal(three.play, false)
  assert.equal(three.finished, true)
  assert.equal(three.state, two.state)
})

test('声音回退：保存声音不可用时退回第一个可用声音，切篇重新回退', () => {
  let state = createTodayAudioState(manifest(), 'dylan')
  assert.equal(state.voice, 'jianwen')
  assert.equal(createTodayAudioState(manifest(), 'vivian').voice, 'vivian')
  state = setIndex(createTodayAudioState(manifest(), 'vivian'), 1)
  assert.equal(state.voice, 'jianwen', '第二篇没有周报声音')
  state = setIndex(state, 2)
  assert.equal(state.voice, 'vivian', '第三篇只有周报声音')
  assert.equal(selectVoice(state, 'uncle_fu').voice, 'vivian')
  assert.equal(selectVoice(state, 'vivian'), state, '重复选择同一声音不产生新状态')
  assert.deepEqual(voiceOptions(state).map(item => [item.id, item.available, item.active]), [
    ['jianwen', false, false], ['vivian', true, true], ['uncle_fu', false, false], ['dylan', false, false]
  ])
  assert.equal(resolveVoice(state, 2, 'jianwen'), 'vivian')
  const none = createTodayAudioState(manifest({ articles: [{ article_id: 'z', title: '无音频', audio: {} }] }), 'jianwen')
  assert.equal(none.voice, 'jianwen', '整篇没有音频时保留默认声音 id 以便界面显示')
  assert.equal(hasTrack(none), false)
  assert.equal(statusLabel(none), '这篇暂无可播放音频')
})

test('ready:false / 请求失败：显示生成中，控件禁用且不抛错', () => {
  const pending = { date: '2026-11-08', ready: false, voices: DEFAULT_VOICES, articles: [] }
  for (const raw of [pending, null, undefined, {}, 'oops']) {
    const state = createTodayAudioState(raw, 'vivian')
    assert.equal(statusLabel(state), PENDING_TEXT)
    assert.equal(state.ready, false)
    assert.equal(state.articles.length, 0)
    assert.equal(currentTrack(state), null)
    assert.equal(hasTrack(state), false)
    assert.equal(canPrev(state), false)
    assert.equal(canNext(state), false)
    assert.equal(afterEnded(state).play, false)
    assert.equal(voiceOptions(state).every(item => item.available === false), true)
  }
  const empty = createTodayAudioState(manifest({ articles: [] }), '')
  assert.equal(statusLabel(empty), '今日暂无可朗读的文章')
})

test('原始 manifest 没有 ready 字段时按有无文章推断', () => {
  const raw = manifest()
  delete raw.ready
  assert.equal(normalizeManifest(raw).ready, true)
  assert.equal(createTodayAudioState({ date: '2026-11-08', articles: [] }, '').ready, false)
})

test('进度、时长与展示文案', () => {
  const state = createTodayAudioState(manifest(), '')
  const track = currentTrack(state)
  assert.equal(track.articleId, 'a')
  assert.equal(track.title, '第一篇')
  assert.equal(track.index, 0)
  assert.equal(track.total, 3)
  assert.equal(track.duration, 182.4)
  assert.equal(track.url, '/uploads/tts/2026-11-08/a/a.mp3')
  assert.equal(formatTime(182.4), '3:02')
  assert.equal(formatTime(0), '0:00')
  assert.equal(formatTime(-1), '0:00')
  assert.equal(formatTime(59.9), '0:59')
  assert.equal(formatTime(undefined), '0:00')
  assert.equal(progressRatio(91.2, 182.4), 0.5)
  assert.equal(progressRatio(-5, 182.4), 0)
  assert.equal(progressRatio(400, 182.4), 1)
  assert.equal(progressRatio(10, 0), 0)
  assert.equal(ratioToSeconds(0.25, 182.4), 45.6)
  assert.equal(ratioToSeconds(-1, 182.4), 0)
  assert.equal(ratioToSeconds(5, 182.4), 182.4)
  assert.equal(VOICE_STORAGE_KEY, 'jianwen_tts_voice')
  assert.equal(statusLabel(state, true), '正在读取今日朗读')
  assert.equal(statusLabel(state), '')
})

test('脏数据被收敛：缺 title、空 url、非法 duration、缺 article_id', () => {
  const state = createTodayAudioState({
    ready: true,
    generated_at: 123,
    voices: [{ id: 'jianwen' }, { label: '缺 id' }, null],
    articles: [
      { article_id: 'k', audio: { jianwen: { url: '', duration: 10 }, vivian: { url: '/v.mp3', duration: 'x' } } },
      { title: '没有 id' },
      null
    ]
  }, '')
  assert.deepEqual(state.voices, [{ id: 'jianwen', label: 'jianwen' }])
  assert.equal(state.articles.length, 1)
  assert.equal(state.articles[0].title, '')
  assert.deepEqual(Object.keys(state.articles[0].audio), ['vivian'])
  assert.equal(state.articles[0].audio.vivian.duration, 0)
  // 声音表里只有 jianwen，这篇只有 vivian：没有可用声音时停在声音表第一位。
  assert.equal(state.voice, 'jianwen')
  assert.equal(hasTrack(state), false)
  assert.equal(currentTrack(state).duration, 0)
})

test('进度与秒数边界：current=0、负数、超 duration 均收敛到 0~1 或不超过 duration', () => {
  const base = 182.4
  // current=0: progressRatio(0, base) = 0, ratioToSeconds(0, base) = 0
  assert.equal(progressRatio(0, base), 0)
  assert.equal(ratioToSeconds(0, base), 0)
  // current 为负数: 收敛到 0
  assert.equal(progressRatio(-1, base), 0)
  assert.equal(ratioToSeconds(-0.5, base), 0)
  // current 超过 duration: progressRatio 收敛到 1, ratioToSeconds 收敛到 duration
  assert.equal(progressRatio(base * 2, base), 1)
  assert.equal(ratioToSeconds(base * 3, base), base)
  // 综合边界：确保所有值都在合理范围内
  assert.ok(progressRatio(-100, base) >= 0 && progressRatio(-100, base) <= 1)
  assert.ok(ratioToSeconds(-1, base) >= 0 && ratioToSeconds(-1, base) <= base)
})
