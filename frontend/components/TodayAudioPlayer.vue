<template>
  <view :class="['today-audio', darkMode ? 'is-dark' : '']">
    <view class="audio-head">
      <text class="audio-eyebrow">今日朗读</text>
      <text class="audio-count">
        <text class="audio-position">{{ positionLabel }}</text>
        <text class="audio-total">/ {{ totalLabel }} 篇</text>
      </text>
    </view>

    <view class="audio-title-block">
      <!-- 中文没有空格可断：按标点切段，每段整体换行，避免把「怎么选」劈开。 -->
      <view v-if="title" class="audio-title">
        <text v-for="(part, i) in titleParts" :key="i" class="audio-title-chunk">{{ part }}</text>
      </view>
      <text v-if="statusText" class="audio-status">{{ statusText }}</text>
    </view>

    <view class="audio-voice-row">
      <text class="audio-voice-label">声音</text>
      <picker
        class="audio-voice-picker"
        mode="selector"
        :range="voiceLabels"
        :value="voiceIndex"
        :disabled="voiceLocked"
        @change="onVoiceChange"
      >
        <view
          :class="['audio-voice-trigger', voiceLocked ? 'is-locked' : '']"
          :aria-label="`朗读声音：${voiceLabel}`"
        >
          <text class="audio-voice-name">{{ voiceLabel }}</text>
          <text class="audio-icon audio-caret">▾</text>
        </view>
      </picker>
    </view>

    <view class="audio-controls">
      <button class="audio-skip" :disabled="!prevEnabled" aria-label="上一篇" @click="goPrev">
        <text class="audio-icon">‹</text>
        <text class="audio-skip-text">上一篇</text>
      </button>
      <button
        :class="['audio-play', disabled ? 'is-disabled' : '']"
        :disabled="disabled"
        :aria-label="playing ? '暂停朗读' : '播放朗读'"
        @click="togglePlay"
      >
        <text class="audio-icon audio-play-icon">{{ playing ? '❚❚' : '▶' }}</text>
      </button>
      <button class="audio-skip" :disabled="!nextEnabled" aria-label="下一篇" @click="goNext">
        <text class="audio-skip-text">下一篇</text>
        <text class="audio-icon">›</text>
      </button>
    </view>

    <view class="audio-progress">
      <slider
        class="audio-slider"
        :value="sliderValue"
        :min="0"
        :max="1000"
        :step="1"
        :disabled="disabled"
        active-color="#1F5F7A"
        background-color="rgba(31,95,122,0.16)"
        block-size="18"
        :aria-label="`播放进度 ${currentLabel} / ${durationLabel}`"
        @changing="onSeeking"
        @change="onSeek"
      />
      <view class="audio-times">
        <text class="audio-time">{{ currentLabel }}</text>
        <text class="audio-time">{{ durationLabel }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { getTodayAudio, todayAudioUrl } from '@/utils/api.js'
import {
  VOICE_STORAGE_KEY,
  afterEnded,
  canNext,
  canPrev,
  createListenTracker,
  createTodayAudioState,
  currentTrack,
  finishListen,
  formatTime,
  hasTrack,
  progressRatio,
  ratioToSeconds,
  resetListenAnchor,
  selectVoice,
  statusLabel,
  step,
  trackListen,
  voiceOptions
} from '@/utils/today-audio-state.js'

export default {
  name: 'TodayAudioPlayer',
  props: {
    darkMode: { type: Boolean, default: false }
  },
  // listened：一篇真实播放累计 ≥ 90%，页面据此按已读处理。
  emits: ['listened'],
  data() {
    return {
      state: createTodayAudioState({ ready: false, articles: [] }, ''),
      loading: true,
      playing: false,
      currentTime: 0,
      knownDuration: 0,
      sliderValue: 0,
      seeking: false,
      playError: ''
    }
  },
  computed: {
    voices() { return voiceOptions(this.state) },
    // 下拉只列这篇有音频的声音；一个都没有时退回完整清单，好让标签仍能显示当前声音。
    selectableVoices() {
      const available = this.voices.filter(voice => voice.available)
      return available.length ? available : this.voices
    },
    voiceLabels() { return this.selectableVoices.map(voice => voice.label) },
    voiceIndex() {
      const index = this.selectableVoices.findIndex(voice => voice.active)
      return index < 0 ? 0 : index
    },
    voiceLabel() {
      const current = this.selectableVoices.find(voice => voice.active) || this.selectableVoices[0]
      return current ? current.label : '默认声音'
    },
    // 只有一个可播声音（或控件禁用）时，下拉照常显示，但不弹选择面板。
    voiceLocked() { return this.disabled || this.voices.filter(voice => voice.available).length <= 1 },
    track() { return currentTrack(this.state) },
    title() { return this.track ? this.track.title : '' },
    // 中文标题没有空格可断：先按标点切段，每段整体换行，避免把「怎么选」劈开（与网站 titleChunks 一致）。
    titleParts() {
      const text = String(this.title || '').trim()
      if (!text) return []
      return text.match(/[^，、：；？！]+[，、：；？！]?/g) || [text]
    },
    positionLabel() { return this.track ? String(this.track.index + 1) : '0' },
    totalLabel() { return String(this.state.articles.length) },
    statusText() { return this.playError || statusLabel(this.state, this.loading) },
    disabled() { return this.loading || !hasTrack(this.state) },
    prevEnabled() { return !this.loading && canPrev(this.state) },
    nextEnabled() { return !this.loading && canNext(this.state) },
    duration() {
      if (this.knownDuration > 0) return this.knownDuration
      return this.track ? this.track.duration : 0
    },
    currentLabel() { return formatTime(this.currentTime) },
    durationLabel() { return formatTime(this.duration) }
  },
  created() {
    // 音频上下文不放进 data：它不可序列化，也没必要参与响应式。
    this.audio = null
    this.audioSrc = ''
    // 「听完即读完」判定器：非响应式，只用于判定，不参与渲染。
    this.listen = createListenTracker()
  },
  mounted() {
    this.loadManifest()
  },
  methods: {
    loadManifest() {
      const saved = uni.getStorageSync(VOICE_STORAGE_KEY) || ''
      this.loading = true
      getTodayAudio()
        .then(manifest => {
          this.state = createTodayAudioState(manifest, uni.getStorageSync(VOICE_STORAGE_KEY) || saved)
          this.loading = false
          // 换源出错不能把已拿到的清单打回「生成中」：只记日志，用户点播放时会再加载一次。
          try { this.applyTrack(false) } catch (error) { console.error('[today-audio] applyTrack', error) }
        }, () => {
          // 生成中或请求失败都不报错，只显示「今日朗读生成中」。
          this.state = createTodayAudioState({ ready: false, articles: [] }, saved)
          this.loading = false
        })
    },
    // uni.createInnerAudioContext 每次换源都重新走一遍 src，进度按比例恢复。
    ensureAudio() {
      if (this.audio) return this.audio
      const audio = uni.createInnerAudioContext()
      audio.onPlay(() => { this.playing = true; this.playError = '' })
      audio.onPause(() => { this.playing = false })
      audio.onStop(() => { this.playing = false })
      audio.onTimeUpdate(() => {
        if (this.seeking) return
        this.currentTime = audio.currentTime || 0
        this.knownDuration = audio.duration > 0 ? audio.duration : this.knownDuration
        this.sliderValue = Math.round(progressRatio(this.currentTime, this.duration) * 1000)
        const track = this.track
        if (track && this.playing && trackListen(this.listen, track.articleId, this.currentTime, this.duration)) this.announceListened(track)
      })
      // 部分 App 运行时没有 onSeeking；拖动在 onSeek 里已重置锚点，这里只是兜底。
      try { if (typeof audio.onSeeking === 'function') audio.onSeeking(() => resetListenAnchor(this.listen)) } catch (error) {}
      audio.onEnded(() => this.handleEnded())
      audio.onError(error => {
        this.playing = false
        // 播放失败要让用户看到原因，而不是按钮按了没反应。
        this.playError = `播放失败${error && error.errCode ? `（${error.errCode}）` : ''}，请稍后重试`
        this.knownDuration = this.track ? this.track.duration : 0
      })
      this.audio = audio
      this.audioSrc = ''
      return audio
    },
    // 只改 src 不 play：真正出声要等用户点播放。
    loadSource(audio, ratio) {
      const track = this.track
      const url = track && track.url ? todayAudioUrl(track.url) : ''
      if (audio.src === url && this.audioSrc === url) return
      // Android 原生播放器未设过 src 时 stop() 会抛错，导致后面的 src 赋值被跳过。
      if (this.audioSrc) { try { audio.stop() } catch (error) {} }
      audio.src = url
      this.audioSrc = url
      if (!url || !ratio) return
      const seek = () => {
        audio.offCanplay(seek)
        try { audio.seek(ratioToSeconds(ratio, audio.duration || track.duration)) } catch (error) {}
      }
      audio.onCanplay(seek)
    },
    applyTrack(keepRatio) {
      resetListenAnchor(this.listen)
      const track = this.track
      // 正在播时换篇/换声音，接着播，不让用户再点一次。
      const resume = this.playing
      const ratio = keepRatio && this.audio ? progressRatio(this.audio.currentTime || 0, this.audio.duration || this.knownDuration) : 0
      this.playing = false
      this.currentTime = 0
      this.knownDuration = track ? track.duration : 0
      this.sliderValue = 0
      // 用户还没点播放就先不建上下文，避免每次进页面都占一个音频实例。
      if (!track || !track.url) {
        if (this.audio) {
          try { this.audio.stop() } catch (error) {}
          this.audio.src = ''
          this.audioSrc = ''
        }
        return
      }
      const audio = this.ensureAudio()
      this.loadSource(audio, ratio)
      if (resume) this.startPlayback(audio)
    },
    // Android 原生播放器刚设 src 时还在 prepare，立即 play() 会被丢弃；
    // 先调一次 play()，若 600ms 内没进入播放态再补一次，最多补 3 次。
    startPlayback(audio) {
      this.playError = ''
      clearTimeout(this.playRetryTimer)
      let tries = 0
      const attempt = () => {
        try { audio.play() } catch (error) {}
        tries += 1
        this.playRetryTimer = setTimeout(() => {
          if (!this.playing && audio.paused !== false && tries < 4) attempt()
        }, 600)
      }
      attempt()
    },
    togglePlay() {
      if (this.disabled) return
      const audio = this.ensureAudio()
      if (this.playing) { audio.pause(); return }
      // 上下文新建后（例如刚换过声音）src 可能还没设，播放前补一次。
      this.loadSource(audio, 0)
      this.startPlayback(audio)
    },
    goPrev() {
      if (!this.prevEnabled) return
      this.state = step(this.state, -1)
      this.applyTrack(false)
    },
    goNext() {
      if (!this.nextEnabled) return
      this.state = step(this.state, 1)
      this.applyTrack(false)
    },
    chooseVoice(voiceId) {
      const next = selectVoice(this.state, voiceId)
      if (next === this.state) return
      this.state = next
      uni.setStorageSync(VOICE_STORAGE_KEY, this.state.voice)
      this.applyTrack(true)
    },
    // picker 的 @change 给的是下拉序号，换成声音 id 再走 chooseVoice（同一套存储与续播逻辑）。
    onVoiceChange(event) {
      const index = Number((event.detail && event.detail.value) || 0)
      const voice = this.selectableVoices[index]
      if (voice) this.chooseVoice(voice.id)
    },
    onSeeking(event) {
      this.seeking = true
      const value = Number((event.detail && event.detail.value) || 0)
      this.sliderValue = value
      this.currentTime = ratioToSeconds(value / 1000, this.duration)
    },
    onSeek(event) {
      const value = Number((event.detail && event.detail.value) || 0)
      const seconds = ratioToSeconds(value / 1000, this.duration)
      this.sliderValue = value
      this.currentTime = seconds
      this.seeking = false
      if (!this.audio || this.disabled) return
      resetListenAnchor(this.listen)
      try { this.audio.seek(seconds) } catch (error) {}
    },
    announceListened(track) {
      this.$emit('listened', { articleId: track.articleId, title: track.title })
    },
    handleEnded() {
      const track = this.track
      if (track && finishListen(this.listen, track.articleId, this.duration)) this.announceListened(track)
      const result = afterEnded(this.state)
      if (!result.play) {
        this.playing = false
        return
      }
      this.state = result.state
      this.applyTrack(false)
      // 下一篇可能没有当前声音的音频，那就停在原地等用户自己选。
      if (hasTrack(this.state)) this.ensureAudio().play()
    },
    // 页面隐藏或卸载时暂停并销毁，避免后台出声和内存泄漏。
    stopAudio() {
      clearTimeout(this.playRetry)
      if (!this.audio) return
      try {
        this.audio.pause()
        this.audio.stop()
        this.audio.destroy()
      } catch (error) {}
      this.audio = null
      this.audioSrc = ''
      this.playing = false
    }
  }
}
</script>

<style scoped>
.today-audio {
  display: flex;
  flex-direction: column;
  gap: 26rpx;
  padding: 30rpx 32rpx 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.88);
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 24rpx 60rpx rgba(31, 47, 58, 0.1);
}

/* 顶行：小标题 + 篇数 */
.audio-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.audio-eyebrow {
  color: #1F5F7A;
  font-size: 22rpx;
  font-weight: 600;
  letter-spacing: 3rpx;
}

.audio-count {
  color: #6C7880;
  font-size: 22rpx;
  font-variant-numeric: tabular-nums;
}

.audio-position {
  color: #1F5F7A;
  font-weight: 600;
}

/* 标题 + 状态：单独一块，和上下行都拉开距离 */
.audio-title-block {
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  margin-top: 6rpx;
}

/* 每段 inline-block：换行只发生在标点处，词不会被劈开 */
.audio-title-chunk {
  display: inline-block;
}

.audio-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  color: #122231;
  font-size: 34rpx;
  font-weight: 600;
  line-height: 1.45;
  text-wrap: pretty;
}

.audio-status {
  color: #6C7880;
  font-size: 24rpx;
  line-height: 1.6;
  text-wrap: pretty;
}

/* 声音：左文字 + 右下拉 */
.audio-voice-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.audio-voice-label {
  flex: none;
  color: #6C7880;
  font-size: 24rpx;
  letter-spacing: 1rpx;
}

.audio-voice-picker {
  flex: 0 1 auto;
  min-width: 0;
  max-width: 62%;
}

/* 触发区做成下拉框的样子：浅底、圆角、内边距，右侧箭头 */
.audio-voice-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14rpx;
  min-width: 220rpx;
  min-height: 60rpx;
  padding: 0 20rpx;
  border-radius: 16rpx;
  background: rgba(31, 95, 122, 0.07);
  box-shadow: 0 0 0 1rpx rgba(31, 95, 122, 0.08), 0 6rpx 16rpx rgba(31, 47, 58, 0.05);
  transition: background 140ms ease, box-shadow 140ms ease;
}

.audio-voice-trigger.is-locked {
  background: rgba(108, 120, 128, 0.06);
  box-shadow: 0 0 0 1rpx rgba(108, 120, 128, 0.07);
}

.audio-voice-name {
  overflow: hidden;
  color: #1F5F7A;
  font-size: 25rpx;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.audio-voice-trigger.is-locked .audio-voice-name {
  color: #5C6C75;
  font-weight: 400;
}

.audio-caret {
  color: #7C8B95;
  font-size: 22rpx;
}

/* 控制行：三个按钮水平居中，间距明显 */
.audio-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 44rpx;
  margin-top: 8rpx;
}

.audio-skip {
  display: inline-flex;
  align-items: center;
  gap: 8rpx;
  margin: 0;
  padding: 0 22rpx;
  min-height: 64rpx;
  border: 0;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.08);
  color: #1F5F7A;
  font-size: 24rpx;
  line-height: 1;
}

.audio-skip::after {
  border: 0;
}

.audio-skip[disabled] {
  color: #A6B0B6;
  background: rgba(108, 120, 128, 0.06);
}

/* 图标统一光学对齐：相对文字下移 0.125em，由这个类统一控制 */
.audio-icon {
  position: relative;
  top: 0.125em;
  font-size: 28rpx;
  line-height: 1;
}

.audio-play {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 112rpx;
  height: 112rpx;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #F7FAF8;
  box-shadow: 0 16rpx 36rpx rgba(20, 62, 82, 0.24);
  transition: box-shadow 140ms ease, transform 140ms ease;
}

.audio-play::after {
  border: 0;
}

.audio-play.is-disabled {
  background: rgba(108, 120, 128, 0.18);
  box-shadow: none;
  color: #FFFFFF;
}

.audio-play-icon {
  font-size: 34rpx;
}

/* 进度条独占一行，时间在下方两端 */
.audio-progress {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  margin-top: 4rpx;
}

.audio-slider {
  width: 100%;
  margin: 0;
}

.audio-times {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4rpx;
}

.audio-time {
  color: #6C7880;
  font-size: 22rpx;
  font-variant-numeric: tabular-nums;
}

.is-dark.today-audio {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.86);
  box-shadow: 0 24rpx 60rpx rgba(0, 0, 0, 0.28);
}

.is-dark .audio-eyebrow,
.is-dark .audio-position {
  color: #7EB8D1;
}

.is-dark .audio-count,
.is-dark .audio-status,
.is-dark .audio-time,
.is-dark .audio-voice-label {
  color: #B6C2CC;
  font-weight: 240;
}

.is-dark .audio-title {
  color: #F4F7FA;
  font-weight: 360;
}

/* 分段是 text 子元素：暗色下显式给同色同字重，避免个别端不继承 */
.is-dark .audio-title-chunk {
  color: #F4F7FA;
  font-weight: 360;
}

.is-dark .audio-eyebrow,
.is-dark .audio-position {
  font-weight: 360;
}

/* 暗色下拉：靠明度差分层，不用边框 */
.is-dark .audio-voice-trigger {
  background: rgba(126, 184, 209, 0.1);
  box-shadow: 0 0 0 1rpx rgba(126, 184, 209, 0.14), 0 6rpx 16rpx rgba(0, 0, 0, 0.18);
}

.is-dark .audio-voice-trigger.is-locked {
  background: rgba(126, 184, 209, 0.05);
  box-shadow: 0 0 0 1rpx rgba(126, 184, 209, 0.08);
}

.is-dark .audio-voice-name {
  color: #E4EFF5;
  font-weight: 360;
}

.is-dark .audio-voice-trigger.is-locked .audio-voice-name {
  color: #8B9AA4;
  font-weight: 240;
}

.is-dark .audio-caret {
  color: #8B9AA4;
}

.is-dark .audio-skip {
  background: rgba(126, 184, 209, 0.1);
  color: #B6C2CC;
  font-weight: 240;
}

.is-dark .audio-skip[disabled] {
  background: rgba(126, 184, 209, 0.05);
  color: #6F7C85;
}

.is-dark .audio-play {
  background: linear-gradient(135deg, rgba(126, 184, 209, 0.9), rgba(31, 95, 122, 0.94));
  color: #101820;
}

.is-dark .audio-play.is-disabled {
  background: rgba(126, 184, 209, 0.12);
  color: #7C8B95;
}
</style>
