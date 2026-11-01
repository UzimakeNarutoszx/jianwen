<template>
  <view :class="['composer-shell', darkMode ? 'is-dark' : '']">
    <text class="quota-label">{{ quotaLabel }}</text>
    <view class="composer">
    <button class="tool-button" aria-label="更多功能" @click="$emit('tool')">
      <image class="tool-icon" src="/static/icons/icon-add.png" mode="aspectFit" />
    </button>
    <input
      class="composer-input"
      :value="modelValue"
      placeholder="问点什么"
      confirm-type="send"
      @input="onInput"
      @confirm="$emit('send')"
    />
    <button class="send-button" :disabled="sending" @click="$emit('send')">
      <image class="send-icon" src="/static/icons/icon-send.png" mode="aspectFit" />
      <text class="send-text">发送</text>
    </button>
    </view>
  </view>
</template>

<script>
export default {
  name: 'AskComposer',
  props: {
    modelValue: { type: String, default: '' },
    sending: { type: Boolean, default: false },
    darkMode: { type: Boolean, default: false },
    quotaLabel: { type: String, default: '今日额度已耗尽 0/20' }
  },
  emits: ['update:modelValue', 'send', 'tool'],
  methods: {
    onInput(event) {
      this.$emit('update:modelValue', event.detail.value)
    }
  }
}
</script>

<style scoped>
.composer {
  position: fixed;
  left: 22rpx;
  right: 22rpx;
  bottom: calc(124rpx + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  gap: 16rpx;
  padding: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.86);
  border-radius: 34rpx;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 -14rpx 44rpx rgba(20, 33, 43, 0.12);
}

.composer-shell { position: fixed; left: 22rpx; right: 22rpx; bottom: calc(124rpx + env(safe-area-inset-bottom)); z-index: 5; }
/* #ifdef APP-PLUS */
.composer-shell { bottom: 12rpx; }
/* #endif */
.quota-label { display: block; margin: 0 18rpx 10rpx; color: #1f5f7a; font-size: 22rpx; line-height: 1.2; font-variant-numeric: tabular-nums; }
.composer-shell .composer { position: relative; left: auto; right: auto; bottom: auto; }
.composer-shell.is-dark .quota-label { color: #9fc7d8; }

.tool-button,
.send-button {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.tool-button {
  flex: 0 0 76rpx;
  flex-basis: 76rpx;
  height: 76rpx;
  border-radius: 24rpx;
  background: rgba(31, 95, 122, 0.1);
}

/* 76rpx 视觉尺寸不变，透明命中区补到 108rpx。 */
.tool-button::before,
.send-button::before {
  content: '';
  position: absolute;
  top: -16rpx;
  right: -16rpx;
  bottom: -16rpx;
  left: -16rpx;
}

.tool-icon {
  width: 30rpx;
  height: 30rpx;
}

.composer-input {
  flex: 1;
  min-height: 76rpx;
  padding: 0 24rpx;
  border: 1rpx solid rgba(31, 95, 122, 0.12);
  border-radius: 24rpx;
  background: rgba(247, 250, 252, 0.92);
  color: #14212b;
  font-size: 26rpx;
}

.send-button {
  flex: 0 0 128rpx;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 8rpx;
  width: 128rpx;
  min-height: 76rpx;
  border-radius: 24rpx;
  background: linear-gradient(135deg, #1f5f7a, #143e52);
  color: #ffffff;
  white-space: nowrap;
}

.send-button[disabled] {
  opacity: 0.6;
}

.send-button::after,
.tool-button::after {
  border: 0;
}

.tool-button:active,
.send-button:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.send-icon {
  flex: 0 0 30rpx;
  width: 30rpx;
  height: 30rpx;
}

.send-text {
  flex: 0 0 auto;
  color: #ffffff;
  font-size: 24rpx;
  line-height: 1;
  font-weight: 900;
  white-space: nowrap;
}

:is(.composer-input):focus,
:is(.composer-input):focus-visible {
  outline: 0;
  border-color: transparent;
  box-shadow: 0 0 0 2rpx var(--jw-focus), 0 0 0 8rpx var(--jw-focus-halo);
  transition: background-color 0.14s ease;
}

/* 暗色走局部变量换值，避免整段 !important。 */
.composer.is-dark {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.94);
  box-shadow: 0 -14rpx 44rpx rgba(0, 0, 0, 0.28);
}

.composer.is-dark .tool-button {
  background: rgba(126, 184, 209, 0.12);
}

.composer.is-dark .composer-input {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.86);
  color: #eef4f6;
}

.composer.is-dark .send-button {
  background: linear-gradient(135deg, rgba(31, 95, 122, 0.9), rgba(16, 39, 55, 0.94));
}

.composer.is-dark .send-text {
  font-weight: 360;
}
</style>
