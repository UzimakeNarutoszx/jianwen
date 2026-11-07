<template>
  <view :class="['page with-tabbar discover-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="discover-hero">
      <view class="hero-grid"></view>
      <view class="hero-head">
        <view class="hero-title-block">
          <text class="hero-kicker">DISCOVER</text>
          <text class="page-title">发现</text>
          <text class="subtle">按兴趣继续看懂公共议题</text>
        </view>
        <view class="hero-badge">
          <text class="hero-badge-number">{{ totalEntryCount }}</text>
          <text class="hero-badge-label">个入口</text>
        </view>
      </view>

      <view class="search-dock" @click="openSearch">
        <view class="search-icon-wrap">
          <image class="search-icon" src="/static/icons/icon-search.png" mode="aspectFit" />
        </view>
        <view class="search-copy">
          <text class="search-input">搜政策、新闻、话题</text>
          <text class="search-hint">热词：就业补贴、党章、AI技能、住房保障</text>
        </view>
        <image class="search-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
      </view>
    </view>

    <view class="section-head first-section">
      <view class="section-copy">
        <text class="section-eyebrow">TOPIC HALL</text>
        <text class="section-title inline-title">主题频道</text>
      </view>
      <text class="section-note">按议题进入</text>
    </view>
    <view class="topic-grid">
      <view v-for="(topic, index) in topics" :key="topic.name" class="topic-card card" @click="openCategory(topic.name)">
        <view class="topic-icon-wrap">
          <image v-if="topic.image" class="topic-image" :src="topic.image" mode="aspectFill" lazy-load />
          <text v-else class="topic-initial">{{ topicInitial(topic.name) }}</text>
        </view>
        <view class="topic-copy">
          <text class="topic-name">{{ topic.name }}</text>
        </view>
        <text v-if="topic.isPriority" class="topic-priority">重点</text>
      </view>
    </view>

    <view class="section-head">
      <view class="section-copy">
        <text class="section-eyebrow">BOOKSHELF</text>
        <text class="section-title inline-title">经典文献</text>
      </view>
      <text class="section-note">目录与权威阅读入口</text>
    </view>
    <scroll-view class="classic-shelf" scroll-x>
      <view class="classic-track">
        <view v-for="book in classicBooks" :key="book.bookId" class="classic-card card" @click="openClassic(book.bookId)">
          <view class="classic-cover-wrap">
            <image class="classic-cover" :src="book.coverImage" mode="aspectFill" lazy-load />
            <view class="classic-cover-shade"></view>
            <text class="classic-category">{{ book.category || '经典' }}</text>
          </view>
          <view class="classic-copy">
            <text class="classic-title">{{ book.title }}</text>
            <text class="classic-meta">{{ book.author }}</text>
            <text class="classic-desc">{{ book.description }}</text>
            <view class="classic-source-row">
              <text class="classic-source">{{ book.sourceOrg }}</text>
              <image class="classic-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
            </view>
          </view>
        </view>
      </view>
    </scroll-view>

    <view class="section-head">
      <view class="section-copy">
        <text class="section-eyebrow">SPECIAL FILES</text>
        <text class="section-title inline-title">专题</text>
      </view>
      <text class="section-note">成组理解</text>
    </view>
    <view class="feature-list">
      <view v-for="feature in features" :key="feature.id" class="feature-card card" @click="openCategory(feature.categoryName)">
        <image class="card-bg-image" :src="feature.image" mode="aspectFill" lazy-load />
        <view class="image-gradient"></view>
        <view class="feature-copy">
          <text class="feature-kicker">{{ feature.categoryName || '专题' }}</text>
          <text class="feature-title">{{ feature.title }}</text>
          <text class="feature-desc">{{ feature.desc }}</text>
          <text class="feature-tags">{{ feature.tags }}</text>
        </view>
      </view>
    </view>

    <view class="section-head">
      <view class="section-copy">
        <text class="section-eyebrow">LIVE UPDATE</text>
        <text class="section-title inline-title">最近更新</text>
      </view>
      <text class="section-note">刚更新 / 官方来源</text>
    </view>
    <view class="update-list">
      <StateView
        v-if="loadState !== 'ready' || !updates.length"
        :state="loadState === 'ready' ? 'empty' : loadState"
        :message="stateMessage"
        :dark-mode="darkMode"
        @retry="loadContent()"
      />
      <view v-for="(item, index) in updates" :key="item.id" class="update-item card" @click="openArticle(item.articleId)">
        <view class="update-rank">
          <text>{{ updateRank(index) }}</text>
        </view>
        <view class="update-copy">
          <view class="update-meta">
            <text class="update-chip fresh">刚更新</text>
            <text class="update-chip">{{ item.topic || item.category || '公共议题' }}</text>
          </view>
          <text class="update-title">{{ item.title }}</text>
          <view class="update-foot">
            <text class="source-line">{{ item.source }}</text>
            <text v-if="item.updateLabel" class="update-date">{{ item.updateLabel }}</text>
          </view>
        </view>
        <image class="update-thumb" :src="item.image" mode="aspectFill" lazy-load />
      </view>
    </view>

    <text class="page-end">资源有限，学习无止境</text>
  </view>
</template>

<script>
import { getClassicBooks, getDiscoverContent } from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import StateView from '@/components/StateView.vue'

export default {
  components: { StateView },
  data() {
    return {
      topics: [],
      darkMode: false,
      fontSize: 'standard',
      features: [],
      updates: [],
      classicBooks: [],
      loadState: 'loading',
      loadError: '',
      loadVersion: 0
    }
  },
  computed: {
    stateMessage() {
      if (this.loadState === 'loading') return '正在加载主题、经典与最新更新'
      if (this.loadState === 'error') return this.loadError || '发现内容暂时加载失败，请稍后重试'
      return '最近还没有新的更新，稍后再来看看'
    },
    totalEntryCount() {
      return this.topics.length + this.features.length + this.classicBooks.length
    }
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadContent()
    applyTabBarTheme(this.darkMode)
  },
  onPullDownRefresh() {
    this.loadContent().finally(() => uni.stopPullDownRefresh())
  },
  methods: {
    async loadContent() {
      const version = ++this.loadVersion
      // 有内容时不退回 loading 占位，下拉刷新只是静默重拉。
      const hasContent = this.updates.length > 0 || this.topics.length > 0
      if (!hasContent) {
        this.loadState = 'loading'
        this.loadError = ''
      }
      try {
        const [discover, books] = await Promise.all([getDiscoverContent(), getClassicBooks()])
        if (version !== this.loadVersion) return
        this.topics = discover.topics || []
        this.features = discover.features || []
        this.updates = discover.updates || []
        this.classicBooks = books || []
        this.loadState = 'ready'
      } catch (error) {
        if (version !== this.loadVersion) return
        if (hasContent) {
          uni.showToast({ title: error.message || '刷新失败，稍后再试', icon: 'none' })
          return
        }
        this.loadState = 'error'
        this.loadError = error.message || '发现内容加载失败，请稍后重试'
      }
    },
    openArticle(id) {
      uni.navigateTo({ url: `/pages/article/detail?id=${encodeURIComponent(id)}` })
    },
    openClassic(bookId) {
      uni.navigateTo({ url: `/pages/classics/detail?id=${encodeURIComponent(bookId)}` })
    },
    openCategory(name) {
      uni.navigateTo({ url: `/pages/category/category?name=${encodeURIComponent(name || '')}` })
    },
    openSearch() {
      uni.navigateTo({ url: '/pages/search/search' })
    },
    topicInitial(name) {
      return (name || '议').slice(0, 1)
    },
    topicDesc(topic, index) {
      if (topic.isPriority) return '优先理解的公共议题'
      const labels = ['政策脉络', '民生入口', '产业变化', '办事线索']
      return labels[index % labels.length]
    },
    updateRank(index) {
      return String(index + 1).padStart(2, '0')
    }
  }
}
</script>

<style scoped>
.discover-page {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 12% 0%, rgba(214, 184, 112, 0.3) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 90% 8%, rgba(31, 95, 122, 0.2) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 430rpx, #F5F7F4 100%);
}

.discover-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 30rpx;
  padding: 32rpx;
  margin: -18rpx -18rpx 54rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 34rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.5)),
    linear-gradient(135deg, rgba(245,235,207,0.86), rgba(226,240,244,0.76));
  box-shadow: 0 28rpx 78rpx rgba(48, 65, 72, 0.12);
}

.hero-grid {
  position: absolute;
  inset: 0;
  opacity: 0.24;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(31,95,122,0.08) 1rpx, transparent 1rpx),
    linear-gradient(90deg, rgba(31,95,122,0.08) 1rpx, transparent 1rpx);
  background-size: 58rpx 58rpx;
}

.hero-head,
.search-dock,
.topic-card,
.classic-source-row,
.section-head,
.update-item,
.update-rank,
.update-meta,
.hero-badge,
.search-icon-wrap,
.topic-icon-wrap {
  display: flex;
}

.hero-head {
  position: relative;
  z-index: 1;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
}

.hero-title-block,
.search-copy,
.topic-copy,
.classic-copy,
.feature-copy,
.update-copy,
.section-copy {
  display: flex;
  flex-direction: column;
}

.hero-title-block {
  gap: 10rpx;
  min-width: 0;
}

.hero-kicker,
.section-eyebrow,
.feature-kicker {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.hero-badge {
  flex: 0 0 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 116rpx;
  height: 116rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 28rpx;
  background: rgba(255,255,255,0.7);
  box-shadow: 0 16rpx 36rpx rgba(20, 33, 43, 0.08);
}

.hero-badge-number {
  color: #143E52;
  font-size: 38rpx;
  line-height: 1;
  font-weight: 900;
}

.hero-badge-label {
  margin-top: 8rpx;
  color: #66737B;
  font-size: 21rpx;
  line-height: 1.2;
  font-weight: 800;
}

.search-dock {
  position: relative;
  z-index: 1;
  align-items: center;
  gap: 22rpx;
  min-height: 126rpx;
  padding: 24rpx 26rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 26rpx;
  background: rgba(255,255,255,0.78);
  box-shadow: 0 18rpx 46rpx rgba(31, 47, 58, 0.09);
}

.search-icon-wrap {
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 74rpx;
  height: 74rpx;
  border-radius: 20rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
}

.search-icon {
  width: 34rpx;
  height: 34rpx;
  filter: brightness(0) invert(1);
}

.search-copy {
  flex: 1;
  min-width: 0;
  gap: 8rpx;
}

.search-input {
  color: #14212B;
  font-size: 29rpx;
  line-height: 1.35;
  font-weight: 900;
}

.search-hint {
  color: #6B7982;
  font-size: 22rpx;
  line-height: 1.45;
}

.search-arrow {
  flex: 0 0 auto;
  width: 30rpx;
  height: 30rpx;
  opacity: 0.58;
}

.first-section {
  margin-top: 0;
}

.section-head {
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  margin: 70rpx 0 30rpx;
}

.section-copy {
  gap: 8rpx;
  min-width: 0;
}

.inline-title {
  margin: 0;
}

.section-note {
  flex: 0 0 auto;
  color: #8A949E;
  font-size: 23rpx;
  line-height: 1.35;
}

.topic-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22rpx;
}

.topic-card {
  position: relative;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20rpx;
  min-height: 166rpx;
  padding: 26rpx;
  overflow: hidden;
  text-align: center;
}

.topic-card:active,
.classic-card:active,
.feature-card:active,
.update-item:active,
.search-dock:active {
  transform: scale(0.985);
  opacity: 0.92;
}

.topic-icon-wrap {
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 72rpx;
  height: 72rpx;
  border-radius: 20rpx;
  overflow: hidden;
  background: rgba(31,95,122,0.1);
}

.topic-image {
  width: 100%;
  height: 100%;
}

.topic-initial {
  color: #1F5F7A;
  font-size: 28rpx;
  line-height: 1;
  font-weight: 900;
}

.topic-copy {
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 10rpx;
}

.topic-name {
  display: block;
  width: 100%;
  color: #14212B;
  font-size: 28rpx;
  line-height: 1.3;
  font-weight: 900;
  text-align: center;
}

.topic-desc {
  color: #66737B;
  font-size: 22rpx;
  line-height: 1.4;
}

.topic-priority {
  position: absolute;
  right: 18rpx;
  bottom: 18rpx;
  padding: 6rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(212,170,78,0.16);
  color: #876112;
  font-size: 20rpx;
  line-height: 1.2;
  font-weight: 900;
}

.classic-shelf {
  width: 100%;
  white-space: nowrap;
}

.classic-track {
  display: inline-flex;
  gap: 24rpx;
  padding-right: 8rpx;
}

.classic-card {
  display: inline-flex;
  flex-direction: column;
  width: 318rpx;
  min-height: 486rpx;
  white-space: normal;
  overflow: hidden;
}

.classic-cover-wrap {
  position: relative;
  flex: 0 0 auto;
  height: 172rpx;
  overflow: hidden;
  background: #DCE5EA;
}

.classic-cover,
.classic-cover-shade {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.classic-cover-shade {
  background:
    linear-gradient(180deg, rgba(7, 22, 34, 0.06), rgba(7, 22, 34, 0.62)),
    linear-gradient(90deg, rgba(20, 62, 82, 0.56), rgba(20, 62, 82, 0.02));
}

.classic-category {
  position: absolute;
  left: 20rpx;
  bottom: 18rpx;
  max-width: 230rpx;
  padding: 7rpx 14rpx;
  border: 1rpx solid rgba(255,255,255,0.36);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.2);
  color: #FFFFFF;
  font-size: 20rpx;
  line-height: 1.25;
  font-weight: 900;
}

.classic-copy {
  flex: 1;
  gap: 12rpx;
  padding: 26rpx;
}

.classic-title {
  color: #14212B;
  font-size: 28rpx;
  line-height: 1.35;
  font-weight: 900;
}

.classic-meta,
.classic-source {
  color: #1F5F7A;
  font-size: 22rpx;
  font-weight: 800;
}

.classic-desc {
  flex: 1;
  color: #5C6873;
  font-size: 23rpx;
  line-height: 1.55;
}

.classic-source {
  color: #8A949E;
}

.classic-source-row {
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: auto;
}

.classic-arrow {
  width: 24rpx;
  height: 24rpx;
  opacity: 0.56;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 26rpx;
}

.feature-card {
  position: relative;
  min-height: 252rpx;
  padding: 38rpx;
  overflow: hidden;
}

.card-bg-image,
.image-gradient {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.image-gradient {
  background:
    linear-gradient(90deg, rgba(247,250,252,0.98), rgba(247,250,252,0.42) 58%, rgba(247,250,252,0.14)),
    linear-gradient(180deg, rgba(20,62,82,0.04), rgba(20,62,82,0.12));
}

.feature-copy {
  position: relative;
  z-index: 1;
  gap: 16rpx;
  max-width: 76%;
}

.feature-title {
  color: #14212B;
  font-size: 34rpx;
  line-height: 1.32;
  font-weight: 900;
}

.feature-desc,
.feature-tags {
  color: #3F4F59;
  font-size: 25rpx;
  line-height: 1.58;
}

.update-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.update-item {
  align-items: center;
  gap: 22rpx;
  min-height: 164rpx;
  padding: 24rpx;
}

.update-rank {
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 58rpx;
  height: 58rpx;
  border-radius: 18rpx;
  background: rgba(31,95,122,0.1);
}

.update-rank text {
  color: #1F5F7A;
  font-size: 24rpx;
  line-height: 1;
  font-weight: 900;
}

.update-copy {
  flex: 1;
  min-width: 0;
  gap: 12rpx;
}

.update-meta {
  flex-wrap: wrap;
  gap: 10rpx;
}

.update-chip {
  padding: 5rpx 12rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.09);
  color: #1F5F7A;
  font-size: 20rpx;
  line-height: 1.25;
  font-weight: 900;
}

.update-chip.fresh {
  background: rgba(212,170,78,0.16);
  color: #876112;
}

.update-title {
  color: #14212B;
  font-size: 28rpx;
  line-height: 1.42;
  font-weight: 900;
}

/* 发布日期来自接口的 published_date；缺失时整行不渲染。 */
.update-foot {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16rpx;
  min-width: 0;
}

.update-date {
  flex: 0 0 auto;
  color: #7C8790;
  font-size: 22rpx;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}

.update-thumb {
  flex: 0 0 auto;
  width: 118rpx;
  height: 118rpx;
  border-radius: 22rpx;
  background: #DCE5EA;
}

.page-end {
  display: block;
  margin-top: 54rpx;
  color: #8A949E;
  font-size: 24rpx;
  text-align: center;
}

.font-large .page-title {
  font-size: 50rpx;
}

.font-large .feature-title {
  font-size: 38rpx;
}

.font-large .topic-name,
.font-large .update-title {
  font-size: 31rpx;
}

.font-large .classic-title {
  font-size: 31rpx;
}

.font-small .page-title {
  font-size: 42rpx;
}

.font-small .feature-title {
  font-size: 31rpx;
}

.font-small .topic-name,
.font-small .update-title {
  font-size: 26rpx;
}

.font-small .classic-title {
  font-size: 26rpx;
}

.dark-mode.discover-page {
  background:
    radial-gradient(circle at 12% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 90% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .discover-hero {
  border-color: rgba(126,184,209,0.14);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .hero-grid {
  opacity: 0.16;
}

.dark-mode .search-dock,
.dark-mode .hero-badge,
.dark-mode .topic-card,
.dark-mode .classic-card,
.dark-mode .feature-card,
.dark-mode .update-item {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

.dark-mode .page-title,
.dark-mode .search-input,
.dark-mode .topic-name,
.dark-mode .classic-title,
.dark-mode .feature-title,
.dark-mode .update-title {
  color: #F4F7FA !important;
}

.dark-mode .subtle,
.dark-mode .hero-badge-label,
.dark-mode .search-hint,
.dark-mode .topic-desc,
.dark-mode .section-note,
.dark-mode .classic-desc,
.dark-mode .classic-source,
.dark-mode .feature-desc,
.dark-mode .feature-tags,
.dark-mode .source-line,
.dark-mode .update-date,
.dark-mode .page-end {
  color: #B6C2CC !important;
}

.dark-mode .hero-kicker,
.dark-mode .section-eyebrow,
.dark-mode .feature-kicker,
.dark-mode .topic-priority,
.dark-mode .update-chip.fresh {
  color: #D4AA4E !important;
}

.dark-mode .hero-badge-number,
.dark-mode .classic-meta,
.dark-mode .topic-initial,
.dark-mode .update-rank text,
.dark-mode .update-chip {
  color: #7EB8D1 !important;
}

.dark-mode .topic-icon-wrap,
.dark-mode .update-rank,
.dark-mode .update-chip {
  background: rgba(126,184,209,0.12) !important;
}

.dark-mode .topic-priority,
.dark-mode .update-chip.fresh {
  background: rgba(212,170,78,0.14) !important;
}

.dark-mode .image-gradient {
  background:
    linear-gradient(90deg, rgba(14,23,32,0.94), rgba(14,23,32,0.62) 58%, rgba(14,23,32,0.18)),
    linear-gradient(180deg, rgba(126,184,209,0.06), rgba(126,184,209,0.12));
}
</style>
