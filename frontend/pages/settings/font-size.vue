<template>
  <view :class="['page settings-page font-size-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="settings-head">
      <view class="head-copy">
        <text class="head-kicker">阅读舒适度</text>
        <text class="page-title">字号</text>
        <text class="subtle">选择适合你阅读的文字大小，正文预览会同步变化。</text>
      </view>
      <view class="reading-icon">
        <text class="reading-icon-line reading-icon-line-large">Aa</text>
        <text class="reading-icon-line">阅读</text>
      </view>
    </view>

    <view class="option-list">
      <button v-for="option in options" :key="option.value" :class="['font-option', fontSize === option.value ? 'selected' : '']" @click="selectFontSize(option.value)">
        <view class="option-copy">
          <view class="option-head">
            <text class="option-title">{{ option.label }}</text>
            <text class="option-meta">{{ option.meta }}</text>
          </view>
          <text class="option-desc">{{ option.desc }}</text>
          <text :class="['option-preview', `sample-${option.value}`]">政策摘录会以这种字号呈现，阅读节奏更清晰。</text>
        </view>
        <view class="option-check">
          <text v-if="fontSize === option.value" class="check-mark">✓</text>
        </view>
      </button>
    </view>

    <view :class="['preview-card', 'card', `preview-${fontSize}`]">
      <view class="preview-topline">
        <text class="preview-kicker">政策摘录</text>
        <text class="preview-status">{{ currentOption.label }}</text>
      </view>
      <text class="preview-title">政策不是结论，而是判断的起点</text>
      <text class="preview-body">见闻会把公开来源、关键变化和与你有关的部分放在一起，帮助你先理解，再决定要不要继续深入查看。</text>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      darkMode: false,
      fontSize: 'standard',
      options: [
        { value: 'small', label: '小字', meta: '紧凑', desc: '适合快速浏览，单屏可容纳更多内容' },
        { value: 'standard', label: '标准', meta: '推荐', desc: '正文大小均衡，适合多数日常阅读' },
        { value: 'large', label: '大字', meta: '舒适', desc: '进一步放大正文，适合长文和弱光环境' }
      ]
    }
  },
  computed: {
    currentOption() {
      return this.options.find(option => option.value === this.fontSize) || this.options[1]
    }
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
  },
  methods: {
    selectFontSize(value) {
      this.fontSize = value
      uni.setStorageSync('jianwen_font_size', value)
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
        return
      }
      uni.switchTab({ url: '/pages/profile/profile' })
    }
  }
}
</script>

<style scoped>
.settings-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 56rpx;
  margin-bottom: 30rpx;
}

.settings-head,
.preview-card,
.head-copy,
.option-copy {
  display: flex;
  flex-direction: column;
}

.settings-head {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 30rpx;
  margin-bottom: 38rpx;
}

.head-copy {
  flex: 1;
  gap: 14rpx;
  min-width: 0;
}

.head-kicker {
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1.3;
  font-weight: 900;
}

.reading-icon {
  position: relative;
  z-index: 1;
  flex: 0 0 124rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 124rpx;
  height: 124rpx;
  border: 1rpx solid rgba(31, 95, 122, 0.14);
  border-radius: 28rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.86), rgba(230, 240, 244, 0.72)),
    rgba(255, 255, 255, 0.78);
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.9), 0 16rpx 36rpx rgba(31, 95, 122, 0.12);
}

.reading-icon-line {
  color: #5C6873;
  font-size: 20rpx;
  line-height: 1.2;
  font-weight: 800;
}

.reading-icon-line-large {
  margin-bottom: 8rpx;
  color: #1F5F7A;
  font-size: 36rpx;
  font-weight: 900;
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 22rpx;
}

.font-option {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 28rpx;
  width: 100%;
  min-height: 188rpx;
  padding: 32rpx 34rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.88);
  border-radius: 28rpx;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 20rpx 52rpx rgba(31, 47, 58, 0.09);
  text-align: left;
  transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
}

.option-copy {
  flex: 1;
  gap: 12rpx;
  min-width: 0;
}

.option-head {
  display: flex;
  align-items: center;
  gap: 16rpx;
  min-width: 0;
}

.option-title {
  color: #14212B;
  font-size: 31rpx;
  line-height: 1.25;
  font-weight: 900;
}

.option-meta {
  display: inline-flex;
  align-items: center;
  min-height: 38rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.15);
  color: #8A6C28;
  font-size: 20rpx;
  line-height: 1;
  font-weight: 900;
}

.option-desc {
  color: #5C6873;
  font-size: 24rpx;
  line-height: 1.5;
}

.option-preview {
  color: #253A46;
  line-height: 1.58;
  font-weight: 700;
}

.sample-small {
  font-size: 25rpx;
}

.sample-standard {
  font-size: 29rpx;
}

.sample-large {
  font-size: 34rpx;
  line-height: 1.5;
}

.option-check {
  flex: 0 0 46rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46rpx;
  height: 46rpx;
  border: 2rpx solid rgba(31, 95, 122, 0.2);
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.76);
}

.check-mark {
  color: #FFFFFF;
  font-size: 26rpx;
  line-height: 1;
  font-weight: 900;
}

.font-option.selected {
  border-color: #1F5F7A;
  background:
    linear-gradient(135deg, rgba(230, 240, 244, 0.96), rgba(255, 255, 255, 0.82)),
    #E6F0F4;
  box-shadow: 0 24rpx 58rpx rgba(31, 95, 122, 0.16);
}

.font-option.selected .option-check {
  border-color: #1F5F7A;
  background: #1F5F7A;
}

.preview-card {
  gap: 22rpx;
  margin-top: 42rpx;
  padding: 38rpx;
}

.preview-topline {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
}

.preview-kicker {
  color: #1F5F7A;
  font-size: 23rpx;
  line-height: 1.3;
  font-weight: 900;
}

.preview-status {
  min-height: 40rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.1);
  color: #1F5F7A;
  font-size: 21rpx;
  line-height: 40rpx;
  font-weight: 900;
}

.preview-title {
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.35;
  font-weight: 900;
}

.preview-body {
  color: #3F4F59;
  font-size: 28rpx;
  line-height: 1.75;
}

.preview-small .preview-title {
  font-size: 30rpx;
}

.preview-small .preview-body {
  font-size: 25rpx;
  line-height: 1.72;
}

.preview-standard .preview-title {
  font-size: 34rpx;
}

.preview-standard .preview-body {
  font-size: 29rpx;
  line-height: 1.78;
}

.preview-large .preview-title {
  font-size: 38rpx;
}

.preview-large .preview-body {
  font-size: 34rpx;
  line-height: 1.82;
}

.font-large .option-desc {
  font-size: 26rpx;
}

.font-large .option-title {
  font-size: 34rpx;
}

.font-small .option-title {
  font-size: 28rpx;
}

.font-small .option-desc {
  font-size: 22rpx;
}

.dark-mode .head-kicker,
.dark-mode .reading-icon-line-large,
.dark-mode .preview-kicker,
.dark-mode .preview-status {
  color: #7EB8D1;
}

.dark-mode .reading-icon {
  border-color: rgba(126, 184, 209, 0.16);
  background:
    linear-gradient(145deg, rgba(23, 35, 49, 0.86), rgba(17, 27, 39, 0.78)),
    #172331;
  box-shadow: inset 0 1rpx 0 rgba(255, 255, 255, 0.06), 0 18rpx 42rpx rgba(0, 0, 0, 0.22);
}

.dark-mode .reading-icon-line,
.dark-mode .option-desc {
  color: #9AAAB4;
}

.dark-mode .font-option {
  border-color: rgba(126, 184, 209, 0.16);
  background: rgba(23, 35, 49, 0.86);
  box-shadow: 0 24rpx 60rpx rgba(0, 0, 0, 0.22);
}

.dark-mode .font-option.selected {
  border-color: #7EB8D1;
  background:
    linear-gradient(135deg, rgba(32, 56, 74, 0.96), rgba(23, 35, 49, 0.86)),
    #20384A;
}

.dark-mode .option-title,
.dark-mode .option-preview,
.dark-mode .preview-title {
  color: #F4F7FA;
}

.dark-mode .option-meta {
  background: rgba(212, 170, 78, 0.16);
  color: #D8B96A;
}

.dark-mode .option-check {
  border-color: rgba(126, 184, 209, 0.28);
  background: rgba(17, 27, 39, 0.72);
}

.dark-mode .font-option.selected .option-check {
  border-color: #7EB8D1;
  background: #7EB8D1;
}

.dark-mode .check-mark {
  color: #0E1720;
}

.dark-mode .preview-status {
  background: rgba(126, 184, 209, 0.13);
}

.dark-mode .preview-body {
  color: #C9D5DD;
}
</style>
