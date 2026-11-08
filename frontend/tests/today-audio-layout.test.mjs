import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

// 今日朗读播放器的排版约束：只读组件源码做静态断言，不依赖运行时。
const src = await readFile(new URL('../components/TodayAudioPlayer.vue', import.meta.url), 'utf8')
const template = src.slice(src.indexOf('<template>'), src.indexOf('</template>'))
const script = src.slice(src.indexOf('<script>'), src.indexOf('</script>'))
const style = src.slice(src.indexOf('<style'), src.indexOf('</style>'))

const topLevelKeys = () => [...script.matchAll(/^  (\w+)(?:\(\)\s*\{|:)/gm)].map(match => match[1])

test('音色改成 picker 下拉，不再是一排 radio 按钮', () => {
  assert.match(template, /<picker\b/, '音色选择要用 uni-app 的 picker')
  assert.match(template, /mode="selector"/, 'picker 用选择器模式')
  assert.match(template, /:range="voiceLabels"/, 'range 传声音 label 列表')
  assert.match(template, /@change="onVoiceChange"/, '选择后回到 chooseVoice 那条逻辑')
  assert.match(script, /onVoiceChange\(event\)/)
  assert.match(script, /this\.chooseVoice\(voice\.id\)/, 'onVoiceChange 最终走 chooseVoice(id)')
  const chooseVoice = script.slice(script.indexOf('chooseVoice(voiceId)'))
  assert.match(chooseVoice, /uni\.setStorageSync\(VOICE_STORAGE_KEY/, '仍然保存用户选择的声音')
  assert.match(chooseVoice, /this\.applyTrack\(true\)/, '换声音时保留播放进度')

  // 旧的一排按钮：radiogroup / role="radio" / v-for 铺 button 都不该再出现。
  assert.doesNotMatch(template, /radiogroup/)
  assert.doesNotMatch(template, /role="radio"/)
  assert.doesNotMatch(template, /aria-checked/)
  assert.doesNotMatch(template, /class="audio-voices"/)
  assert.doesNotMatch(style, /\.audio-voice\.is-active/)
})

test('下拉只列当前文章可播的声音，只有一个时锁定不弹出', () => {
  assert.match(script, /selectableVoices\(\)[\s\S]*?filter\(voice => voice\.available\)/)
  assert.match(script, /voiceLocked\(\)\s*\{[^}]*available\)\.length <= 1/)
  assert.match(template, /:disabled="voiceLocked"/, '只有一个可选声音时 picker 不弹出')
  assert.match(template, /voiceLocked \? 'is-locked' : ''/, '锁定时仍显示当前声音名')
})

test('五行布局：标题独立、声音独占一行、控制行居中、进度条占满宽度', () => {
  const order = ['audio-head', 'audio-title-block', 'audio-voice-row', 'audio-controls', 'audio-progress']
  const positions = order.map(name => template.indexOf(`class="${name}"`))
  assert.equal(positions.every(pos => pos >= 0), true, `缺少布局块：${order.filter((name, i) => positions[i] < 0).join(', ')}`)
  assert.deepEqual([...positions].sort((a, b) => a - b), positions, '布局块顺序必须是 顶行 → 标题 → 声音 → 控制 → 进度')

  assert.match(template, /class="audio-voice-label">声音</, '声音这一行左侧有文字标签')
  assert.match(template, /class="audio-times"[\s\S]*?currentLabel[\s\S]*?durationLabel/, '时间在进度条下方，左右两端')
  assert.match(style, /\.audio-times \{[^}]*justify-content: space-between/)
  assert.match(style, /\.today-audio \{[^}]*gap: (2[4-9]|[3-9]\d)rpx/, '各行间距至少 24rpx')
  assert.match(style, /\.audio-controls \{[^}]*justify-content: center/)
  assert.match(style, /\.audio-play \{[^}]*width: 112rpx;\s*height: 112rpx/, '播放键比切换键更大')
  assert.match(style, /\.audio-slider \{[^}]*width: 100%/, '进度条独占一行占满宽度')
  assert.match(style, /\.audio-title \{[^}]*line-clamp: 2/, '标题最多两行')
  assert.match(style, /\.audio-title \{[^}]*text-wrap: pretty/, '标题换行用 pretty')
})

test('UI 基线：无纯黑、无动态数字抖动、图标统一下移、暗色字重降 40%', () => {
  assert.doesNotMatch(src, /#000(?:000)?\b/i, '不使用纯黑')
  assert.doesNotMatch(style, /border:\s*1rpx solid #000/i, '不用实线黑边框分层')
  assert.match(style, /\.audio-count \{[^}]*font-variant-numeric: tabular-nums/)
  assert.match(style, /\.audio-time \{[^}]*font-variant-numeric: tabular-nums/)
  assert.match(style, /\.audio-icon \{[^}]*top: 0\.125em/, '图标统一由 .audio-icon 下移 0.125em')
  assert.doesNotMatch(style, /\.audio-play-icon \{[^}]*top:/, '播放图标不再单独调 margin/top')
  assert.match(style, /\.is-dark \.audio-title \{[^}]*font-weight: 360/)
  assert.match(style, /\.is-dark \.audio-eyebrow,[\s\S]{0,80}font-weight: 360/)
  assert.doesNotMatch(style, /\.is-dark [^{]*\{[^}]*font-weight: 600/, '暗色下 600 要降到 360')
})

test('标题按标点切段，避免中文词被换行劈开', () => {
  // 中文没有空格可断，long 标题要按标点切成 inline-block 整段。
  assert.match(template, /v-for="\(part, i\) in titleParts"/, '标题按 titleParts 逐段渲染')
  assert.match(template, /class="audio-title-chunk"/, '每段带 audio-title-chunk')
  assert.match(script, /titleParts\(\)\s*\{[\s\S]*?const text = String\(this\.title \|\| ''\)\.trim\(\)/, 'titleParts 基于现有 computed title')
  assert.match(script, /if \(!text\) return \[\]/, '空标题返回空数组')
  assert.match(script, /text\.match\(\/\[\^，、：；？！\]\+\[，、：；？！\]\?\/g\) \|\| \[text\]/, '切段正则与网站 titleChunks 一致')
  assert.match(style, /\.audio-title-chunk \{[^}]*display: inline-block/, '每段 inline-block，换行只发生在标点处')
  assert.match(style, /\.is-dark \.audio-title-chunk \{[^}]*color: #F4F7FA/, '暗色下分段继承标题颜色')
})

test('播放行为没被排版改坏', () => {
  assert.doesNotMatch(src, /obeyMuteSwitch\s*=/, 'App 端 obeyMuteSwitch 只读，赋值会让播放键失效')
  const keys = topLevelKeys()
  const dup = keys.filter((key, i) => keys.indexOf(key) !== i)
  assert.deepEqual(dup, [], '组件 script 不能有重复的顶层选项键')
  for (const method of ['startPlayback', 'loadSource', 'applyTrack', 'togglePlay', 'goPrev', 'goNext', 'chooseVoice', 'stopAudio', 'onSeeking', 'onSeek']) {
    assert.match(script, new RegExp(`\\n    ${method}\\(`), `保留方法 ${method}`)
  }
  assert.match(script, /const resumed = |const resume = this\.playing/, 'applyTrack 仍在播放时接着播')
  assert.match(script, /if \(typeof audio\.onSeeking === 'function'\)/, 'onSeeking 仍做存在性判断')
  assert.match(script, /this\.listen = createListenTracker\(\)/, 'listen 追踪器仍在')
  assert.match(script, /emits: \['listened'\]/)
  assert.match(script, /\$emit\('listened'/)
  assert.match(script, /playError: ''/)
  assert.match(script, /darkMode: \{ type: Boolean, default: false \}/)
})
