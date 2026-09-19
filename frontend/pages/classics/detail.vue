<template>
  <view :class="['page classics-detail-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="classics-nav">
      <button class="back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
    </view>

    <view v-if="book" class="book-hero card">
      <view class="hero-bg">
        <image v-if="book.coverImage" class="hero-bg-image" :src="book.coverImage" mode="aspectFill" />
        <view class="hero-bg-overlay"></view>
      </view>

      <view class="cover-shell">
        <view class="cover-stage">
          <image v-if="book.coverImage" class="cover-image" :src="book.coverImage" mode="aspectFill" />
          <view v-else class="cover-fallback">
            <text class="cover-fallback-title">{{ book.title }}</text>
          </view>
        </view>
      </view>

      <view class="hero-copy">
        <view class="hero-meta">
          <text class="tag">{{ book.category || '经典文献' }}</text>
          <text class="source-chip">{{ book.sourceOrg || '权威来源' }}</text>
        </view>
        <text class="book-title">{{ book.title }}</text>
        <text class="book-author">{{ book.author }}</text>
        <text class="book-desc">{{ book.description }}</text>

        <view class="hero-stats">
          <view class="stat-item">
            <text class="stat-value">{{ chapterCount }}</text>
            <text class="stat-label">章节</text>
          </view>
          <view class="stat-item">
            <text class="stat-value">{{ fullTextCount }}</text>
            <text class="stat-label">可读全文</text>
          </view>
        </view>

        <button class="primary-button read-button" @click="openReader()">
          <text class="read-icon">书</text>
          <text>开始阅读</text>
          <image class="read-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
        </button>
      </view>
    </view>

    <view v-if="book" class="catalog-head">
      <view>
        <text class="section-kicker">CATALOG</text>
        <text class="section-title catalog-title">目录</text>
      </view>
      <text class="catalog-count">{{ chapterCount }} 篇</text>
    </view>

    <view v-if="book" class="chapter-list card">
      <view v-for="(chapter, index) in book.chapters" :key="chapter.id || index" class="chapter-item" @click="openReader(chapter)">
        <view class="chapter-axis">
          <text class="chapter-order">{{ chapterOrderText(chapter, index) }}</text>
        </view>
        <view class="chapter-copy">
          <view class="chapter-title-row">
            <text class="chapter-title">{{ chapter.title }}</text>
            <image class="chapter-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
          </view>
          <text class="chapter-summary">{{ chapter.summary || '暂无摘要，进入阅读页查看来源与章节信息。' }}</text>
          <view class="chapter-foot">
            <text :class="['chapter-status', chapter.hasFullText ? 'ready' : 'outline']">
              {{ chapter.hasFullText ? '全文可读' : '目录摘要' }}
            </text>
            <text class="chapter-entry">进入阅读</text>
          </view>
        </view>
      </view>
    </view>

    <view v-if="!book && !loading" class="empty-card card">
      <view class="empty-icon">
        <text>书</text>
      </view>
      <text class="block-title">没有找到这本文献</text>
      <text class="block-body">请返回发现页重新打开。</text>
      <button class="ghost-button empty-button" @click="goBack">返回发现页</button>
    </view>
  </view>
</template>

<script>
import { getClassicBookDetail } from '@/utils/api.js'

export default {
  data() {
    return {
      bookId: '',
      book: null,
      loading: true,
      darkMode: false,
      fontSize: 'standard'
    }
  },
  computed: {
    chapterCount() {
      return this.book && Array.isArray(this.book.chapters) ? this.book.chapters.length : 0
    },
    fullTextCount() {
      if (!this.book || !Array.isArray(this.book.chapters)) return 0
      return this.book.chapters.filter(chapter => chapter.hasFullText).length
    }
  },
  onLoad(options) {
    this.bookId = decodeURIComponent(options.id || '')
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadBook()
  },
  methods: {
    async loadBook() {
      this.loading = true
      try {
        this.book = await getClassicBookDetail(this.bookId)
      } catch (error) {
        uni.showToast({ title: error.message || '经典文献加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    openReader(chapter) {
      const query = [`bookId=${encodeURIComponent(this.bookId)}`]
      if (chapter && chapter.id) query.push(`chapterId=${encodeURIComponent(chapter.id)}`)
      uni.navigateTo({ url: `/pages/classics/reader?${query.join('&')}` })
    },
    chapterOrderText(chapter, index) {
      const order = Number(chapter && chapter.chapterOrder ? chapter.chapterOrder : 0)
      return String(order || index + 1).padStart(2, '0')
    },
    goBack() {
      uni.navigateBack({
        fail: () => uni.switchTab({ url: '/pages/discover/discover' })
      })
    }
  }
}
</script>

<style scoped>
.classics-detail-page {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 2%, rgba(214, 184, 112, 0.34) 0, rgba(214, 184, 112, 0) 300rpx),
    radial-gradient(circle at 92% 8%, rgba(31, 95, 122, 0.2) 0, rgba(31, 95, 122, 0) 340rpx),
    linear-gradient(180deg, #F8F2E6 0%, #EEF5F5 440rpx, #F5F7F4 100%);
}

.classics-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 56rpx;
  margin-bottom: 32rpx;
}

.book-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-color: rgba(255,255,255,0.9);
  background:
    linear-gradient(135deg, rgba(255,255,255,0.84), rgba(255,255,255,0.5)),
    linear-gradient(135deg, rgba(245,235,207,0.92), rgba(226,240,244,0.78));
}

.hero-bg {
  position: relative;
  height: 270rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(31,95,122,0.9), rgba(14,43,59,0.92)),
    linear-gradient(135deg, rgba(212,170,78,0.22), transparent);
}

.hero-bg-image,
.hero-bg-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.hero-bg-image {
  opacity: 0.44;
  filter: blur(8rpx);
  transform: scale(1.08);
}

.hero-bg-overlay {
  background:
    linear-gradient(180deg, rgba(6,21,32,0.1), rgba(6,21,32,0.56)),
    linear-gradient(90deg, rgba(15,44,61,0.82), rgba(15,44,61,0.16));
}

.cover-shell {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  margin-top: -198rpx;
  padding: 0 42rpx;
}

.cover-stage {
  position: relative;
  width: 238rpx;
  height: 326rpx;
  border: 8rpx solid rgba(255,255,255,0.66);
  border-radius: 18rpx;
  overflow: hidden;
  background: #E7E0D1;
  box-shadow:
    0 30rpx 70rpx rgba(8, 28, 38, 0.32),
    14rpx 14rpx 0 rgba(20,33,43,0.14);
}

.cover-stage::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 26rpx;
  z-index: 2;
  width: 2rpx;
  background: rgba(255,255,255,0.32);
}

.cover-image {
  width: 100%;
  height: 100%;
}

.cover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  padding: 28rpx;
  background:
    linear-gradient(180deg, rgba(31,95,122,0.86), rgba(17,55,73,0.94)),
    linear-gradient(135deg, rgba(212,170,78,0.28), transparent);
}

.cover-fallback-title {
  color: #FFFFFF;
  font-size: 31rpx;
  line-height: 1.35;
  font-weight: 900;
  text-align: center;
}

.hero-copy {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20rpx;
  padding: 34rpx 42rpx 42rpx;
  text-align: center;
}

.hero-meta {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 14rpx;
}

.source-chip {
  display: inline-flex;
  align-items: center;
  max-width: 360rpx;
  min-height: 40rpx;
  padding: 0 16rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.16);
  color: #876112;
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.book-title {
  color: #000000;
  font-size: 48rpx;
  line-height: 1.18;
  font-weight: 900;
}

.book-author {
  color: #1F5F7A;
  font-size: 27rpx;
  line-height: 1.35;
  font-weight: 800;
}

.book-desc,
.block-body,
.chapter-summary {
  color: #5C6873;
  font-size: 26rpx;
  line-height: 1.68;
}

.hero-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 18rpx;
  width: 100%;
  margin-top: 2rpx;
}

.stat-item {
  display: flex;
  flex: 1;
  min-width: 0;
  max-width: 220rpx;
  flex-direction: column;
  gap: 8rpx;
  padding: 18rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.58);
  box-shadow: 0 14rpx 34rpx rgba(20, 33, 43, 0.07);
}

.stat-value {
  color: #143E52;
  font-size: 32rpx;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  color: #66737B;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 800;
}

.read-button {
  width: 100%;
  gap: 14rpx;
  margin-top: 8rpx;
  box-shadow: 0 22rpx 48rpx rgba(31, 95, 122, 0.24);
}

.read-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42rpx;
  height: 42rpx;
  border-radius: 999rpx;
  background: rgba(255,255,255,0.16);
  color: #FFFFFF;
  font-size: 20rpx;
  line-height: 1;
  font-weight: 900;
}

.read-arrow {
  width: 28rpx;
  height: 28rpx;
  filter: brightness(0) invert(1);
  opacity: 0.9;
}

.empty-card {
  display: flex;
  gap: 24rpx;
  margin-top: 34rpx;
  padding: 34rpx;
}

.block-title {
  color: #000000;
  font-size: 30rpx;
  font-weight: 900;
}

.catalog-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  margin: 70rpx 0 30rpx;
}

.section-kicker {
  display: block;
  margin-bottom: 8rpx;
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.catalog-title {
  margin: 0;
}

.catalog-count {
  flex: 0 0 auto;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.chapter-list {
  position: relative;
  display: flex;
  flex-direction: column;
  padding: 10rpx 34rpx;
  overflow: hidden;
}

.chapter-list::before {
  content: '';
  position: absolute;
  top: 52rpx;
  bottom: 52rpx;
  left: 62rpx;
  width: 2rpx;
  background: linear-gradient(180deg, rgba(212,170,78,0.44), rgba(31,95,122,0.22));
}

.chapter-item {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  gap: 24rpx;
  padding: 30rpx 0;
  border-bottom: 1rpx solid rgba(31,95,122,0.1);
}

.chapter-item:active {
  transform: scale(0.99);
  opacity: 0.92;
}

.chapter-item:last-child {
  border-bottom: none;
}

.chapter-axis {
  position: relative;
  display: flex;
  flex: 0 0 auto;
  justify-content: center;
  width: 56rpx;
}

.chapter-order {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56rpx;
  height: 56rpx;
  border: 4rpx solid rgba(255,255,255,0.92);
  border-radius: 999rpx;
  background: linear-gradient(135deg, #D4AA4E, #A97B23);
  color: #FFFFFF;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 1;
  box-shadow: 0 12rpx 28rpx rgba(169, 123, 35, 0.2);
}

.chapter-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 14rpx;
  margin-left: 22rpx;
  padding-top: 4rpx;
}

.chapter-title-row,
.chapter-foot {
  display: flex;
  align-items: center;
}

.chapter-title-row {
  justify-content: space-between;
  gap: 20rpx;
}

.chapter-title {
  flex: 1;
  min-width: 0;
  color: #000000;
  font-size: 30rpx;
  line-height: 1.4;
  font-weight: 900;
}

.chapter-arrow {
  flex: 0 0 auto;
  width: 26rpx;
  height: 26rpx;
  opacity: 0.5;
}

.chapter-foot {
  justify-content: space-between;
  gap: 20rpx;
  margin-top: 6rpx;
}

.chapter-status,
.chapter-entry {
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.chapter-status {
  padding: 7rpx 14rpx;
  border-radius: 999rpx;
}

.chapter-status.ready {
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
}

.chapter-status.outline {
  background: rgba(212,170,78,0.16);
  color: #876112;
}

.chapter-entry {
  color: #7C8790;
}

.empty-card {
  flex-direction: column;
  align-items: center;
  margin-top: 120rpx;
  padding: 52rpx 40rpx;
  text-align: center;
}

.empty-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 92rpx;
  height: 92rpx;
  border-radius: 28rpx;
  background: rgba(31,95,122,0.1);
}

.empty-icon text {
  color: #1F5F7A;
  font-size: 30rpx;
  font-weight: 900;
}

.empty-button {
  width: 100%;
  margin-top: 10rpx;
}

.font-large .book-title {
  font-size: 52rpx;
}

.font-large .book-desc,
.font-large .block-body,
.font-large .chapter-summary {
  font-size: 30rpx;
}

.font-large .chapter-title {
  font-size: 34rpx;
}

.font-small .book-title {
  font-size: 42rpx;
}

.font-small .book-desc,
.font-small .block-body,
.font-small .chapter-summary {
  font-size: 24rpx;
}

.font-small .chapter-title {
  font-size: 27rpx;
}

.dark-mode.classics-detail-page {
  background:
    radial-gradient(circle at 12% 2%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 300rpx),
    radial-gradient(circle at 92% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 340rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .chapter-arrow {
  filter: brightness(0) invert(1);
}

.dark-mode .book-hero {
  border-color: rgba(126,184,209,0.16) !important;
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.76)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08)) !important;
}

.dark-mode .cover-stage {
  border-color: rgba(126,184,209,0.2);
  box-shadow:
    0 30rpx 70rpx rgba(0, 0, 0, 0.38),
    14rpx 14rpx 0 rgba(126,184,209,0.08);
}

.dark-mode .book-title,
.dark-mode .block-title,
.dark-mode .chapter-title,
.dark-mode .section-title {
  color: #000000 !important;
}

.dark-mode .stat-value {
  color: #F4F7FA !important;
}

.dark-mode .book-desc,
.dark-mode .block-body,
.dark-mode .chapter-summary,
.dark-mode .stat-label,
.dark-mode .chapter-entry {
  color: #B6C2CC !important;
}

.dark-mode .book-author,
.dark-mode .catalog-count,
.dark-mode .chapter-status.ready {
  color: #7EB8D1 !important;
}

.dark-mode .source-chip,
.dark-mode .section-kicker,
.dark-mode .chapter-status.outline {
  color: #D4AA4E !important;
}

.dark-mode .source-chip,
.dark-mode .chapter-status.outline {
  background: rgba(212,170,78,0.14) !important;
}

.dark-mode .stat-item,
.dark-mode .chapter-list,
.dark-mode .empty-card {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

.dark-mode .catalog-count,
.dark-mode .chapter-status.ready,
.dark-mode .empty-icon {
  background: rgba(126,184,209,0.12) !important;
}

.dark-mode .chapter-list::before {
  background: linear-gradient(180deg, rgba(212,170,78,0.34), rgba(126,184,209,0.2));
}

.dark-mode .chapter-item {
  border-bottom-color: rgba(126,184,209,0.13);
}

.dark-mode .chapter-order {
  border-color: rgba(23,35,49,0.96);
}
</style>
