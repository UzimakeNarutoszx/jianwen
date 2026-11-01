<template>
  <view :class="['page record-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="detail-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="record-hero">
      <view class="hero-copy">
        <text class="hero-kicker">AI ARCHIVE</text>
        <text class="hero-title">AI 档案库</text>
        <text class="hero-desc">{{ heroDesc }}</text>
      </view>
      <view class="hero-count">
        <text class="count-value">{{ records.length }}</text>
        <text class="count-label">条记录</text>
      </view>
    </view>

    <view v-if="records.length" class="record-list">
      <view v-for="record in records" :key="record.id" class="record-card card">
        <view class="record-meta">
          <text class="record-time">{{ formatTime(record.createdAt) }}</text>
          <text class="record-badge">问问</text>
        </view>
        <view class="question-block">
          <text class="block-label">问题</text>
          <text class="question-text">{{ record.question }}</text>
        </view>
        <view class="answer-block">
          <text class="block-label">回答摘要</text>
          <text class="answer-text">{{ summaryText(record.answer) }}</text>
        </view>
        <view class="record-actions">
          <text v-if="record.sources" class="source-link">来源入口：{{ record.sources }}</text>
          <text v-else class="source-link muted">暂无来源入口</text>
          <button class="continue-button" @click="continueAsk(record)">继续问</button>
        </view>
      </view>
    </view>

    <view v-else class="empty-card card">
      <view class="empty-icon">
        <image class="empty-icon-image" src="/static/icons/func-chat.png" mode="aspectFit" />
      </view>
      <text class="empty-title">还没有问问记录</text>
      <text class="empty-desc">在问问页发送问题后，问题、回答摘要和来源入口会自动保存到这里。</text>
      <button class="primary-button" @click="goAsk">去问问</button>
    </view>
  </view>
</template>

<script>
import { getRemoteAiRecords } from '@/utils/api.js'
import { formatDateTime } from '@/utils/date.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import { getAskRecords } from '@/utils/user-data.js'

export default {
  data() {
    return { darkMode: false, fontSize: 'standard', records: [] }
  },
  computed: {
    heroDesc() {
      if (!this.records.length) return '你问过的问题会保存在这里，方便回看依据和继续追问。'
      const latest = this.records[0] && this.records[0].createdAt ? this.formatTime(this.records[0].createdAt) : '刚刚更新'
      return `已保存 ${this.records.length} 条问问，最近更新于 ${latest}`
    }
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadRecords()
    applyTabBarTheme(this.darkMode)
  },
  methods: {
    async loadRecords() {
      if (!uni.getStorageSync('jianwen_auth_token')) {
        this.records = getAskRecords()
        return
      }
      try {
        this.records = await getRemoteAiRecords()
      } catch (error) {
        this.records = getAskRecords()
        uni.showToast({ title: error.message || '问问记录加载失败', icon: 'none' })
      }
    },
    formatTime(value) { return value ? formatDateTime(value) : '刚刚' },
    summaryText(value) {
      const text = String(value || '').replace(/\s+/g, ' ').trim()
      if (!text) return '这条记录暂时没有回答摘要。'
      return text.length > 118 ? `${text.slice(0, 118)}...` : text
    },
    continueAsk(record) {
      uni.setStorageSync('jianwen_pending_ask_context', {
        question: record.question ? `继续围绕这个问题追问：${record.question}` : '',
        title: record.question || '问问记录',
        sources: record.sources || '',
        fromRecord: true
      })
      this.goAsk()
    },
    goAsk() { uni.switchTab({ url: '/pages/ask/ask' }) },
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
.detail-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 44rpx;
  margin-bottom: 42rpx;
}

.page-head,
.record-list,
.record-card,
.empty-card,
.record-hero,
.hero-copy,
.hero-count,
.question-block,
.answer-block {
  display: flex;
  flex-direction: column;
}

.record-hero {
  position: relative;
  flex-direction: row;
  align-items: flex-end;
  justify-content: space-between;
  gap: 28rpx;
  min-height: 260rpx;
  padding: 42rpx;
  margin-bottom: 42rpx;
  border: 1rpx solid rgba(255,255,255,0.74);
  border-radius: 30rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(31,95,122,0.96), rgba(18,55,75,0.92)),
    linear-gradient(135deg, rgba(212,170,78,0.22), transparent);
  box-shadow: 0 24rpx 64rpx rgba(31, 47, 58, 0.16);
}

.record-hero::after {
  content: '';
  position: absolute;
  right: -72rpx;
  top: -84rpx;
  width: 250rpx;
  height: 250rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.22);
  pointer-events: none;
}

.hero-copy,
.hero-count {
  position: relative;
  z-index: 1;
}

.hero-copy {
  flex: 1;
  min-width: 0;
  gap: 14rpx;
}

.hero-kicker {
  color: #D4AA4E;
  font-size: 20rpx;
  line-height: 1.2;
  font-weight: 900;
}

.hero-title {
  color: #FFFFFF;
  font-size: 46rpx;
  line-height: 1.18;
  font-weight: 900;
}

.hero-desc {
  color: rgba(255,255,255,0.82);
  font-size: 25rpx;
  line-height: 1.55;
}

.hero-count {
  align-items: center;
  justify-content: center;
  flex: 0 0 148rpx;
  width: 148rpx;
  min-height: 148rpx;
  border: 1rpx solid rgba(255,255,255,0.34);
  border-radius: 28rpx;
  background: rgba(255,255,255,0.14);
}

.count-value {
  color: #FFFFFF;
  font-size: 52rpx;
  line-height: 1.05;
  font-weight: 900;
}

.count-label {
  margin-top: 8rpx;
  color: rgba(255,255,255,0.72);
  font-size: 22rpx;
  line-height: 1.2;
}

.record-list {
  gap: 30rpx;
}

.record-card,
.empty-card {
  gap: 26rpx;
  padding: 38rpx;
}

.record-meta,
.record-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
}

.record-time {
  color: #8A949E;
  font-size: 23rpx;
  line-height: 1.35;
}

.record-badge {
  flex: 0 0 auto;
  min-height: 38rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(212,170,78,0.16);
  color: #A76A1D;
  font-size: 21rpx;
  line-height: 38rpx;
  font-weight: 900;
}

.question-block,
.answer-block {
  gap: 14rpx;
}

.block-label {
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1.3;
  font-weight: 900;
}

.question-text {
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.42;
  font-weight: 900;
}

.answer-block {
  padding: 26rpx;
  border: 1rpx solid rgba(31,95,122,0.08);
  border-radius: 22rpx;
  background: rgba(247,250,252,0.78);
}

.answer-text {
  color: #3F4F59;
  font-size: 27rpx;
  line-height: 1.62;
}

.source-link {
  flex: 1;
  min-width: 0;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.45;
}

.source-link.muted {
  color: #A3AEB6;
}

.continue-button {
  flex: 0 0 auto;
  min-width: 132rpx;
  min-height: 62rpx;
  padding: 0 24rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  font-size: 24rpx;
  line-height: 62rpx;
  font-weight: 900;
  white-space: nowrap;
}

.empty-card {
  align-items: center;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 112rpx;
  height: 112rpx;
  border-radius: 30rpx;
  background: linear-gradient(135deg, rgba(31,95,122,0.12), rgba(212,170,78,0.16));
}

.empty-icon-image {
  width: 58rpx;
  height: 58rpx;
}

.empty-title {
  color: #14212B;
  font-size: 32rpx;
  font-weight: 900;
}

.empty-desc {
  color: #5C6873;
  font-size: 27rpx;
  line-height: 1.6;
}

.dark-mode .record-hero {
  border-color: rgba(126,184,209,0.16);
  background:
    linear-gradient(135deg, rgba(31,95,122,0.86), rgba(16,39,55,0.94)),
    linear-gradient(135deg, rgba(212,170,78,0.14), transparent);
  box-shadow: 0 24rpx 64rpx rgba(0, 0, 0, 0.26);
}

.dark-mode .question-text,
.dark-mode .empty-title {
  color: #F4F7FA;
}

.dark-mode .answer-block {
  border-color: rgba(126,184,209,0.14);
  background: rgba(12,23,33,0.42);
}

.dark-mode .block-label {
  color: #7EB8D1;
}

.dark-mode .record-badge {
  background: rgba(187,141,45,0.18);
  color: #D4AA4E;
}

.dark-mode .source-link,
.dark-mode .empty-desc {
  color: #B6C2CC;
}
</style>
