<template>
  <view :class="['page category-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="channel-hero">
      <view class="hero-grid"></view>
      <view class="hero-glow"></view>

      <view class="channel-topbar">
        <button class="back-button" @click="goBack">
          <text class="back-symbol"></text>
        </button>
        <view class="channel-label">
          <image class="channel-icon" src="/static/icons/func-topic.png" mode="aspectFit" />
          <text>专题频道</text>
        </view>
      </view>

      <view class="hero-main">
        <view class="hero-copy">
          <text class="hero-kicker">TOPIC BRIEFING</text>
          <text class="hero-title">{{ selectedCategory || '主题频道' }}</text>
          <text class="hero-desc">{{ channelDesc }}</text>
        </view>
        <view class="hero-stat">
          <text class="stat-number">{{ articles.length }}</text>
          <text class="stat-label">篇内容</text>
        </view>
      </view>

      <view class="hero-foot">
        <text class="hero-foot-item">按主题聚合</text>
        <text class="hero-foot-dot"></text>
        <text class="hero-foot-item">来源清晰</text>
        <text class="hero-foot-dot"></text>
        <text class="hero-foot-item">持续更新</text>
      </view>
    </view>

    <scroll-view class="category-scroll" scroll-x :show-scrollbar="false">
      <view class="category-track">
        <button v-for="item in categories" :key="item" :class="['category-chip', selectedCategory === item ? 'active' : '']" @click="selectCategory(item)">
          {{ item }}
        </button>
      </view>
    </scroll-view>

    <view class="article-list">
      <StateView
        v-if="loadState !== 'ready' || !articles.length"
        :state="loadState === 'ready' ? 'empty' : loadState"
        :message="stateMessage"
        :dark-mode="darkMode"
        @retry="loadContent()"
      />

      <view v-for="(item, index) in articles" :key="item.id" class="article-card card" @click="openArticle(item.articleId)">
        <view class="article-media">
          <image class="article-image" :src="item.image" mode="aspectFill" lazy-load />
          <view class="article-image-overlay"></view>
          <view class="article-index">
            <text>{{ articleRank(index) }}</text>
          </view>
        </view>
        <view class="article-copy">
          <view class="article-head">
            <text class="tag">{{ item.category }}</text>
            <text class="read-time">{{ item.readTime }}</text>
          </view>
          <text class="article-title">{{ item.title }}</text>
          <text class="article-desc">{{ item.desc }}</text>
          <text v-if="item.updateLabel" class="article-update-date">{{ item.updateLabel }}</text>
          <view class="article-foot">
            <text class="source-line">{{ item.source }}</text>
            <image class="foot-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
          </view>
        </view>
      </view>
    </view>

    <text class="page-end">已到底，继续换个主题看看</text>
  </view>
</template>

<script>
import { getArticleList, getCategories } from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import StateView from '@/components/StateView.vue'

export default {
  components: { StateView },
  data() {
    return {
      darkMode: false,
      fontSize: 'standard',
      selectedCategory: '',
      categories: [],
      articles: [],
      loadState: 'loading',
      loadError: '',
      loadVersion: 0
    }
  },
  computed: {
    stateMessage() {
      if (this.loadState === 'loading') return '正在加载这个主题的内容'
      if (this.loadState === 'error') return this.loadError || '主题内容暂时加载失败，请稍后重试'
      return '这个主题还在整理，可以先切换到其他主题继续浏览'
    },
    channelDesc() {
      const descriptions = {
        '党和国家': '从会议、文件、部门分工和地方落实看懂国家治理线索。',
        '共产党': '围绕组织体系、经典文献和基层治理建立基础框架。',
        '时政大事': '把权威发布、任务对象和后续执行入口放在一起看。',
        '就业': '聚合补贴、见习岗位、培训和本地就业服务入口。',
        '住房': '关注租房、买房、公积金和保障性住房的本地细则。',
        '科技': '从产业政策、技能训练和岗位变化理解科技议题。',
        '医保': '分清基金支付、报销规则和异地就医等关键入口。',
        '消费': '跟进补贴、价格、服务和日常消费相关公共信息。',
        '城市生活': '观察交通、社区、教育、医疗等公共服务变化。'
      }
      return descriptions[this.selectedCategory] || '按主题继续浏览相关内容，快速建立完整语境。'
    }
  },
  onLoad(options) {
    if (options && options.name) this.selectedCategory = decodeURIComponent(options.name)
  },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadContent()
    applyTabBarTheme(this.darkMode)
  },
  onPullDownRefresh() {
    this.loadContent({ silent: true }).finally(() => uni.stopPullDownRefresh())
  },
  methods: {
    async loadContent(options = {}) {
      const version = ++this.loadVersion
      // 切主题要显示 loading；下拉刷新走 silent，保留旧列表不闪。
      if (!options.silent) {
        this.loadState = 'loading'
        this.loadError = ''
      }
      try {
        const categories = await getCategories()
        if (version !== this.loadVersion) return
        this.categories = categories.map(item => item.name)
        if (!this.categories.includes(this.selectedCategory)) {
          const matched = this.categories.find(item => this.selectedCategory && (this.selectedCategory.includes(item) || item.includes(this.selectedCategory)))
          this.selectedCategory = matched || this.categories[0] || ''
        }
        const articles = this.selectedCategory ? await getArticleList({ category: this.selectedCategory }) : []
        if (version !== this.loadVersion) return
        this.articles = articles
        this.loadState = 'ready'
      } catch (error) {
        if (version !== this.loadVersion) return
        if (options.silent && this.articles.length) {
          uni.showToast({ title: error.message || '刷新失败，稍后再试', icon: 'none' })
          return
        }
        this.loadState = 'error'
        this.loadError = error.message || '主题内容加载失败，请稍后重试'
      }
    },
    selectCategory(category) {
      if (this.selectedCategory === category) return
      this.selectedCategory = category
      // 换主题时先清空，避免新主题加载中混着上一个主题的列表。
      this.articles = []
      this.loadContent()
    },
    openArticle(id) {
      uni.navigateTo({ url: `/pages/article/detail?id=${encodeURIComponent(id)}` })
    },
    articleRank(index) {
      return String(index + 1).padStart(2, '0')
    },
    goBack() {
      if (getCurrentPages().length > 1) {
        uni.navigateBack()
        return
      }
      uni.switchTab({ url: '/pages/discover/discover' })
    }
  }
}
</script>

<style scoped>
.category-page {
  position: relative;
  overflow: hidden;
}

.channel-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 34rpx;
  padding: 28rpx 28rpx 34rpx;
  margin: -24rpx -18rpx 42rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.86);
  border-radius: 36rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.52)),
    linear-gradient(135deg, rgba(245,235,207,0.9), rgba(226,240,244,0.76));
  box-shadow: 0 28rpx 80rpx rgba(48, 65, 72, 0.12);
}

.hero-grid,
.hero-glow {
  position: absolute;
  pointer-events: none;
}

.hero-grid {
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  opacity: 0.26;
  background-image:
    linear-gradient(rgba(31,95,122,0.08) 1rpx, transparent 1rpx),
    linear-gradient(90deg, rgba(31,95,122,0.08) 1rpx, transparent 1rpx);
  background-size: 64rpx 64rpx;
}

.hero-glow {
  top: -110rpx;
  right: -90rpx;
  width: 330rpx;
  height: 330rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.24);
}

.channel-topbar,
.hero-main,
.hero-foot,
.channel-label,
.article-head,
.article-foot {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
}

.channel-topbar {
  justify-content: space-between;
  gap: 24rpx;
}

.channel-label {
  gap: 10rpx;
  min-height: 54rpx;
  padding: 0 20rpx;
  border: 1rpx solid rgba(205, 165, 80, 0.34);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.7);
  color: #7C5C18;
  font-size: 23rpx;
  line-height: 1.3;
  font-weight: 900;
}

.channel-icon {
  width: 28rpx;
  height: 28rpx;
}

.hero-main {
  justify-content: space-between;
  gap: 26rpx;
}

.hero-copy {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  gap: 16rpx;
}

.hero-kicker {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.hero-title {
  color: #101D28;
  font-size: 56rpx;
  line-height: 1.12;
  font-weight: 900;
}

.hero-desc {
  color: #52616D;
  font-size: 26rpx;
  line-height: 1.62;
}

.hero-stat {
  display: flex;
  flex: 0 0 auto;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 132rpx;
  height: 132rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 28rpx;
  background: linear-gradient(135deg, rgba(31,95,122,0.94), rgba(18,55,75,0.9));
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.18);
}

.stat-number {
  color: #FFFFFF;
  font-size: 42rpx;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  margin-top: 10rpx;
  color: rgba(255,255,255,0.82);
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 800;
}

.hero-foot {
  flex-wrap: wrap;
  gap: 12rpx;
}

.hero-foot-item {
  color: #66737B;
  font-size: 23rpx;
  line-height: 1.35;
  font-weight: 800;
}

.hero-foot-dot {
  width: 8rpx;
  height: 8rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
}

.category-scroll {
  width: 100%;
  margin: 0 0 44rpx;
  border-radius: 999rpx;
  overflow: hidden;
  white-space: nowrap;
}

.category-track {
  display: inline-flex;
  gap: 10rpx;
  min-height: 86rpx;
  padding: 8rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.56);
  box-shadow: 0 16rpx 40rpx rgba(31, 47, 58, 0.08);
}

.category-chip {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  line-height: 1.4;
  min-height: 68rpx;
  padding: 0 30rpx;
  border: 0;
  border-radius: 999rpx;
  background: transparent;
  color: #52616D;
  font-size: 26rpx;
  font-weight: 800;
}

.category-chip.active {
  background: #1F5F7A;
  color: #FFFFFF;
  box-shadow: 0 14rpx 34rpx rgba(31, 95, 122, 0.18);
}

.article-list {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
}

.article-card {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 26rpx;
  padding: 26rpx;
  overflow: hidden;
}

.article-index {
  position: absolute;
  left: 16rpx;
  top: 16rpx;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 58rpx;
  height: 46rpx;
  border: 1rpx solid rgba(255,255,255,0.52);
  border-radius: 14rpx;
  background: rgba(255,255,255,0.24);
}

.article-index text {
  color: #FFFFFF;
  font-size: 22rpx;
  line-height: 1;
  font-weight: 900;
}

.article-media {
  position: relative;
  flex: 0 0 206rpx;
  width: 206rpx;
  min-height: 212rpx;
  border-radius: 22rpx;
  overflow: hidden;
  background: #DCE5EA;
}

.article-image,
.article-image-overlay {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.article-image-overlay {
  background:
    linear-gradient(180deg, rgba(10, 24, 34, 0.02), rgba(10, 24, 34, 0.48)),
    linear-gradient(90deg, rgba(10, 24, 34, 0.24), rgba(10, 24, 34, 0.02));
}

.article-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
}

.article-head {
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 20rpx;
}

.read-time {
  color: #8A949E;
  font-size: 23rpx;
  white-space: nowrap;
}

.article-title {
  display: block;
  color: #14212B;
  font-size: 31rpx;
  line-height: 1.42;
  font-weight: 900;
}

.article-desc {
  display: block;
  margin-top: 14rpx;
  color: #3F4F59;
  font-size: 25rpx;
  line-height: 1.55;
}

.article-foot {
  justify-content: space-between;
  gap: 18rpx;
  padding-top: 20rpx;
  margin-top: auto;
}

.source-line {
  flex: 1;
  min-width: 0;
}

.foot-arrow {
  flex: 0 0 auto;
  width: 28rpx;
  height: 28rpx;
  opacity: 0.5;
}

.page-end {
  display: block;
  margin-top: 54rpx;
  color: #8A949E;
  font-size: 24rpx;
  text-align: center;
}

.font-large .hero-title {
  font-size: 60rpx;
}

.font-large .article-title {
  font-size: 35rpx;
}

.font-large .article-card {
  gap: 22rpx;
}

.font-small .hero-title {
  font-size: 50rpx;
}

.font-small .article-title {
  font-size: 28rpx;
}

.dark-mode .channel-hero {
  border-color: rgba(126,184,209,0.12);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .hero-grid {
  opacity: 0.16;
}

.dark-mode .channel-label,
.dark-mode .category-track {
  border-color: rgba(126,184,209,0.16);
  background: rgba(23,35,49,0.76);
}

.dark-mode .hero-title,
.dark-mode .article-title {
  color: #F4F7FA !important;
}

.dark-mode .hero-desc,
.dark-mode .hero-foot-item,
.dark-mode .article-desc,
.dark-mode .read-time,
.dark-mode .source-line {
  color: #B6C2CC !important;
}

.dark-mode .channel-label {
  color: #D4AA4E;
}

.dark-mode .category-chip {
  color: #B6C2CC;
}

.dark-mode .category-chip.active {
  background: #1F5F7A;
  color: #FFFFFF;
}
</style>
