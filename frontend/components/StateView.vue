<template>
  <view :class="['state-view', `state-${state}`, darkMode ? 'dark-mode' : '']" role="status" aria-live="polite">
    <view v-if="state === 'loading'" class="state-loader" aria-hidden="true">
      <text class="state-dot"></text>
      <text class="state-dot"></text>
      <text class="state-dot"></text>
    </view>
    <view v-else :class="['state-mark', `mark-${state}`]" aria-hidden="true">
      <text class="state-mark-symbol">{{ state === 'error' ? '!' : '·' }}</text>
    </view>

    <text class="state-title">{{ state === 'error' ? '内容暂时未能加载' : (message || DEFAULT_TITLE[state]) }}</text>
    <text v-if="state === 'error'" class="state-description">{{ errorDescription }}</text>

    <button v-if="state === 'error'" class="state-retry" @click="$emit('retry')">
      <text class="state-retry-text">重新加载</text>
    </button>
  </view>
</template>

<script>
// 三态占位：loading / empty / error，调用方只负责传状态和文案。
const DEFAULT_TITLE = {
  loading: '正在加载',
  empty: '暂时没有内容',
  error: '加载失败'
}

export default {
  name: 'StateView',
  props: {
    state: {
      type: String,
      default: 'loading',
      validator: value => ['loading', 'empty', 'error'].indexOf(value) !== -1
    },
    message: { type: String, default: '' },
    darkMode: { type: Boolean, default: false }
  },
  emits: ['retry'],
  data() {
    return { DEFAULT_TITLE }
  },
  computed: {
    errorDescription() {
      const message = this.message || ''
      return !message || /request:|fetch|network|https?:|failed|error/i.test(message)
        ? '请检查网络连接，再试一次。'
        : message
    }
  }
}
</script>

<style scoped>
.state-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16rpx;
  padding: 40rpx 32rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.86);
  border-radius: 28rpx;
  background: var(--jw-surface-card);
  box-shadow: 0 8rpx 24rpx rgba(31, 47, 58, 0.04);
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.state-loader {
  display: flex;
  align-items: center;
  gap: 12rpx;
  height: 34rpx;
}

.state-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: var(--jw-blue);
  opacity: 0.35;
  animation: state-pulse 1.05s ease-in-out infinite;
}

.state-dot:nth-child(2) { animation-delay: 0.15s; }
.state-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes state-pulse {
  0%, 100% { opacity: 0.28; transform: scale(0.86); }
  50% { opacity: 0.95; transform: scale(1); }
}

.state-mark {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 68rpx;
  height: 68rpx;
  border-radius: 22rpx;
  background: var(--jw-mist);
  color: var(--jw-muted);
}

.mark-error {
  background: rgba(182, 93, 82, 0.12);
  color: #a8544a;
}

.state-mark-symbol {
  font-size: 34rpx;
  line-height: 1;
  font-weight: 600;
}

.state-title {
  color: var(--jw-ink);
  font-size: 30rpx;
  line-height: 1.4;
  font-weight: 600;
  text-wrap: balance;
}

.state-description {
  max-width: 100%;
  color: var(--jw-muted);
  font-size: 25rpx;
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.state-retry {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 76rpx;
  margin: 8rpx 0 0;
  padding: 0 32rpx;
  border-radius: 999rpx;
  background: rgba(40, 100, 94, 0.1);
  color: var(--jw-blue);
}

.state-retry::after {
  border: 0;
}

.state-retry:active {
  opacity: 0.9;
}

.state-retry:focus-visible {
  outline: 0;
  box-shadow: 0 0 0 2rpx var(--jw-focus-strong), 0 0 0 8rpx var(--jw-focus-halo);
}

.state-retry-text {
  font-size: 27rpx;
  line-height: 1.4;
  font-weight: 600;
}

.dark-mode.state-view {
  border-color: rgba(126, 184, 209, 0.14);
  box-shadow: 0 18rpx 44rpx rgba(0, 0, 0, 0.2);
}

.dark-mode .state-title {
  color: #eef4f6;
  font-weight: 360;
}

.dark-mode .state-mark {
  background: rgba(126, 184, 209, 0.12);
  color: #9fbccb;
}

.dark-mode .mark-error {
  background: rgba(196, 116, 104, 0.16);
  color: #dba79f;
}

.dark-mode .state-retry {
  background: rgba(126, 184, 209, 0.14);
  color: #9fd0e2;
}

.dark-mode .state-retry-text {
  font-weight: 360;
}

@media (prefers-reduced-motion: reduce) {
  .state-dot {
    animation: none;
    opacity: 0.6;
  }
}
</style>
