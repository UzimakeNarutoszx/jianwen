<template>
  <view :class="['page list-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="detail-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view class="folder-hero">
      <view class="folder-glow gold"></view>
      <view class="folder-glow blue"></view>
      <view class="folder-icon">
        <image class="folder-image" src="/static/icons/func-favorite.png" mode="aspectFit" />
      </view>
      <view class="folder-copy">
        <text class="eyebrow">知识资产库</text>
        <text class="page-title">我的收藏</text>
        <text class="subtle">{{ heroSubtitle }}</text>
      </view>
      <view class="sync-badge">
        <text class="sync-dot"></text>
        <text>{{ syncStatusText }}</text>
      </view>
      <view class="hero-stats">
        <view class="hero-stat">
          <text class="stat-value">{{ articles.length }}</text>
          <text class="stat-label">已收藏</text>
        </view>
        <view class="hero-stat">
          <text class="stat-value">{{ topicCount }}</text>
          <text class="stat-label">主题</text>
        </view>
        <view class="hero-stat">
          <text class="stat-value">{{ totalReadTime }}</text>
          <text class="stat-label">阅读</text>
        </view>
      </view>
    </view>

    <view v-if="articles.length" class="filter-row">
      <button
        v-for="item in filters"
        :key="item"
        :class="['filter-pill', activeFilter === item ? 'active' : '']"
        @click="activeFilter = item"
      >
        {{ item }}
      </button>
    </view>

    <view v-if="filteredArticles.length" class="article-list">
      <view v-for="item in filteredArticles" :key="item.id" class="article-card card" @click="openArticle(item.id)">
        <view class="star-mark">
          <image class="star-icon" src="/static/icons/func-favorite.png" mode="aspectFit" />
        </view>
        <view class="card-head">
          <text class="tag">{{ item.topic }}</text>
          <view class="read-meta">
            <text class="meta-dot"></text>
            <text>{{ item.readTime || '约 3 分钟' }}</text>
          </view>
        </view>
        <text class="article-title">{{ item.title }}</text>
        <text class="article-desc">{{ item.desc }}</text>
        <view class="source-row">
          <text class="source-label">来源</text>
          <text class="source-line">{{ item.sources || '见闻整理' }}</text>
        </view>
      </view>
    </view>

    <view v-else class="empty-card card">
      <view class="empty-icon">
        <image class="empty-image" src="/static/icons/func-favorite.png" mode="aspectFit" />
      </view>
      <text class="empty-title">{{ emptyTitle }}</text>
      <text class="empty-desc">{{ emptyDesc }}</text>
      <button class="primary-button" @click="goToday">去今日看看</button>
    </view>
  </view>
</template>

<script>
import { getRemoteFavorites } from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'

export default {
  data() {
    return {
      darkMode: false,
      fontSize: 'standard',
      articles: [],
      isAuthed: false,
      activeFilter: '全部'
    }
  },
  computed: {
    heroSubtitle() {
      if (!this.isAuthed) return '登录后，文章收藏会在云端同步。'
      return this.articles.length ? `已收藏 ${this.articles.length} 篇文章，可按主题快速回看。` : '收藏的文章会出现在这里。'
    },
    syncStatusText() {
      if (!this.isAuthed) return '未登录'
      return this.articles.length ? '云端已同步' : '等待收藏'
    },
    emptyTitle() {
      if (this.articles.length) return '当前主题暂无收藏'
      return this.isAuthed ? '还没有收藏' : '登录后同步收藏'
    },
    emptyDesc() {
      if (this.articles.length) return `“${this.activeFilter}”下还没有收藏文章，可以切回全部查看。`
      if (!this.isAuthed) return '当前未登录，收藏列表暂不可同步。先去今日页看看，也可以在文章详情页收藏内容。'
      return '在文章详情页点右上角星标，就能把文章收进这里。'
    },
    filters() {
      const defaults = ['全部', '政策', '民生', '科技']
      const topics = this.articles.map(item => item.topic).filter(Boolean)
      return Array.from(new Set(defaults.concat(topics))).slice(0, 8)
    },
    filteredArticles() {
      if (this.activeFilter === '全部') return this.articles
      return this.articles.filter(item => item.topic === this.activeFilter)
    },
    topicCount() {
      return new Set(this.articles.map(item => item.topic).filter(Boolean)).size
    },
    totalReadTime() {
      const total = this.articles.reduce((sum, item) => {
        const match = `${item.readTime || ''}`.match(/\d+/)
        return sum + (match ? Number(match[0]) : 3)
      }, 0)
      return total ? `${total}分` : '-'
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
      this.isAuthed = !!uni.getStorageSync('jianwen_auth_token')
      if (!this.isAuthed) {
        this.articles = []
        return
      }
      try {
        this.articles = await getRemoteFavorites()
        if (!this.filters.includes(this.activeFilter)) this.activeFilter = '全部'
      } catch (error) {
        uni.showToast({ title: error.message || '收藏加载失败', icon: 'none' })
      }
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

.page-head,
.article-list,
.empty-card {
  display: flex;
  flex-direction: column;
}

.page-head {
  gap: 18rpx;
  margin-bottom: 52rpx;
}

.folder-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  padding: 38rpx 34rpx 34rpx;
  margin-bottom: 34rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 32rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.54)),
    linear-gradient(135deg, rgba(245,235,207,0.88), rgba(226,240,244,0.78));
  box-shadow: 0 26rpx 68rpx rgba(48, 65, 72, 0.11);
}

.folder-glow {
  position: absolute;
  border-radius: 999rpx;
  pointer-events: none;
}

.folder-glow.gold {
  top: -74rpx;
  right: -44rpx;
  width: 220rpx;
  height: 220rpx;
  background: rgba(212, 170, 78, 0.2);
}

.folder-glow.blue {
  bottom: 92rpx;
  left: -84rpx;
  width: 230rpx;
  height: 230rpx;
  background: rgba(31, 95, 122, 0.12);
}

.folder-icon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 92rpx;
  height: 92rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 26rpx;
  background: rgba(255,255,255,0.58);
}

.folder-image {
  width: 52rpx;
  height: 52rpx;
}

.folder-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 14rpx;
}

.eyebrow {
  color: #D4AA4E;
  font-size: 23rpx;
  font-weight: 900;
}

.sync-badge {
  position: absolute;
  top: 40rpx;
  right: 32rpx;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10rpx;
  min-height: 52rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.64);
  color: #1F5F7A;
  font-size: 23rpx;
  font-weight: 800;
}

.sync-dot {
  width: 10rpx;
  height: 10rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
}

.hero-stats {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16rpx;
}

.hero-stat {
  display: flex;
  flex-direction: column;
  gap: 6rpx;
  min-height: 104rpx;
  padding: 20rpx 18rpx;
  border: 1rpx solid rgba(255,255,255,0.66);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.52);
}

.stat-value {
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.1;
  font-weight: 900;
}

.stat-label {
  color: #66737B;
  font-size: 22rpx;
}

.filter-row {
  display: flex;
  gap: 16rpx;
  margin: 0 -4rpx 30rpx;
  overflow-x: auto;
  white-space: nowrap;
}

.filter-pill {
  flex: 0 0 auto;
  min-height: 62rpx;
  padding: 0 28rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.66);
  color: #5C6873;
  font-size: 25rpx;
  font-weight: 800;
}

.filter-pill.active {
  border-color: rgba(31,95,122,0.2);
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  box-shadow: 0 16rpx 36rpx rgba(31, 95, 122, 0.18);
}

.article-list {
  gap: 28rpx;
}

.article-card,
.empty-card {
  padding: 38rpx;
}

.article-card {
  position: relative;
  overflow: hidden;
}

.article-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 8rpx;
  height: 100%;
  background: linear-gradient(180deg, #D4AA4E, rgba(31,95,122,0.18));
}

.star-mark {
  position: absolute;
  top: 34rpx;
  right: 34rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54rpx;
  height: 54rpx;
  border-radius: 18rpx;
  background: rgba(212,170,78,0.13);
}

.star-icon {
  width: 30rpx;
  height: 30rpx;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 78rpx;
  padding-right: 64rpx;
}

.read-meta {
  display: flex;
  align-items: center;
  gap: 10rpx;
  flex-shrink: 0;
  color: #8A949E;
  font-size: 24rpx;
}

.meta-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
}

.article-title {
  display: block;
  margin-top: 30rpx;
  color: #14212B;
  font-size: 32rpx;
  line-height: 1.38;
  font-weight: 800;
}

.article-desc {
  display: block;
  margin: 22rpx 0 26rpx;
  color: #5C6873;
  font-size: 27rpx;
  line-height: 1.62;
}

.source-row {
  display: flex;
  align-items: flex-start;
  gap: 14rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid rgba(31,95,122,0.08);
}

.source-label {
  flex: 0 0 auto;
  color: #D4AA4E;
  font-size: 23rpx;
  font-weight: 900;
}

.empty-card {
  align-items: flex-start;
  gap: 28rpx;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 96rpx;
  height: 96rpx;
  border-radius: 28rpx;
  background: linear-gradient(135deg, rgba(31,95,122,0.1), rgba(212,170,78,0.16));
}

.empty-image {
  width: 52rpx;
  height: 52rpx;
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

.dark-mode .folder-hero {
  border-color: rgba(126,184,209,0.16);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .folder-icon,
.dark-mode .hero-stat,
.dark-mode .sync-badge,
.dark-mode .filter-pill {
  border-color: rgba(126,184,209,0.16);
  background: rgba(23,35,49,0.72);
}

.dark-mode .stat-value,
.dark-mode .article-title,
.dark-mode .empty-title {
  color: #F4F7FA;
}

.dark-mode .stat-label,
.dark-mode .article-desc,
.dark-mode .empty-desc,
.dark-mode .read-meta {
  color: #B6C2CC;
}

.dark-mode .source-row {
  border-top-color: rgba(126,184,209,0.12);
}

.dark-mode .filter-pill.active {
  border-color: rgba(126,184,209,0.24);
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
}
</style>
