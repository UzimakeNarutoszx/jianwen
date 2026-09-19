<template>
  <view :class="['page article-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="detail-nav">
      <view class="article-nav-button article-back-button back-button" @tap.stop="handleNavAction('back')" @click.stop="handleNavAction('back')" role="button" aria-label="返回">
        <text class="back-symbol"></text>
      </view>
      <view :class="['article-nav-button article-favorite-button', isFavorite ? 'active' : '']" @tap.stop="handleNavAction('favorite')" @click.stop="handleNavAction('favorite')" role="button">
        <text class="favorite-icon">{{ isFavorite ? '★' : '☆' }}</text>
        <text class="favorite-text">{{ isFavorite ? '已收藏' : '收藏' }}</text>
      </view>
    </view>

    <view class="article-hero">
      <view class="hero-topline">
        <text class="tag">{{ article.topic || '政策解读' }}</text>
        <text class="hero-kicker">深度解读报告</text>
      </view>
      <text class="title">{{ article.title || '文章加载中' }}</text>
      <view class="article-info">
        <text class="meta">{{ article.readTime || '约 5 分钟' }} · AI辅助整理</text>
        <text class="source-line">{{ article.sources || '以权威来源为准' }}</text>
      </view>
    </view>

    <view class="summary-card card">
      <view class="summary-head">
        <text class="block-title">先看这三点</text>
        <text class="summary-note">快速建立判断框架</text>
      </view>
      <view class="summary-list">
        <view v-for="item in summaryCards" :key="item.id" class="summary-item">
          <text class="summary-index">{{ item.indexLabel }}</text>
          <text class="summary-text">{{ item.text }}</text>
        </view>
      </view>
    </view>

    <view class="insight-grid">
      <view class="impact-card card">
        <view class="module-title-row">
          <text class="module-icon">◎</text>
          <text class="mini-title">影响范围</text>
        </view>
        <view class="impact-tags">
          <text v-for="item in impactItems" :key="item" class="impact-tag">{{ item }}</text>
        </view>
      </view>
      <view class="timeline-card card">
        <view class="module-title-row">
          <text class="module-icon">↳</text>
          <text class="mini-title">时间线</text>
        </view>
        <view class="timeline">
          <view v-for="(item, index) in timelineItems" :key="item" class="timeline-item">
            <text class="timeline-marker">{{ index + 1 }}</text>
            <text class="timeline-step">{{ item }}</text>
          </view>
        </view>
      </view>
    </view>

    <view class="body-card card">
      <view v-for="section in article.sections" :key="section.heading" class="section">
        <text class="section-heading">{{ section.heading }}</text>
        <text class="section-body">{{ section.body }}</text>
      </view>
    </view>

    <view class="ask-card card">
      <view class="ask-title-row">
        <view>
          <text class="block-title">文章内 AI 助手</text>
          <text class="ask-desc">围绕这篇文章继续追问</text>
        </view>
        <text class="ask-mark">AI</text>
      </view>
      <view class="question-row">
        <button v-for="question in quickQuestions" :key="question.label" class="question-chip" @click="goAsk(question.value)">
          {{ question.label }}
        </button>
      </view>
      <view class="ask-input-row">
        <input v-model="draft" class="ask-input" placeholder="问问这件事" confirm-type="send" @confirm="goAsk(draft)" />
        <button class="send-button" @click="goAsk()">
          <text class="send-icon">↗</text>
          <text class="send-text">发送</text>
        </button>
      </view>
    </view>

    <view class="source-card card">
      <text class="block-title">来源与依据</text>
      <view v-for="source in article.references" :key="source.title" class="source-item">
        <view class="source-main">
          <view class="source-badges">
            <text class="source-level">官方来源</text>
            <text class="source-level muted">主要依据</text>
          </view>
          <text class="source-title">{{ source.title }}</text>
          <text class="source-line">{{ source.org }} · {{ source.date }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { deleteRemoteFavorite, getArticleDetail, getRemoteFavorite, saveRemoteFavorite, saveRemoteHistory } from '@/utils/api.js'
import { addArticleHistory, isArticleFavorite, markArticleRead as markArticleReadRecord, toggleArticleFavorite } from '@/utils/user-data.js'

const emptyArticle = {
  topic: '',
  title: '',
  readTime: '',
  sources: '',
  summary: [],
  sections: [],
  references: [],
  relation: ''
}

export default {
  data() {
    return {
      articleId: '',
      article: Object.assign({}, emptyArticle),
      quickQuestions: [
        { label: '问相关', value: '这和我有什么关系？' },
        { label: '说白话', value: '能不能讲得更简单？' },
        { label: '找依据', value: '依据在哪？' }
      ],
      draft: '',
      darkMode: false,
      fontSize: 'standard',
      showSources: true,
      isFavorite: false,
      lastFavoriteTapAt: 0,
      lastNavAction: '',
      lastNavActionAt: 0
    }
  },
  computed: {
    summaryCards() {
      return this.summaryItems.map((text, index) => ({
        id: `${index}-${text}`,
        indexLabel: index < 9 ? `0${index + 1}` : `${index + 1}`,
        text
      }))
    },
    summaryItems() {
      const items = this.article.summary && this.article.summary.length
        ? this.article.summary.slice(0, 3)
        : ['内容加载中', '请稍后查看', '以权威来源为准']
      while (items.length < 3) items.push('以权威来源为准')
      return items
    },
    impactItems() {
      if (this.article.relation) return this.article.relation.split('/').map(item => item.trim()).filter(Boolean)
      return ['普通用户', '本地居民', '相关从业者']
    },
    timelineItems() {
      return ['政策发布', '地方细则', '申请入口', '开始执行']
    }
  },
  onLoad(options) {
    this.articleId = options && options.id ? options.id : 'job'
    this.loadArticle()
  },
  onShow() {
    this.loadSettings()
    this.isFavorite = isArticleFavorite(this.articleId)
    this.refreshFavoriteStatus()
  },
  onReachBottom() {
    this.markArticleRead()
  },
  methods: {
    async loadArticle() {
      try {
        this.article = await getArticleDetail(this.articleId)
        this.addHistory()
      } catch (error) {
        uni.showToast({ title: error.message || '文章加载失败', icon: 'none' })
      }
    },
    addHistory() {
      markArticleReadRecord(this.articleId)
      addArticleHistory(this.articleId, this.article)
      if (uni.getStorageSync('jianwen_auth_token')) saveRemoteHistory(this.articleId, this.article).catch(() => {})
    },
    markArticleRead() {
      markArticleReadRecord(this.articleId)
      this.addHistory()
    },
    handleNavAction(action) {
      const now = Date.now()
      if (this.lastNavAction === action && now - this.lastNavActionAt < 160) return
      this.lastNavAction = action
      this.lastNavActionAt = now
      if (action === 'favorite') {
        this.lastFavoriteTapAt = now
        this.toggleFavorite()
        return
      }
      if (action === 'back') {
        this.goBack()
      }
    },
    toggleFavorite() {
      this.isFavorite = toggleArticleFavorite(this.articleId, this.article)
      if (uni.getStorageSync('jianwen_auth_token')) {
        const action = this.isFavorite ? saveRemoteFavorite(this.articleId, this.article) : deleteRemoteFavorite(this.articleId)
        action.catch(() => {})
      }
      uni.showToast({ title: this.isFavorite ? '已收藏' : '已取消收藏', icon: 'none' })
    },
    loadSettings() {
      const showSources = uni.getStorageSync('jianwen_show_sources')
      this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
      this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
      this.showSources = showSources === '' ? true : showSources !== false
    },
    async refreshFavoriteStatus() {
      if (!uni.getStorageSync('jianwen_auth_token')) return
      try {
        const favorite = await getRemoteFavorite(this.articleId)
        this.isFavorite = !!favorite
      } catch (error) {}
    },
    goBack() {
      if (Date.now() - this.lastFavoriteTapAt < 350) return
      uni.navigateBack({ fail: () => uni.switchTab({ url: '/pages/today/today' }) })
    },
    async goAsk(questionText = '') {
      if (!this.article.title) {
        uni.showToast({ title: '文章还在加载，请稍后再试', icon: 'none' })
        return
      }
      const finalQuestion = (questionText || this.draft || '').trim()
      this.markArticleRead()
      uni.setStorageSync('jianwen_pending_ask_context', {
        articleId: this.articleId,
        title: this.article.title,
        topic: this.article.topic || this.article.category || '',
        sources: this.article.sources || '',
        question: finalQuestion,
        from: 'article'
      })
      this.draft = ''
      uni.switchTab({
        url: '/pages/ask/ask',
        fail: () => uni.reLaunch({ url: '/pages/ask/ask' })
      })
    }
  }
}
</script>

<style scoped>
.article-page {
  padding-bottom: calc(92rpx + env(safe-area-inset-bottom));
  overflow: hidden;
}

.detail-nav {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 44rpx;
  margin-bottom: 42rpx;
}

.article-favorite-button {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 56rpx;
  color: #1F5F7A;
  line-height: 1;
}

.article-favorite-button {
  position: absolute;
  top: 0;
  right: 0;
  gap: 8rpx;
  min-width: 144rpx;
  padding: 0 20rpx;
  border: 1rpx solid #DCE5EA;
  border-radius: 999rpx;
  background: #FFFFFF;
  color: #6B7680;
}

.article-favorite-button.active {
  border-color: #F2B84B;
  background: #FFF6E3;
  color: #F2B84B;
}

.favorite-icon {
  font-size: 27rpx;
  line-height: 1;
}

.favorite-text {
  font-size: 24rpx;
  font-weight: 800;
  line-height: 1;
}

.title {
  color: #FFFFFF;
  font-size: 48rpx;
  line-height: 1.25;
  font-weight: 900;
}

.article-info {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.meta {
  color: rgba(255,255,255,0.82);
  font-size: 25rpx;
}

.body-card,
.source-card,
.impact-card,
.timeline-card {
  padding: 48rpx;
  margin-bottom: 44rpx;
}

.ask-card {
  padding: 30rpx 32rpx;
  margin-bottom: 38rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(244,250,250,0.76)),
    linear-gradient(135deg, rgba(31,95,122,0.08), rgba(212,170,78,0.1)) !important;
}

.block-title,
.mini-title {
  display: block;
  margin-bottom: 36rpx;
  color: #000000;
  font-size: 32rpx;
  font-weight: 800;
}

.impact-tags,
.question-row {
  display: flex;
  flex-wrap: wrap;
  gap: 22rpx;
}

.ask-card .block-title {
  margin-bottom: 22rpx;
  font-size: 28rpx;
}

.ask-card .question-row {
  flex-wrap: nowrap;
  gap: 12rpx;
  margin-bottom: 22rpx;
}

.impact-tag,
.question-chip {
  padding: 14rpx 20rpx;
  border-radius: 12rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 26rpx;
  font-weight: 800;
}

.ask-card .question-chip {
  flex: 1;
  min-width: 0;
  min-height: 54rpx;
  padding: 10rpx 16rpx;
  border-radius: 999rpx;
  font-size: 24rpx;
  line-height: 1.2;
  white-space: nowrap;
}

.timeline {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline::before {
  content: '';
  position: absolute;
  left: 20rpx;
  top: 18rpx;
  bottom: 18rpx;
  width: 2rpx;
  background: #DCE5EA;
}

.timeline-item {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 22rpx;
  padding-bottom: 30rpx;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-marker {
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 42rpx;
  width: 42rpx;
  height: 42rpx;
  border: 4rpx solid #FFFFFF;
  border-radius: 999rpx;
  background: #1F5F7A;
  color: #FFFFFF;
  font-size: 21rpx;
  font-weight: 900;
  line-height: 1;
}

.timeline-step {
  flex: 1;
  min-width: 0;
  padding-top: 4rpx;
  color: #2D3D47;
  font-size: 27rpx;
  line-height: 1.45;
  font-weight: 800;
}

.section {
  margin-bottom: 54rpx;
}

.section:last-child {
  margin-bottom: 0;
}

.section-heading {
  display: block;
  margin-bottom: 24rpx;
  color: #000000;
  font-size: 31rpx;
  font-weight: 800;
}

.section-body {
  display: block;
  color: #3F4F59;
  font-size: 30rpx;
  line-height: 1.9;
}

.ask-input-row {
  display: flex;
  gap: 12rpx;
  align-items: center;
  padding: 10rpx 12rpx;
  border: 1rpx solid #DCE5EA;
  border-radius: 12rpx;
  background: #F7FAFC;
}

.ask-input {
  flex: 1;
  min-height: 52rpx;
  color: #14212B;
  font-size: 25rpx;
}

.send-button {
  flex: 0 0 96rpx;
  min-height: 48rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  font-size: 23rpx;
  font-weight: 800;
  white-space: nowrap;
}

.source-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 34rpx;
  padding: 42rpx 0;
  border-top: 1rpx solid #E8EEF2;
}

.source-item > view {
  flex: 1;
  min-width: 0;
}

.source-item:first-of-type {
  border-top: none;
}

.source-level {
  display: inline-flex;
  margin-bottom: 16rpx;
  padding: 6rpx 12rpx;
  border-radius: 8rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 22rpx;
  font-weight: 800;
}

.source-title {
  display: block;
  margin-bottom: 16rpx;
  color: #000000;
  font-size: 27rpx;
  line-height: 1.45;
  font-weight: 700;
}

.dark-mode .article-favorite-button {
  border-color: #273847;
  background: #172331;
  color: #B6C2CC;
}

.dark-mode .article-favorite-button.active {
  border-color: #7A5A1F;
  background: #332916;
  color: #F2B84B;
}

.dark-mode .timeline::before {
  background: #273847;
}

.dark-mode .timeline-marker {
  border-color: #172331;
}

.dark-mode .timeline-step {
  color: #D7E2EA;
}

.detail-nav {
  justify-content: space-between;
  min-height: 72rpx;
  padding: 8rpx;
  margin: -22rpx -8rpx 28rpx;
  border: 1rpx solid rgba(255,255,255,0.74);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.58);
  box-shadow: 0 18rpx 42rpx rgba(31, 47, 58, 0.08);
}

.article-nav-button,
.article-favorite-button,
.question-chip,
.send-button,
.summary-index,
.module-icon,
.ask-mark {
  display: flex;
  align-items: center;
  justify-content: center;
}

.article-back-button {
  position: static;
  z-index: 2;
}

.article-favorite-button {
  position: static;
  z-index: 1;
  flex: 0 0 auto;
  margin: 0 0 0 auto;
  border-color: rgba(31,95,122,0.16);
  background: rgba(255,255,255,0.82);
  color: #5C6873;
}

.article-favorite-button.active {
  border-color: rgba(212,170,78,0.58);
  background: rgba(255,246,227,0.95);
  color: #A76A1D;
}

.article-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  padding: 42rpx 36rpx;
  margin-bottom: 38rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 32rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,255,255,0.58)),
    linear-gradient(135deg, rgba(245,235,207,0.92), rgba(226,240,244,0.82));
  box-shadow: 0 26rpx 70rpx rgba(48, 65, 72, 0.12);
}

.article-hero::after {
  content: '';
  position: absolute;
  right: -72rpx;
  top: -84rpx;
  width: 230rpx;
  height: 230rpx;
  border-radius: 999rpx;
  background: rgba(212,170,78,0.22);
  pointer-events: none;
}

.hero-topline,
.article-hero .title,
.article-hero .article-info {
  position: relative;
  z-index: 1;
}

.hero-topline,
.summary-head,
.module-title-row,
.ask-title-row,
.source-badges {
  display: flex;
  align-items: center;
}

.hero-topline {
  justify-content: space-between;
  gap: 20rpx;
}

.hero-kicker {
  color: #7C8790;
  font-size: 22rpx;
  font-weight: 800;
}

.article-hero .title {
  color: #000000;
  font-size: 46rpx;
  line-height: 1.28;
  font-weight: 900;
}

.article-hero .article-info {
  align-items: flex-start;
  gap: 14rpx;
}

.article-hero .meta {
  color: #5C6873;
  font-weight: 700;
}

.summary-card {
  position: relative;
  padding: 48rpx;
  margin-bottom: 34rpx;
  overflow: hidden;
}

.summary-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 8rpx;
  background: linear-gradient(180deg, #1F5F7A, #D4AA4E);
}

.summary-head {
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 30rpx;
}

.summary-head .block-title {
  margin-bottom: 0;
}

.summary-note,
.ask-desc {
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.4;
}

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
}

.summary-item {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  padding: 24rpx;
  border: 1rpx solid rgba(31,95,122,0.08);
  border-radius: 20rpx;
  background: rgba(230,240,244,0.52);
}

.summary-index {
  flex: 0 0 54rpx;
  width: 54rpx;
  height: 54rpx;
  border-radius: 16rpx;
  background: #1F5F7A;
  color: #FFFFFF;
  font-size: 22rpx;
  font-weight: 900;
  line-height: 1;
}

.summary-text {
  flex: 1;
  min-width: 0;
  color: #243540;
  font-size: 29rpx;
  line-height: 1.58;
  font-weight: 800;
}

.body-card,
.source-card,
.impact-card,
.timeline-card {
  margin-bottom: 34rpx;
}

.module-title-row {
  gap: 14rpx;
  margin-bottom: 30rpx;
}

.module-title-row .mini-title {
  margin-bottom: 0;
}

.module-icon {
  width: 42rpx;
  height: 42rpx;
  border-radius: 14rpx;
  background: rgba(212,170,78,0.18);
  color: #A76A1D;
  font-size: 24rpx;
  font-weight: 900;
}

.impact-tag,
.question-chip {
  border-radius: 999rpx;
}

.section {
  margin-bottom: 58rpx;
}

.section-heading {
  font-size: 32rpx;
  line-height: 1.36;
  font-weight: 900;
}

.section-body {
  line-height: 1.96;
}

.ask-card {
  padding: 34rpx 32rpx;
  margin-bottom: 34rpx;
}

.ask-title-row {
  justify-content: space-between;
  gap: 24rpx;
  margin-bottom: 24rpx;
}

.ask-card .block-title {
  margin-bottom: 8rpx;
}

.ask-mark {
  flex: 0 0 58rpx;
  width: 58rpx;
  height: 58rpx;
  border-radius: 18rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  font-size: 22rpx;
  font-weight: 900;
  box-shadow: 0 14rpx 30rpx rgba(31,95,122,0.2);
}

.ask-input-row {
  padding: 12rpx;
  border-radius: 18rpx;
  background: rgba(247,250,252,0.92);
}

.ask-input {
  min-width: 0;
  min-height: 58rpx;
}

.send-button {
  flex: 0 0 132rpx;
  align-items: center;
  justify-content: center;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 6rpx;
  width: 132rpx;
  min-height: 56rpx;
  border-radius: 14rpx;
  white-space: nowrap;
}

.send-icon {
  flex: 0 0 auto;
  font-size: 22rpx;
  line-height: 1;
}

.send-text {
  flex: 0 0 auto;
  white-space: nowrap;
}

.source-main {
  flex: 1;
  min-width: 0;
}

.source-badges {
  flex-wrap: wrap;
  gap: 10rpx;
  margin-bottom: 16rpx;
}

.source-level {
  margin-bottom: 0;
}

.source-level.muted {
  background: rgba(212,170,78,0.16);
  color: #A76A1D;
}

.font-large .article-hero .title {
  font-size: 50rpx;
}

.font-large .summary-text,
.font-large .section-body {
  font-size: 33rpx;
}

.font-large .section-heading {
  font-size: 35rpx;
}

.font-large .question-chip,
.font-large .send-button,
.font-large .favorite-text {
  font-size: 25rpx;
}

.font-small .article-hero .title {
  font-size: 42rpx;
}

.font-small .summary-text,
.font-small .section-body {
  font-size: 27rpx;
}

.font-small .section-heading {
  font-size: 29rpx;
}

.font-small .question-chip,
.font-small .send-button,
.font-small .favorite-text {
  font-size: 22rpx;
}

.dark-mode .detail-nav {
  border-color: rgba(126,184,209,0.14);
  background: rgba(23,35,49,0.72);
  box-shadow: 0 18rpx 42rpx rgba(0, 0, 0, 0.24);
}

.dark-mode .article-hero {
  border-color: rgba(126,184,209,0.14);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.94), rgba(17,27,39,0.76)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .article-hero::after {
  background: rgba(187,141,45,0.14);
}

.dark-mode .article-hero .title,
.dark-mode .block-title,
.dark-mode .mini-title,
.dark-mode .section-heading,
.dark-mode .source-title {
  color: #000000;
}

.dark-mode .summary-text {
  color: #F4F7FA;
}

.dark-mode .hero-kicker,
.dark-mode .article-hero .meta,
.dark-mode .summary-note,
.dark-mode .ask-desc {
  color: #B6C2CC;
}

.dark-mode .summary-item {
  border-color: #273847;
  background: rgba(32,56,74,0.64);
}

.dark-mode .summary-index,
.dark-mode .send-button {
  background: #1F5F7A;
}

.dark-mode .module-icon {
  background: rgba(187,141,45,0.14);
  color: #D4AA4E;
}

.dark-mode .ask-mark {
  background: linear-gradient(135deg, #1F5F7A, #20384A);
  box-shadow: 0 14rpx 30rpx rgba(0, 0, 0, 0.24);
}

.dark-mode .source-level.muted {
  background: rgba(187,141,45,0.14);
  color: #D4AA4E;
}
</style>
