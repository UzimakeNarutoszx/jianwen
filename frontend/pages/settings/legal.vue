<template>
  <view :class="['page settings-page legal-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="settings-head legal-head">
      <view class="head-main">
        <view class="document-mark">
          <view class="document-fold"></view>
          <view class="document-line long"></view>
          <view class="document-line"></view>
        </view>
        <view class="head-copy">
          <text class="head-kicker">合规文档</text>
          <text class="page-title">{{ page.title }}</text>
          <text class="subtle">{{ page.subtitle || '平台规则、数据保存和内容边界说明' }}</text>
        </view>
      </view>

      <view class="meta-strip">
        <view class="meta-item">
          <text class="meta-label">最后更新</text>
          <text class="meta-value">{{ page.updated_label || updatedText }}</text>
        </view>
        <view class="meta-divider"></view>
        <view class="meta-item">
          <text class="meta-label">适用范围</text>
          <text class="meta-value">见闻 App 与相关服务</text>
        </view>
      </view>
    </view>

    <view v-for="(section, index) in page.sections" :key="section.title" class="content-card legal-section card">
      <view class="section-head">
        <text class="section-index">{{ index + 1 }}</text>
        <text class="content-title">{{ section.title }}</text>
      </view>
      <text class="content-body">{{ section.body }}</text>
    </view>
  </view>
</template>

<script>
import { getContentPage } from '@/utils/api.js'
import { formatDate } from '@/utils/date.js'

export default {
  data() {
    return {
      darkMode: false,
      fontSize: 'standard',
      updatedText: '',
      page: { title: '', subtitle: '', updated_label: '', sections: [] }
    }
  },
  onShow() {
    this.updatedText = formatDate()
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadPage()
  },
  methods: {
    async loadPage() {
      try {
        this.page = await getContentPage('legal')
      } catch (error) {
        uni.showToast({ title: error.message || '页面内容加载失败', icon: 'none' })
      }
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
  margin-bottom: 34rpx;
}

.settings-head,
.content-card,
.head-main,
.head-copy,
.meta-strip,
.meta-item,
.section-head {
  display: flex;
}

.settings-head,
.content-card,
.head-copy,
.meta-item {
  flex-direction: column;
}

.legal-head {
  gap: 34rpx;
  margin-bottom: 42rpx;
  padding: 36rpx 34rpx 32rpx;
}

.head-main {
  position: relative;
  z-index: 1;
  align-items: flex-start;
  gap: 26rpx;
}

.document-mark {
  position: relative;
  flex: 0 0 86rpx;
  width: 86rpx;
  height: 96rpx;
  border: 2rpx solid rgba(31, 95, 122, 0.32);
  border-radius: 20rpx;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(232, 244, 247, 0.78)),
    linear-gradient(180deg, rgba(212, 170, 78, 0.18), rgba(31, 95, 122, 0.08));
  box-shadow: 0 18rpx 36rpx rgba(31, 95, 122, 0.12);
}

.document-mark::before {
  content: '';
  position: absolute;
  left: 22rpx;
  top: 20rpx;
  width: 28rpx;
  height: 28rpx;
  border: 4rpx solid rgba(31, 95, 122, 0.66);
  border-radius: 999rpx;
}

.document-mark::after {
  content: '';
  position: absolute;
  left: 36rpx;
  top: 46rpx;
  width: 18rpx;
  height: 22rpx;
  border-right: 4rpx solid rgba(31, 95, 122, 0.66);
  border-bottom: 4rpx solid rgba(31, 95, 122, 0.66);
  transform: rotate(45deg);
}

.document-fold {
  position: absolute;
  top: 0;
  right: 0;
  width: 28rpx;
  height: 28rpx;
  border-left: 1rpx solid rgba(31, 95, 122, 0.2);
  border-bottom: 1rpx solid rgba(31, 95, 122, 0.2);
  border-radius: 0 18rpx 0 12rpx;
  background: rgba(212, 170, 78, 0.18);
}

.document-line {
  position: absolute;
  left: 18rpx;
  bottom: 18rpx;
  width: 36rpx;
  height: 4rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.24);
}

.document-line.long {
  bottom: 30rpx;
  width: 50rpx;
}

.head-copy {
  flex: 1;
  gap: 12rpx;
  min-width: 0;
}

.head-kicker {
  color: #1F5F7A;
  font-size: 23rpx;
  line-height: 1.2;
  font-weight: 900;
}

.meta-strip {
  position: relative;
  z-index: 1;
  flex-direction: row;
  align-items: stretch;
  gap: 22rpx;
  padding: 22rpx 24rpx;
  border: 1rpx solid rgba(31, 95, 122, 0.12);
  border-radius: 22rpx;
  background: rgba(255, 255, 255, 0.58);
}

.meta-item {
  flex: 1;
  gap: 8rpx;
  min-width: 0;
}

.meta-divider {
  width: 1rpx;
  background: rgba(31, 95, 122, 0.14);
}

.meta-label {
  color: #7C8790;
  font-size: 22rpx;
  line-height: 1.2;
}

.meta-value {
  color: #143E52;
  font-size: 25rpx;
  line-height: 1.35;
  font-weight: 800;
}

.content-card {
  gap: 26rpx;
  margin-bottom: 32rpx;
  padding: 40rpx;
}

.legal-section {
  border-color: rgba(31, 95, 122, 0.1) !important;
  background: rgba(255, 255, 255, 0.76) !important;
  box-shadow: 0 18rpx 46rpx rgba(31, 47, 58, 0.08) !important;
}

.section-head {
  align-items: center;
  gap: 18rpx;
}

.section-index {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 42rpx;
  width: 42rpx;
  height: 42rpx;
  border-radius: 14rpx;
  background: rgba(212, 170, 78, 0.18);
  color: #8A641E;
  font-size: 22rpx;
  line-height: 1;
  font-weight: 900;
}

.content-title {
  flex: 1;
  min-width: 0;
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.35;
  font-weight: 900;
}

.content-body {
  color: #3F4F59;
  font-size: 30rpx;
  line-height: 1.86;
  text-align: justify;
}

.font-small .content-body {
  font-size: 28rpx;
}

.font-large .content-card {
  padding: 42rpx 38rpx;
}

.font-large .content-title {
  font-size: 34rpx;
}

.font-large .content-body {
  font-size: 34rpx;
  line-height: 1.86;
}

.dark-mode .legal-head {
  background:
    linear-gradient(135deg, rgba(23,35,49,0.92), rgba(17,27,39,0.76)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08)) !important;
}

.dark-mode .document-mark {
  border-color: rgba(126, 184, 209, 0.22);
  background:
    linear-gradient(145deg, rgba(32, 56, 74, 0.92), rgba(23, 35, 49, 0.78)),
    linear-gradient(180deg, rgba(187, 141, 45, 0.1), rgba(126, 184, 209, 0.08));
  box-shadow: 0 18rpx 38rpx rgba(0, 0, 0, 0.22);
}

.dark-mode .document-mark::before,
.dark-mode .document-mark::after {
  border-color: rgba(126, 184, 209, 0.72);
}

.dark-mode .document-fold {
  border-color: rgba(126, 184, 209, 0.14);
  background: rgba(187, 141, 45, 0.12);
}

.dark-mode .document-line {
  background: rgba(126, 184, 209, 0.24);
}

.dark-mode .head-kicker,
.dark-mode .meta-value {
  color: #7EB8D1 !important;
}

.dark-mode .meta-strip {
  border-color: rgba(126, 184, 209, 0.14);
  background: rgba(14, 23, 32, 0.42);
}

.dark-mode .meta-divider {
  background: rgba(126, 184, 209, 0.14);
}

.dark-mode .meta-label {
  color: #8796A3;
}

.dark-mode .legal-section {
  border-color: rgba(126, 184, 209, 0.14) !important;
  background: rgba(23, 35, 49, 0.74) !important;
  box-shadow: 0 20rpx 52rpx rgba(0, 0, 0, 0.18) !important;
}

.dark-mode .section-index {
  background: rgba(187, 141, 45, 0.14);
  color: #CDA967;
}

@media screen and (max-width: 360px) {
  .head-main {
    gap: 20rpx;
  }

  .document-mark {
    flex-basis: 76rpx;
    width: 76rpx;
    height: 86rpx;
  }

  .meta-strip {
    flex-direction: column;
    gap: 18rpx;
  }

  .meta-divider {
    width: 100%;
    height: 1rpx;
  }
}
</style>
