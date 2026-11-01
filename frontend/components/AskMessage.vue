<template>
  <view :id="`message-${message.id}`" :class="['message', message.role, `font-${fontSize}`, { 'is-dark': darkMode }]">
    <view class="message-meta">
      <view class="message-avatar">
        <image
          v-if="message.role === 'assistant'"
          class="message-avatar-icon"
          src="/static/icons/tab-ask-active.png"
          mode="aspectFit"
        />
        <text v-else>{{ message.role === 'user' ? '你' : '文' }}</text>
      </view>
      <text class="message-label">{{ label }}</text>
    </view>

    <view class="message-bubble">
      <template v-if="message.role === 'assistant'">
        <!-- 已完成块：HTML 缓存，只在块内容变化时重算 -->
        <rich-text v-if="message.renderBlocks" class="message-text markdown-message" :nodes="message.renderBlocks" />
        <!-- 正在增长的块：H5 逐字渐显，其余端直接渲染 -->
        <view v-if="liveBlock" class="message-text markdown-message live-block">
          <template v-if="charReveal">
            <text
              v-for="(item, index) in liveChars"
              :key="index"
              class="reveal-char"
              :style="{ animationDelay: item.delay + 'ms' }"
            >{{ item.char }}</text>
          </template>
          <rich-text v-else :nodes="liveHtml" />
        </view>
        <rich-text
          v-else-if="!message.renderBlocks && message.text"
          class="message-text markdown-message"
          :nodes="fullHtml"
        />
      </template>
      <text v-else class="message-text">{{ message.text }}</text>

      <view v-if="message.role === 'assistant' && message.thinkingLabel" class="thinking-bar">
        <text class="thinking-pulse"></text>
        <text class="message-thinking">{{ message.thinkingLabel }}</text>
      </view>

      <view v-if="message.sources && showSources" class="message-source">
        <view class="source-head">
          <image class="source-icon" src="/static/icons/icon-search.png" mode="aspectFit" />
          <text>来源入口</text>
        </view>
        <text class="source-text">{{ message.sources }}</text>
      </view>
    </view>

    <button v-if="canCopy" class="copy-button" :aria-label="copied ? '已复制' : '复制回答'" @click="copyAnswer">
      <text :class="['copy-mark', copied ? 'is-copied' : '']">{{ copied ? '已复制' : '复制' }}</text>
    </button>
  </view>
</template>

<script>
import { markdownToHtml } from '@/utils/markdown.js'

// rich-text 无法逐字加动画；仅 H5 用纯文本 span 渲染增长块。
// #ifdef H5
const CHAR_REVEAL = true
// #endif
// #ifndef H5
const CHAR_REVEAL = false
// #endif

const COPY_RESET_MS = 2500

export default {
  name: 'AskMessage',
  props: {
    message: { type: Object, required: true },
    showSources: { type: Boolean, default: true },
    darkMode: { type: Boolean, default: false },
    fontSize: { type: String, default: 'standard' }
  },
  data() {
    return {
      charReveal: CHAR_REVEAL,
      copied: false,
      copyTimer: null,
      charDelays: [],
      lastTail: ''
    }
  },
  computed: {
    label() {
      if (this.message.role === 'user') return '你'
      if (this.message.role === 'context') return '文章上下文'
      return '见闻助理'
    },
    liveBlock() {
      if (this.message.role !== 'assistant' || !this.message.streaming) return ''
      return String(this.message.liveBlock || '')
    },
    liveHtml() {
      return markdownToHtml(this.liveBlock)
    },
    liveChars() {
      const chars = Array.from(this.liveBlock)
      return chars.map((char, index) => ({ char, delay: this.charDelays[index] || 0 }))
    },
    fullHtml() {
      return markdownToHtml(this.message.text || '')
    },
    canCopy() {
      if (this.message.role !== 'assistant') return false
      // 流式输出和「正在思考…」占位阶段不提供复制。
      if (this.message.streaming) return false
      const text = String(this.message.text || '').trim()
      return !!text && text !== '正在思考…'
    }
  },
  watch: {
    liveBlock: {
      immediate: true,
      handler(value) {
        const chars = Array.from(String(value || ''))
        const previous = Array.from(this.lastTail)
        const grew = chars.length >= previous.length && previous.every((char, index) => chars[index] === char)
        const base = grew ? previous.length : 0
        const delays = this.charDelays.slice(0, base)
        // 与网页 webpage/js/ask.js 一致：批内序号 --i 上限 5，延迟 = --i × 30ms。
        for (let index = base; index < chars.length; index++) {
          delays.push(Math.min(index - base, 5) * 30)
        }
        this.charDelays = delays
        this.lastTail = chars.join('')
      }
    }
  },
  beforeUnmount() {
    this.clearCopyTimer()
  },
  methods: {
    clearCopyTimer() {
      if (this.copyTimer) {
        clearTimeout(this.copyTimer)
        this.copyTimer = null
      }
    },
    copyAnswer() {
      const data = String(this.message.text || '').trim()
      if (!data) return
      // 重复点击先清旧定时器再重计时，始终只有一个定时器。
      this.clearCopyTimer()
      uni.setClipboardData({
        data,
        success: () => {
          this.copied = true
          this.copyTimer = setTimeout(() => {
            this.copyTimer = null
            this.copied = false
          }, COPY_RESET_MS)
        },
        fail: () => {
          this.copied = false
          uni.showToast({ title: '复制失败，请长按选择文本', icon: 'none' })
        }
      })
    }
  }
}
</script>

<style scoped>
.message {
  --msg-text: #14212b;
  --msg-muted: #7c8790;
  --msg-border: rgba(31, 95, 122, 0.1);
  --msg-bubble: rgba(255, 255, 255, 0.82);
  --msg-assistant-bubble: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(247, 250, 252, 0.86)), rgba(255, 255, 255, 0.86);
  --msg-user-bubble: linear-gradient(135deg, #1f5f7a, #143e52);
  --msg-context-bubble: rgba(212, 170, 78, 0.1);
  --msg-context-border: rgba(212, 170, 78, 0.2);
  --msg-context-text: #725516;
  --msg-avatar-bg: rgba(31, 95, 122, 0.1);
  --msg-avatar-text: #1f5f7a;
  --msg-thinking-bg: rgba(31, 95, 122, 0.08);
  --msg-source-head: #1f5f7a;
  --msg-weight: 400;
  --msg-strong-weight: 900;
  display: flex;
  width: 100%;
  max-width: 100%;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 36rpx;
}

.message:last-child {
  margin-bottom: 0;
}

.message.user {
  align-items: flex-end;
}

.message.context {
  align-items: stretch;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.message.user .message-meta {
  flex-direction: row-reverse;
}

.message.context .message-meta {
  display: none;
}

.message-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46rpx;
  height: 46rpx;
  border-radius: 16rpx;
  background: var(--msg-avatar-bg);
  color: var(--msg-avatar-text);
  font-size: 22rpx;
  line-height: 1;
  font-weight: var(--msg-strong-weight);
}

.message.user .message-avatar {
  background: #1f5f7a;
  color: #ffffff;
}

.message-avatar-icon {
  width: 28rpx;
  height: 28rpx;
}

.message-label {
  margin: 0;
  color: var(--msg-muted);
  font-size: 22rpx;
  font-weight: var(--msg-weight);
}

.message-bubble {
  max-width: 92%;
  padding: 30rpx 32rpx;
  border: 1rpx solid var(--msg-border);
  border-radius: 26rpx;
  background: var(--msg-bubble);
  box-shadow: 0 18rpx 42rpx rgba(20, 33, 43, 0.07);
}

.message.assistant .message-bubble {
  width: 100%;
  max-width: 100%;
  border-bottom-left-radius: 10rpx;
  background: var(--msg-assistant-bubble);
}

.message.user .message-bubble {
  border-color: var(--msg-border);
  border-bottom-right-radius: 10rpx;
  background: var(--msg-user-bubble);
}

.message.context .message-bubble {
  max-width: 100%;
  border-color: var(--msg-context-border);
  border-radius: 20rpx;
  background: var(--msg-context-bubble);
  box-shadow: none;
}

.message-text {
  display: block;
  padding: 0;
  margin: 0;
  border-radius: 0;
  background: transparent;
  color: var(--msg-text);
  font-size: 29rpx;
  line-height: 1.7;
  font-weight: var(--msg-weight);
}

.message.assistant .message-text {
  width: 100%;
  text-align: left;
}

.message.user .message-text {
  background: transparent;
  color: #ffffff;
}

.message.context .message-text {
  border: 0;
  background: transparent;
  color: var(--msg-context-text);
  font-size: 25rpx;
}

.markdown-message {
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.live-block {
  white-space: pre-wrap;
}

/* 逐字渐显：单字 120ms，批内错开 30ms；延迟由脚本按新增字符计算。 */
.reveal-char {
  animation: char-reveal 120ms ease-out both;
}

/* 与网页 css/ask.css 的 stream-in 一致：从 blur(6px)、完全透明渐显到清晰。 */
@keyframes char-reveal {
  from {
    filter: blur(6px);
    opacity: 0;
  }
  to {
    filter: blur(0);
    opacity: 1;
  }
}

.thinking-bar {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-height: 52rpx;
  padding: 0 18rpx;
  margin-top: 22rpx;
  border-radius: 999rpx;
  background: var(--msg-thinking-bg);
}

.thinking-pulse {
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: #d4aa4e;
  box-shadow: 0 0 18rpx rgba(212, 170, 78, 0.62);
}

.message-thinking {
  margin: 0;
  color: var(--msg-muted);
  font-size: 22rpx;
  font-weight: var(--msg-weight);
}

.message-source {
  margin-top: 24rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid var(--msg-border);
}

.source-head {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 10rpx;
  color: var(--msg-source-head);
  font-size: 22rpx;
  line-height: 1.3;
  font-weight: var(--msg-strong-weight);
}

.source-icon {
  width: 24rpx;
  height: 24rpx;
}

.source-text {
  display: block;
  color: var(--msg-muted);
  font-size: 23rpx;
  line-height: 1.5;
  font-weight: var(--msg-weight);
}

.copy-button {
  position: relative;
  align-self: flex-start;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 88rpx;
  margin: 0;
  padding: 0 8rpx;
  background: transparent;
  color: var(--msg-muted);
}

.copy-button::after {
  border: 0;
}

.copy-button:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 2rpx rgba(40, 100, 94, 0.2), 0 0 0 8rpx rgba(40, 100, 94, 0.08);
}

.copy-mark {
  font-size: 22rpx;
  line-height: 1.4;
  font-weight: var(--msg-weight);
  font-variant-numeric: tabular-nums;
}

.copy-mark.is-copied {
  color: #4b8f7f;
}

/* 暗色：同一套变量换值，不用 !important 覆盖。 */
.message.is-dark {
  --msg-text: #eef4f6;
  --msg-muted: #b6c2cc;
  --msg-border: rgba(126, 184, 209, 0.16);
  --msg-bubble: rgba(23, 35, 49, 0.86);
  --msg-assistant-bubble: rgba(23, 35, 49, 0.86);
  --msg-user-bubble: linear-gradient(135deg, rgba(31, 95, 122, 0.9), rgba(16, 39, 55, 0.94));
  --msg-context-bubble: rgba(212, 170, 78, 0.12);
  --msg-context-border: rgba(212, 170, 78, 0.24);
  --msg-context-text: #d4aa4e;
  --msg-avatar-bg: rgba(126, 184, 209, 0.12);
  --msg-avatar-text: #9fd0e2;
  --msg-thinking-bg: rgba(126, 184, 209, 0.12);
  --msg-source-head: #7eb8d1;
  --msg-weight: 240;
  --msg-strong-weight: 360;
}

.message.is-dark .message-bubble {
  box-shadow: 0 18rpx 42rpx rgba(0, 0, 0, 0.2);
}

.message.is-dark .copy-mark.is-copied {
  color: #8fd0bb;
}

.font-large .message-text {
  font-size: 32rpx;
}

.font-small .message-text {
  font-size: 27rpx;
}

@media (prefers-reduced-motion: reduce) {
  .reveal-char {
    animation: none;
    filter: none;
    opacity: 1;
  }
}
</style>
