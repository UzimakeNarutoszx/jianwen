// Run: node webpage/tests/today-audio.test.cjs
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const audio = require('../js/today-audio.js')

function manifest(overrides = {}) {
  return Object.assign({
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
      { article_id: 'a', title: '第一篇', position: 0, audio: { jianwen: { url: '/uploads/tts/2026-11-08/a/jianwen.mp3', duration: 182.4 }, vivian: { url: '/uploads/tts/2026-11-08/a/vivian.mp3', duration: 180 } } },
      { article_id: 'b', title: '第二篇', position: 1, audio: { jianwen: { url: '/uploads/tts/2026-11-08/b/jianwen.mp3', duration: 90 }, dylan: { url: '/uploads/tts/2026-11-08/b/dylan.mp3', duration: 91 } } },
      { article_id: 'c', title: '第三篇', position: 2, audio: { vivian: { url: '/uploads/tts/2026-11-08/c/vivian.mp3', duration: 120 } } }
    ]
  }, overrides)
}

// 第一篇 / 最后一篇：到头禁用对应方向。
{
  let state = audio.createTodayAudioState(manifest(), '')
  assert.equal(audio.canPrev(state), false, '第一篇不能再往前')
  assert.equal(audio.canNext(state), true, '第一篇可以往后')
  state = audio.setIndex(state, 99)
  assert.equal(state.index, 2, '越界索引收敛到最后一篇')
  assert.equal(audio.canNext(state), false, '最后一篇不能再往后')
  assert.equal(audio.canPrev(state), true, '最后一篇可以往前')
  assert.equal(audio.step(state, 1), state, '到末尾再点下一篇状态不变')
  const single = audio.createTodayAudioState(manifest({ articles: [manifest().articles[0]] }), '')
  assert.equal(audio.canPrev(single), false)
  assert.equal(audio.canNext(single), false)
}

// 自动续播只发生在当日清单内，最后一篇停下。
{
  let state = audio.createTodayAudioState(manifest(), '')
  const first = audio.afterEnded(state)
  assert.equal(first.play, true)
  assert.equal(first.state.index, 1)
  const second = audio.afterEnded(first.state)
  assert.equal(second.play, true)
  assert.equal(second.state.index, 2)
  const last = audio.afterEnded(second.state)
  assert.equal(last.play, false, '最后一篇播完即停')
  assert.equal(last.finished, true)
  assert.equal(last.state.index, 2)
}

// 声音回退：保存的声音在这篇没有时退回第一个可用声音，并在切篇时重新回退。
{
  let state = audio.createTodayAudioState(manifest(), 'dylan')
  assert.equal(state.voice, 'jianwen', '第一篇没有 dylan，回退到第一个可用声音')
  const kept = audio.createTodayAudioState(manifest(), 'vivian')
  assert.equal(kept.voice, 'vivian', '用户保存的声音可用时保留')
  state = audio.selectVoice(audio.setIndex(kept, 1), 'vivian')
  assert.equal(state.voice, 'jianwen', '第二篇没有 vivian，回退到 jianwen')
  state = audio.setIndex(state, 2)
  assert.equal(state.voice, 'vivian', '第三篇只有 vivian，自动切到 vivian')
  assert.equal(audio.selectVoice(state, 'dylan').voice, 'vivian', '选一个本页没有的声音时仍停在可用声音')
  const options = audio.voiceOptions(state)
  assert.deepEqual(options.map(item => [item.id, item.available]), [['jianwen', false], ['vivian', true], ['uncle_fu', false], ['dylan', false]])
  assert.equal(options.find(item => item.id === 'vivian').active, true)
}

// 音色下拉：option 只列这篇能播的声音，选中项跟 state.voice 一致，切换按比例保留进度由 DOM 层负责。
{
  const first = audio.createTodayAudioState(manifest(), 'vivian')
  const firstSelect = audio.voiceSelect(first)
  assert.equal(firstSelect.disabled, false, '有音频时下拉可用')
  assert.equal(firstSelect.empty, false)
  assert.deepEqual(firstSelect.options.map(item => item.id), ['jianwen', 'vivian'], '第一篇能播 jianwen / vivian，只列这两个')
  assert.deepEqual(firstSelect.options.map(item => item.label), ['见闻', '周报'], 'option 文案取 voices 里的 label')
  assert.equal(firstSelect.value, 'vivian', '保存的声音可用时下拉停在该声音')
  assert.deepEqual(firstSelect.options.filter(item => item.selected).map(item => item.id), ['vivian'], '只有一个 option 是选中态')
  assert.deepEqual(audio.voiceChoices(first).map(item => item.id), ['jianwen', 'vivian'])

  const third = audio.setIndex(first, 2)
  const thirdSelect = audio.voiceSelect(third)
  assert.deepEqual(thirdSelect.options.map(item => item.id), ['vivian'], '第三篇只有 vivian，option 数量为 1')
  assert.equal(thirdSelect.value, 'vivian')
  assert.equal(thirdSelect.disabled, false)

  const second = audio.setIndex(audio.createTodayAudioState(manifest(), ''), 1)
  assert.deepEqual(audio.voiceSelect(second).options.map(item => item.id), ['jianwen', 'dylan'], '第二篇能播 jianwen / dylan')

  // 清单未就绪 / 正在加载：select 禁用，且保留全部声音名让用户看到有哪些声音。
  const pending = audio.createTodayAudioState({ date: '2026-11-08', ready: false, voices: manifest().voices, articles: [] }, 'vivian')
  const pendingSelect = audio.voiceSelect(pending)
  assert.equal(pendingSelect.disabled, true, 'ready:false 时音色下拉禁用')
  assert.equal(pendingSelect.options.length, 4, 'ready:false 时仍列出声音表里的全部声音')
  assert.equal(audio.voiceSelect(audio.withLoading(pending, true)).disabled, true, '加载中下拉禁用')
  assert.equal(audio.voiceSelect(audio.withLoading(first, true)).disabled, true, '加载中即使有音频也禁用下拉')

  const noAudio = audio.createTodayAudioState(manifest({ articles: [{ article_id: 'x', title: '无音频', position: 0, audio: {} }] }), '')
  const noAudioSelect = audio.voiceSelect(noAudio)
  assert.equal(noAudioSelect.empty, true, '这篇没有任何声音时标记 empty')
  assert.equal(noAudioSelect.disabled, true, '没有可播声音时下拉禁用')
  assert.deepEqual(noAudioSelect.options, [])

  assert.equal(audio.isPlayable(first), true)
  assert.equal(audio.isPlayable(pending), false, 'ready:false 时播放按钮与进度条同样不可用')
  assert.equal(audio.isPlayable(noAudio), false)
  assert.equal(audio.isPlayable(audio.withLoading(first, true)), false, '加载中不可播放')
}

// DOM 骨架：音色是原生 select（不再是 role=radio 按钮排），标签、进度与无障碍属性都在。
{
  const source = fs.readFileSync(path.join(__dirname, '../js/today-audio.js'), 'utf8')
  const skeleton = source.slice(source.indexOf('const SKELETON'), source.indexOf('function mount'))
  assert.match(skeleton, /<select[^>]*data-el="voice-select"/, '音色用原生 select')
  assert.match(skeleton, /<label[^>]*for="today-audio-voice"[^>]*>声音<\/label>/, 'select 有「声音」label')
  assert.match(skeleton, /<select[^>]*id="today-audio-voice"/, 'label 的 for 指向 select 的 id')
  assert.doesNotMatch(skeleton, /role="radio"/, '不再有 role=radio 的音色按钮')
  assert.doesNotMatch(skeleton, /ta-voices/, '旧的音色按钮容器已移除')
  assert.match(skeleton, /class="ta-progress"/, '进度条独占一行')
  assert.match(skeleton, /aria-valuetext="0:00 \/ 0:00"/, '进度条保留 aria-valuetext')
  assert.match(skeleton, /data-act="prev"[^>]*aria-label="上一篇"/, '上一篇 aria-label')
  assert.match(skeleton, /data-act="next"[^>]*aria-label="下一篇"/, '下一篇 aria-label')
  assert.match(skeleton, /data-act="play"[^>]*aria-label="播放朗读"/, '播放按钮 aria-label')
}

// ready:false / 请求失败：状态提示生成中，控件全部不可用。
{
  for (const raw of [{ date: '2026-11-08', ready: false, voices: [{ id: 'jianwen', label: '见闻' }], articles: [] }, null, {}, { ready: true, articles: [] }]) {
    const state = audio.createTodayAudioState(raw, 'vivian')
    assert.equal(audio.statusLabel(state), raw && raw.ready === true ? '今日暂无可朗读的文章' : audio.PENDING_TEXT)
    assert.equal(audio.hasTrack(state), false)
    assert.equal(audio.canPrev(state), false)
    assert.equal(audio.canNext(state), false)
    assert.equal(audio.currentTrack(state), null)
    const ended = audio.afterEnded(state)
    assert.equal(ended.play, false)
  }
  const pending = audio.createTodayAudioState({ ready: false, articles: [] }, '')
  assert.equal(audio.statusLabel(audio.withLoading(pending, true)), '正在读取今日朗读')
}

// 进度、时长与标题展示。
{
  const state = audio.createTodayAudioState(manifest(), 'uncle_fu')
  assert.equal(state.voice, 'jianwen', 'uncle_fu 一个都没有时回退到默认第一个可用')
  const track = audio.currentTrack(state)
  assert.equal(track.title, '第一篇')
  assert.equal(track.total, 3)
  assert.equal(audio.formatTime(0), '0:00')
  assert.equal(audio.formatTime(182.4), '3:02')
  assert.equal(audio.formatTime(9.9), '0:09')
  assert.equal(audio.formatTime(NaN), '0:00')
  assert.equal(audio.progressRatio(91.2, 182.4), 0.5)
  assert.equal(audio.progressRatio(200, 182.4), 1, '比例夹在 0–1')
  assert.equal(audio.progressRatio(10, 0), 0)
  assert.equal(audio.ratioToSeconds(0.5, 182.4), 91.2)
  assert.equal(audio.ratioToSeconds(2, 182.4), 182.4)
  assert.equal(audio.statusLabel(state), '')
}

// 缺字段 / 脏数据不影响渲染。
{
  const state = audio.createTodayAudioState({ ready: true, voices: 'bad', articles: [{ article_id: 'x', audio: { jianwen: { url: '', duration: 'x' }, dylan: { url: '/v.mp3', duration: -1 } } }, null, { title: 'no id' }] }, '')
  assert.equal(state.articles.length, 1)
  assert.equal(Object.keys(state.articles[0].audio).length, 1, '空 url 的声音被丢弃')
  assert.equal(state.articles[0].audio.dylan.duration, 0)
  assert.equal(state.voice, 'dylan')
  assert.equal(state.voices.length, audio.DEFAULT_VOICES.length, 'voices 非法时用默认真实声音表')
}

// 标题按中文标点切段，换行只落在标点后，不会把「启动」劈成两半。
{
  assert.deepEqual(audio.titleChunks('二十一大代表选举启动，2360名代表怎么选'), ['二十一大代表选举启动，', '2360名代表怎么选'])
  assert.deepEqual(audio.titleChunks('无标点标题'), ['无标点标题'])
  assert.deepEqual(audio.titleChunks(''), [])
}

console.log('今日朗读：切换边界、声音回退、ready:false、进度与脏数据校验通过。')


// 连续音轨：优先整条播放，段内按时间映射到篇目。
{
  const m = manifest({
    continuous: {
      jianwen: {
        url: '/uploads/tts/2026-11-08/continuous-jianwen.mp3',
        duration: 300,
        segments: [
          { article_id: 'a', start: 0, end: 182.4 },
          { article_id: 'b', start: 183, end: 273 }
        ]
      }
    }
  })
  let state = audio.createTodayAudioState(m, 'jianwen')
  const continuous = audio.continuousFor(state)
  assert.ok(continuous, '识别连续音轨')
  assert.equal(continuous.url, '/uploads/tts/2026-11-08/continuous-jianwen.mp3')
  assert.equal(audio.isPlayable(state), true, '有连续音轨即可播放')
  assert.equal(audio.segmentIndexAt(continuous, 10), 0)
  assert.equal(audio.segmentIndexAt(continuous, 200), 1)
  state = audio.createTodayAudioState(m, 'vivian')
  assert.equal(audio.continuousFor(state), null, '该声音没有连续音轨时回退逐篇')
}
