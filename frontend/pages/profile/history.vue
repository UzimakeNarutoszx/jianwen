<template>
  <view :class="['page list-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="detail-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="history-hero">
      <view class="hero-copy">
        <text class="hero-kicker">阅读轨迹</text>
        <text class="page-title">最近看过</text>
        <text class="subtle">{{ heroSubtitle }}</text>
      </view>
      <view class="hero-stat">
        <text class="stat-number">{{ articles.length }}</text>
        <text class="stat-label">篇文章</text>
      </view>
    </view>

    <view v-if="articles.length" class="timeline-list">
      <view v-for="group in groupedArticles" :key="group.key" class="timeline-group">
        <view class="group-head">
          <text class="group-title">{{ group.label }}</text>
          <text class="group-count">{{ group.items.length }} 篇</text>
        </view>
        <view class="group-body">
          <view v-for="item in group.items" :key="item.id" class="timeline-item">
            <view class="timeline-rail">
              <view class="timeline-dot"></view>
              <view class="timeline-line"></view>
            </view>
            <view class="article-card card" @click="openArticle(item.id)">
              <view class="card-head">
                <view class="time-block">
                  <text class="read-time">{{ formatTime(item.visitedAt) }}</text>
                  <text class="read-date">{{ formatDateLabel(item.visitedAt) }}</text>
                </view>
                <text class="tag">{{ item.topic || '见闻' }}</text>
              </view>
              <text class="article-title">{{ item.title }}</text>
              <text class="article-desc">{{ item.desc }}</text>
              <text class="source-line">{{ item.sources }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <view v-else class="empty-card card">
      <view class="empty-icon">
        <image class="empty-icon-img" src="/static/icons/func-history.png" mode="aspectFit" />
      </view>
      <text class="empty-title">{{ emptyTitle }}</text>
      <text class="empty-desc">{{ emptyDesc }}</text>
      <button class="primary-button" @click="goToday">去今日看看</button>
    </view>
  </view>
</template>

<script>
import { getRemoteHistory } from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'

export default {
  data() {
    return { darkMode: false, fontSize: 'standard', articles: [], hasAuth: false }
  },
  computed: {
    heroSubtitle() {
      if (!this.hasAuth) return '登录后可同步保存最近看过的文章'
      return this.articles.length ? '按时间回到刚刚读过的内容，继续阅读更快' : '读过的文章会按时间保存在这里'
    },
    emptyTitle() {
      return this.hasAuth ? '还没有阅读记录' : '登录后查看阅读记录'
    },
    emptyDesc() {
      return this.hasAuth ? '打开一篇文章后，它会自动加入最近看过。' : '登录后，阅读过的文章会在这里按时间同步保存。'
    },
    groupedArticles() {
      const groups = [
        { key: 'today', label: '今天', items: [] },
        { key: 'yesterday', label: '昨天', items: [] },
        { key: 'earlier', label: '更早', items: [] }
      ]
      this.articles.forEach(item => {
        const distance = this.getDayDistance(item.visitedAt)
        if (distance === 0) groups[0].items.push(item)
        else if (distance === 1) groups[1].items.push(item)
        else groups[2].items.push(item)
      })
      return groups.filter(group => group.items.length)
    }
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadArticles()
    applyTabBarTheme(this.darkMode)
  },
  methods: {
    async loadArticles() {
      this.hasAuth = !!uni.getStorageSync('jianwen_auth_token')
      if (!this.hasAuth) {
        this.articles = []
        return
      }
      try {
        this.articles = await getRemoteHistory()
      } catch (error) {
        uni.showToast({ title: error.message || '历史加载失败', icon: 'none' })
      }
    },
    toDate(value) { return value ? new Date(value) : new Date() },
    pad(value) { return String(value).padStart(2, '0') },
    getDayDistance(value) {
      const date = this.toDate(value)
      const today = new Date()
      const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime()
      const target = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
      return Math.floor((start - target) / 86400000)
    },
    formatTime(value) {
      const date = this.toDate(value)
      return `${this.pad(date.getHours())}:${this.pad(date.getMinutes())}`
    },
    formatDateLabel(value) {
      const date = this.toDate(value)
      return `${date.getMonth() + 1}月${date.getDate()}日`
    },
    openArticle(id) { uni.navigateTo({ url: `/pages/article/detail?id=${id}` }) },
    goToday() { uni.switchTab({ url: '/pages/today/today' }) },
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

.history-hero,
.hero-copy,
.hero-stat,
.timeline-list,
.timeline-group,
.group-body,
.timeline-item,
.empty-card {
  display: flex;
  flex-direction: column;
}

.history-hero {
  position: relative;
  gap: 30rpx;
  padding: 38rpx 34rpx 36rpx;
  margin-bottom: 54rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 30rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.48)),
    linear-gradient(135deg, rgba(245,235,207,0.84), rgba(226,240,244,0.72));
  box-shadow: 0 24rpx 64rpx rgba(48, 65, 72, 0.1);
}

.history-hero::after {
  content: '';
  position: absolute;
  right: -58rpx;
  top: -76rpx;
  width: 230rpx;
  height: 230rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.18);
  pointer-events: none;
}

.hero-copy {
  position: relative;
  z-index: 1;
  gap: 16rpx;
}

.hero-kicker {
  color: #1F5F7A;
  font-size: 23rpx;
  line-height: 1.3;
  font-weight: 900;
}

.hero-stat {
  position: relative;
  z-index: 1;
  align-self: flex-start;
  min-width: 162rpx;
  padding: 20rpx 24rpx;
  border: 1rpx solid rgba(212, 170, 78, 0.34);
  border-radius: 26rpx;
  background: rgba(255, 250, 235, 0.7);
}

.stat-number {
  color: #A76A1D;
  font-size: 48rpx;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  margin-top: 8rpx;
  color: #6E7A82;
  font-size: 22rpx;
  line-height: 1.3;
  font-weight: 800;
}

.timeline-list {
  gap: 46rpx;
}

.timeline-group {
  gap: 22rpx;
}

.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  padding-left: 60rpx;
}

.group-title {
  color: #14212B;
  font-size: 30rpx;
  line-height: 1.35;
  font-weight: 900;
}

.group-count {
  color: #8A949E;
  font-size: 22rpx;
  line-height: 1.4;
}

.group-body {
  gap: 28rpx;
}

.timeline-item {
  position: relative;
  flex-direction: row;
  gap: 18rpx;
  align-items: stretch;
}

.timeline-rail {
  position: relative;
  width: 42rpx;
  flex: 0 0 42rpx;
  display: flex;
  justify-content: center;
}

.timeline-dot {
  position: relative;
  z-index: 1;
  width: 18rpx;
  height: 18rpx;
  margin-top: 40rpx;
  border: 5rpx solid rgba(255,255,255,0.95);
  border-radius: 999rpx;
  background: #D4AA4E;
  box-shadow: 0 0 0 8rpx rgba(212, 170, 78, 0.18);
}

.timeline-line {
  position: absolute;
  top: 58rpx;
  bottom: -28rpx;
  width: 2rpx;
  background: linear-gradient(180deg, rgba(31,95,122,0.22), rgba(31,95,122,0.02));
}

.article-card,
.empty-card {
  padding: 40rpx;
}

.article-card {
  flex: 1;
  min-width: 0;
}

.card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22rpx;
}

.time-block {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-width: 0;
}

.article-title {
  display: block;
  margin-top: 30rpx;
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.38;
  font-weight: 800;
  word-break: break-word;
}

.article-desc {
  display: block;
  margin: 24rpx 0;
  color: #5C6873;
  font-size: 27rpx;
  line-height: 1.62;
}

.read-time {
  color: #1F5F7A;
  font-size: 34rpx;
  line-height: 1.1;
  font-weight: 900;
}

.read-date {
  color: #8A949E;
  font-size: 22rpx;
  line-height: 1.3;
}

.empty-card {
  align-items: stretch;
  gap: 28rpx;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 88rpx;
  height: 88rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.1);
}

.empty-icon-img {
  width: 46rpx;
  height: 46rpx;
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

.dark-mode .history-hero {
  border-color: rgba(126,184,209,0.16);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .hero-kicker,
.dark-mode .read-time {
  color: #7EB8D1;
}

.dark-mode .hero-stat {
  border-color: rgba(187, 141, 45, 0.22);
  background: rgba(53, 43, 23, 0.42);
}

.dark-mode .stat-number {
  color: #D4AA4E;
}

.dark-mode .stat-label,
.dark-mode .group-count,
.dark-mode .read-date,
.dark-mode .article-desc,
.dark-mode .empty-desc {
  color: #B6C2CC;
}

.dark-mode .group-title,
.dark-mode .article-title,
.dark-mode .empty-title {
  color: #F4F7FA;
}

.dark-mode .timeline-dot {
  border-color: #172331;
  background: #D4AA4E;
  box-shadow: 0 0 0 8rpx rgba(212, 170, 78, 0.14);
}

.dark-mode .timeline-line {
  background: linear-gradient(180deg, rgba(126,184,209,0.28), rgba(126,184,209,0.03));
}

.dark-mode .empty-icon {
  background: #20384A;
}
</style>
