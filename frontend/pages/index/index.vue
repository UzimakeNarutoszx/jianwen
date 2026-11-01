<template>
  <view :class="['page redirect-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="ambient-glow glow-gold"></view>
    <view class="ambient-glow glow-blue"></view>
    <view class="brand-panel">
      <view class="brand-icon-wrap">
        <image class="brand-icon" src="/static/brand-icon.png" mode="aspectFit" />
      </view>
      <text class="brand-title">见闻</text>
      <text class="subtle loading-copy">正在整理今日简报</text>
      <view class="loading-row">
        <view class="loading-ring"></view>
        <view class="loading-dots">
          <text class="loading-dot dot-a"></text>
          <text class="loading-dot dot-b"></text>
          <text class="loading-dot dot-c"></text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      darkMode: false,
      fontSize: 'standard'
    }
  },
  onLoad() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    uni.switchTab({
      url: '/pages/today/today'
    })
  }
}
</script>

<style scoped>
.redirect-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 0%, rgba(214, 184, 112, 0.32) 0, rgba(214, 184, 112, 0) 300rpx),
    radial-gradient(circle at 84% 18%, rgba(31, 95, 122, 0.2) 0, rgba(31, 95, 122, 0) 340rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 460rpx, #F5F7F4 100%);
}

.ambient-glow {
  position: absolute;
  border-radius: 999rpx;
  pointer-events: none;
}

.glow-gold {
  top: 18%;
  right: -90rpx;
  width: 280rpx;
  height: 280rpx;
  background: rgba(212, 170, 78, 0.18);
}

.glow-blue {
  left: -110rpx;
  bottom: 20%;
  width: 320rpx;
  height: 320rpx;
  background: rgba(31, 95, 122, 0.13);
}

.brand-panel {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 520rpx;
  max-width: 100%;
  padding: 70rpx 52rpx 62rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.86);
  border-radius: 32rpx;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.54)),
    linear-gradient(135deg, rgba(245, 235, 207, 0.74), rgba(226, 240, 244, 0.64));
  box-shadow: 0 28rpx 76rpx rgba(48, 65, 72, 0.13);
}

.brand-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 126rpx;
  height: 126rpx;
  margin-bottom: 30rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.82);
  border-radius: 32rpx;
  background: rgba(255, 255, 255, 0.76);
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.15);
}

.brand-icon {
  width: 68rpx;
  height: 68rpx;
}

.brand-title {
  color: #101D28;
  font-size: 56rpx;
  line-height: 1.12;
  font-weight: 900;
}

.loading-copy {
  margin-top: 18rpx;
  color: #5E6E78;
  font-size: 26rpx;
  line-height: 1.45;
  text-align: center;
}

.loading-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  margin-top: 40rpx;
  min-height: 42rpx;
}

.loading-ring {
  width: 34rpx;
  height: 34rpx;
  border: 4rpx solid rgba(31, 95, 122, 0.14);
  border-top-color: #1F5F7A;
  border-right-color: rgba(212, 170, 78, 0.72);
  border-radius: 999rpx;
  animation: loading-spin 1.1s linear infinite;
}

.loading-dots {
  display: flex;
  align-items: center;
  gap: 10rpx;
}

.loading-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
  opacity: 0.34;
  animation: loading-pulse 1.2s ease-in-out infinite;
}

.dot-b {
  animation-delay: 0.16s;
}

.dot-c {
  animation-delay: 0.32s;
}

.font-large .brand-title {
  font-size: 62rpx;
}

.font-large .loading-copy {
  font-size: 30rpx;
}

.font-small .brand-title {
  font-size: 50rpx;
}

.font-small .loading-copy {
  font-size: 24rpx;
}

.dark-mode.redirect-page {
  background:
    radial-gradient(circle at 18% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 300rpx),
    radial-gradient(circle at 84% 18%, rgba(75, 154, 187, 0.18) 0, rgba(75, 154, 187, 0) 340rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .glow-gold {
  background: rgba(212, 170, 78, 0.11);
}

.dark-mode .glow-blue {
  background: rgba(126, 184, 209, 0.1);
}

.dark-mode .brand-panel {
  border-color: rgba(126, 184, 209, 0.14);
  background:
    linear-gradient(135deg, rgba(23, 35, 49, 0.92), rgba(17, 27, 39, 0.76)),
    linear-gradient(135deg, rgba(126, 184, 209, 0.12), rgba(187, 141, 45, 0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .brand-icon-wrap {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.86);
  box-shadow: 0 18rpx 42rpx rgba(0, 0, 0, 0.26);
}

.dark-mode .brand-title {
  color: #F4F7FA !important;
}

.dark-mode .loading-copy {
  color: #B6C2CC !important;
}

.dark-mode .loading-ring {
  border-color: rgba(126, 184, 209, 0.16);
  border-top-color: #7EB8D1;
  border-right-color: rgba(212, 170, 78, 0.6);
}

.dark-mode .loading-dot {
  background: #D4AA4E;
}

@keyframes loading-spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

@keyframes loading-pulse {
  0%,
  80%,
  100% {
    opacity: 0.34;
    transform: scale(0.82);
  }

  40% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>
