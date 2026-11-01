<template>
  <view :class="['page with-tabbar today-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="hero">
      <view class="hero-glow glow-a"></view>
      <view class="hero-glow glow-b"></view>
      <view class="hero-grid"></view>

      <view class="topbar">
        <view class="brand-lockup">
          <image class="brand-mark" src="/static/brand-icon.png" mode="aspectFit" />
          <view>
            <text class="brand-title">见闻</text>
            <text class="date-text">{{ todayText }}</text>
          </view>
        </view>
        <view class="today-pill">
          <text class="today-pill-dot"></text>
          <text class="today-pill-text">今日</text>
        </view>
      </view>

      <view class="hero-copy-block">
        <text class="hero-kicker">DAILY BRIEFING</text>
        <text class="hero-title">今天和你有关的几件事</text>
        <text class="hero-copy">用几分钟，看懂今天值得知道的公共变化。</text>
      </view>

      <view class="hero-stats">
        <view class="stat-chip primary">
          <text class="stat-value">{{ articles.length }}</text>
          <text class="stat-label">今日事项</text>
        </view>
        <view class="stat-chip">
          <text class="stat-value">{{ readCount }}</text>
          <text class="stat-label">已经读懂</text>
        </view>
        <view class="stat-chip">
          <text class="stat-value">{{ progressPercent }}%</text>
          <text class="stat-label">理解进度</text>
        </view>
      </view>

      <view v-if="majorEvent" class="major-event card" @click="openMajorEvent">
        <image class="major-event-image" :src="majorEventImage" mode="aspectFill" />
        <view class="major-event-body">
          <view class="major-event-eyebrow">
            <text>大事报道</text>
            <text :class="['major-event-badge', majorEvent.status === '已闭幕' ? 'is-closed' : '']">{{ majorEvent.status || '进行中' }}</text>
          </view>
          <text class="major-event-title">{{ majorEvent.event_name || majorEvent.title }}</text>
          <text class="major-event-summary">{{ majorEvent.summary }}</text>
          <text class="major-event-meta">{{ majorEventDates }} · {{ majorEvent.source_name }}</text>
        </view>
      </view>
      <swiper v-if="bannerItems.length" class="banner-swiper" indicator-dots circular autoplay interval="4200" duration="420">
        <swiper-item v-for="item in bannerItems" :key="item.id">
          <view class="banner-card" @click="openBanner(item)">
            <image class="banner-image" :src="item.image" mode="aspectFill" lazy-load />
            <view class="banner-overlay"></view>
            <view class="banner-content">
              <view class="banner-meta">
                <text class="banner-badge">重点简报</text>
                <image class="banner-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
              </view>
              <text class="banner-title">{{ item.title }}</text>
              <text class="banner-desc">{{ item.desc }}</text>
            </view>
          </view>
        </swiper-item>
      </swiper>
    </view>

    <view class="briefing-panel">
      <view v-if="dailyQuote" class="quote-card card">
        <view class="quote-accent"></view>
        <text class="quote-mark">“</text>
        <view class="quote-head">
          <view>
            <text class="quote-label">今日金句</text>
            <text class="quote-source">{{ quoteSource }}</text>
          </view>
          <view class="quote-tags">
            <text class="quote-type">{{ quoteTypeLabel }}</text>
            <text class="quote-theme">{{ dailyQuote.theme }}</text>
          </view>
        </view>
        <text class="quote-text">{{ dailyQuote.text }}</text>
        <view class="quote-explain">
          <text class="quote-subtitle">白话解释</text>
          <text class="quote-body">{{ dailyQuote.plainExplanation }}</text>
        </view>
        <view class="quote-explain">
          <text class="quote-subtitle">今日关联</text>
          <text class="quote-body">{{ dailyQuote.todayConnection }}</text>
        </view>
      </view>

      <view class="progress-card card">
        <view class="progress-orb" :style="progressOrbStyle">
          <image class="progress-icon" src="/static/icons/func-topic.png" mode="aspectFit" />
          <text class="progress-number">{{ progressPercent }}%</text>
        </view>
        <view class="progress-content">
          <view class="progress-title-row">
            <text class="progress-title">今日理解清单</text>
            <image class="progress-state-icon" src="/static/icons/func-history.png" mode="aspectFit" />
          </view>
          <text class="progress-desc">{{ progressDesc }}</text>
          <view class="progress-track">
            <view class="progress-fill" :style="progressFillStyle"></view>
          </view>
          <view class="progress-dots">
            <text v-for="item in articles" :key="item.id" :class="['progress-dot', item.viewed ? 'done' : '']"></text>
          </view>
        </view>
      </view>
    </view>

    <view class="article-list">
      <view class="article-section-head">
        <text class="section-eyebrow">TODAY FILES</text>
        <text class="section-heading">今日 briefing 卡片流</text>
      </view>

      <StateView
        v-if="loadState !== 'ready' || !articles.length"
        :state="loadState === 'ready' ? 'empty' : loadState"
        :message="stateMessage"
        :dark-mode="darkMode"
        @retry="loadContent()"
      />

      <view v-for="(item, index) in articles" :key="item.id" class="article-card card" @click="openArticle(item.id)">
        <view class="article-media">
          <image class="article-image" :src="item.image" mode="aspectFill" lazy-load />
          <view class="article-image-overlay"></view>
          <view class="article-rank">
            <text>{{ articleRank(index) }}</text>
          </view>
          <view class="article-topic">
            <text>{{ item.topic }}</text>
          </view>
        </view>
        <view class="card-head">
          <text class="tag">和我有关</text>
          <text :class="['read-state', item.viewed ? 'viewed' : '']">{{ item.viewed ? '已读' : '未读' }}</text>
        </view>
        <text class="article-title">{{ item.title }}</text>
        <view class="relation-row">
          <text class="relation-label">关联</text>
          <text class="relation-text">{{ item.relation }}</text>
        </view>
        <view class="card-foot">
          <text class="source-line">{{ item.sources }}</text>
          <view class="read-time-wrap">
            <text class="read-time">{{ item.readTime }}</text>
            <image class="foot-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
          </view>
        </view>
      </view>
    </view>

    <view class="today-end">
      <text class="subtle">今天就这些，明天再来。</text>
      <button class="ghost-button" @click="goDiscover">去发现看看更多</button>
    </view>
  </view>
</template>

<script>
import { buildFileUrl, getDailyQuote, getMajorEvents, getRemoteTodayChecklist, getTodayContent } from '@/utils/api.js'
import { formatToday } from '@/utils/date.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import { getReadArticleIds } from '@/utils/user-data.js'
import StateView from '@/components/StateView.vue'

// 60 秒内回到页面不重拉，避免 tab 切换反复打接口。
const RELOAD_INTERVAL_MS = 60000

export default {
  components: { StateView },
  data() {
    return {
      majorEvent: null,
      todayText: '',
      darkMode: false,
      fontSize: 'standard',
      articles: [],
      banners: [],
      dailyQuote: null,
      loadState: 'loading',
      loadError: '',
      lastLoadedAt: 0,
      loadVersion: 0
    }
  },
  computed: {
    stateMessage() {
      if (this.loadState === 'loading') return '正在整理今天值得知道的事'
      if (this.loadState === 'error') return this.loadError || '今日内容暂时加载失败，请稍后重试'
      return '今天还没有新内容，晚点再来看看'
    },
    majorEventImage() {
      return buildFileUrl((this.majorEvent && this.majorEvent.image) || '/static/images/共产党.jpg')
    },
    majorEventDates() {
      const item = this.majorEvent || {}
      if (item.start_date && item.end_date && item.start_date !== item.end_date) {
        return `${item.start_date} 至 ${item.end_date}`
      }
      return item.start_date || item.end_date || ''
    },
    readCount() { return this.articles.filter(item => item.viewed).length },
    isComplete() { return this.articles.length > 0 && this.readCount === this.articles.length },
    progressPercent() {
      if (!this.articles.length) return 0
      return Math.round((this.readCount / this.articles.length) * 100)
    },
    progressOrbStyle() {
      const degrees = Math.round((this.progressPercent / 100) * 360)
      const center = this.darkMode ? 'rgba(23,35,49,0.96)' : 'rgba(255,255,255,0.92)'
      const accent = this.darkMode ? '#7EB8D1' : '#1F5F7A'
      const track = this.darkMode ? 'rgba(126,184,209,0.16)' : 'rgba(31,95,122,0.12)'
      return {
        background: `radial-gradient(circle at 50% 50%, ${center} 0, ${center} 44rpx, transparent 46rpx), conic-gradient(#D4AA4E 0deg, ${accent} ${degrees}deg, ${track} ${degrees}deg)`
      }
    },
    progressFillStyle() {
      return { width: `${this.progressPercent}%` }
    },
    progressDesc() {
      return this.isComplete ? '今日清单已完成' : `今日 ${this.articles.length} 件事 · 已读 ${this.readCount} 件`
    },
    bannerItems() { return this.banners },
    quoteSource() {
      if (!this.dailyQuote) return ''
      return this.dailyQuote.sourceAuthor
        ? `${this.dailyQuote.sourceTitle} / ${this.dailyQuote.sourceAuthor}`
        : this.dailyQuote.sourceTitle
    },
    quoteTypeLabel() {
      const labels = {
        classical: '四书五经',
        ancient: '古代名言',
        red: '红色文献',
        manifesto: '共产党宣言'
      }
      return labels[this.dailyQuote?.sourceType] || '有出处'
    }
  },
  onShow() {
    this.todayText = formatToday()
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    // 60s 内刚成功加载过就不重拉；失败或过期才重新请求。
    const fresh = this.loadState === 'ready' && Date.now() - this.lastLoadedAt < RELOAD_INTERVAL_MS
    if (!fresh) this.loadContent()
    applyTabBarTheme(this.darkMode)
  },
  onPullDownRefresh() {
    this.loadContent().finally(() => uni.stopPullDownRefresh())
  },
  methods: {
    // 大事报道：失败就不显示，不影响今日内容。
    loadMajorEvent() {
      getMajorEvents()
        .then(items => { this.majorEvent = items[0] || null })
        .catch(() => { this.majorEvent = null })
    },
    // 打开官方原文：H5 新窗口；App 内用系统浏览器。
    openMajorEvent() {
      const url = this.majorEvent && this.majorEvent.source_url
      if (!url || !/^https:\/\//.test(url)) return
      // #ifdef H5
      window.open(url, '_blank', 'noopener')
      // #endif
      // #ifdef APP-PLUS
      plus.runtime.openURL(url)
      // #endif
      // #ifdef MP
      uni.setClipboardData({ data: url })
      uni.showToast({ title: '原文链接已复制', icon: 'none' })
      // #endif
    },
    async loadContent() {
      this.loadMajorEvent()
      const version = ++this.loadVersion
      // 已有内容时刷新不退回 loading 占位，避免列表整块闪一下。
      const hasContent = this.articles.length > 0
      if (!hasContent) {
        this.loadState = 'loading'
        this.loadError = ''
      }
      this.loadDailyQuote()
      const fallback = async () => {
        const data = await getTodayContent()
        const readIds = getReadArticleIds()
        return {
          articles: (data.articles || []).map(item => Object.assign({}, item, { viewed: readIds.includes(item.id) })),
          banners: data.banners || []
        }
      }
      try {
        let result
        if (uni.getStorageSync('jianwen_auth_token')) {
          try {
            result = await getRemoteTodayChecklist()
          } catch (error) {
            result = await fallback()
          }
        } else {
          result = await fallback()
        }
        if (version !== this.loadVersion) return
        this.articles = result.articles || []
        this.banners = result.banners || []
        this.loadState = 'ready'
        this.lastLoadedAt = Date.now()
      } catch (error) {
        if (version !== this.loadVersion) return
        // 已有内容时刷新失败保留旧列表，只提示；否则才切三态错误页。
        if (hasContent) {
          uni.showToast({ title: error.message || '刷新失败，稍后再试', icon: 'none' })
          return
        }
        this.loadState = 'error'
        this.loadError = error.message || '今日内容加载失败，请稍后重试'
      }
    },
    async loadDailyQuote() {
      try {
        this.dailyQuote = await getDailyQuote()
      } catch (error) {
        this.dailyQuote = null
      }
    },
    openArticle(id) {
      uni.navigateTo({ url: `/pages/article/detail?id=${id}` })
    },
    openBanner(item) {
      if (item.type === 'article') this.openArticle(item.articleId)
    },
    articleRank(index) {
      return String(index + 1).padStart(2, '0')
    },
    goDiscover() {
      uni.switchTab({ url: '/pages/discover/discover' })
    }
  }
}
</script>

<style scoped>
.today-page {
  position: relative;
  overflow: hidden;
  background:
    radial-gradient(circle at 18% 0%, rgba(214, 184, 112, 0.34) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 88% 12%, rgba(31, 95, 122, 0.24) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 460rpx, #F5F7F4 100%);
}

.hero,
.briefing-panel,
.article-list,
.today-end,
.brand-lockup,
.hero-copy-block {
  display: flex;
  flex-direction: column;
}

.hero {
  position: relative;
  gap: 34rpx;
  padding: 28rpx 28rpx 36rpx;
  margin: -24rpx -18rpx 44rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.86);
  border-radius: 36rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.48)),
    linear-gradient(135deg, rgba(245,235,207,0.9), rgba(226,240,244,0.78));
  box-shadow: 0 28rpx 80rpx rgba(48, 65, 72, 0.12);
}

.hero-glow,
.hero-grid {
  position: absolute;
  pointer-events: none;
}

.hero-glow {
  border-radius: 999rpx;
  filter: blur(2rpx);
}

.glow-a {
  top: -120rpx;
  right: -100rpx;
  width: 340rpx;
  height: 340rpx;
  background: rgba(212, 170, 78, 0.24);
}

.glow-b {
  left: -120rpx;
  bottom: 160rpx;
  width: 260rpx;
  height: 260rpx;
  background: rgba(31, 95, 122, 0.16);
}

.hero-grid {
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  opacity: 0.28;
  background-image:
    linear-gradient(rgba(31,95,122,0.08) 1rpx, transparent 1rpx),
    linear-gradient(90deg, rgba(31,95,122,0.08) 1rpx, transparent 1rpx);
  background-size: 64rpx 64rpx;
}

.topbar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24rpx;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  margin-bottom: 6rpx;
  overflow: visible;
  background: transparent;
  box-shadow: none;
  transform: translateY(18rpx);
}

.topbar::after {
  display: none;
}

.brand-lockup {
  flex-direction: row;
  align-items: center;
  gap: 18rpx;
  min-width: 0;
}

.brand-mark {
  flex: 0 0 auto;
  width: 58rpx;
  height: 58rpx;
  padding: 12rpx;
  border-radius: 18rpx;
  background: rgba(255,255,255,0.76);
  box-shadow: 0 14rpx 34rpx rgba(31, 95, 122, 0.14);
}

.brand-title {
  color: #122231;
  font-size: 44rpx;
  line-height: 1.12;
  font-weight: 900;
}

.date-text {
  display: block;
  margin-top: 8rpx;
  color: #687783;
  font-size: 23rpx;
  line-height: 1.35;
}

.today-pill {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10rpx;
  min-height: 54rpx;
  padding: 0 20rpx;
  border: 1rpx solid rgba(205, 165, 80, 0.34);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.7);
  box-shadow: 0 12rpx 30rpx rgba(155, 115, 46, 0.1);
}

.today-pill-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: #C89B39;
  box-shadow: 0 0 18rpx rgba(200, 155, 57, 0.72);
}

.today-pill-text {
  color: #7C5C18;
  font-size: 23rpx;
  line-height: 1.3;
  font-weight: 900;
}

.hero-copy-block {
  position: relative;
  z-index: 1;
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

.hero-copy {
  max-width: 560rpx;
  color: #52616D;
  font-size: 27rpx;
  line-height: 1.62;
}

.hero-stats {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 16rpx;
  width: 100%;
}

.stat-chip {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 6rpx;
  padding: 20rpx 18rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.64);
  box-shadow: 0 14rpx 34rpx rgba(20, 33, 43, 0.07);
}

.stat-chip.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.94), rgba(18,55,75,0.9));
}

.stat-value {
  color: #132A38;
  font-size: 32rpx;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  color: #6C7880;
  font-size: 20rpx;
  line-height: 1.25;
  font-weight: 700;
}

.stat-chip.primary .stat-value,
.stat-chip.primary .stat-label {
  color: #FFFFFF;
}

.banner-swiper {
  position: relative;
  z-index: 1;
  height: 360rpx;
}

.banner-card {
  position: relative;
  height: 360rpx;
  padding: 34rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 28rpx;
  overflow: hidden;
  background: #E2EAF0;
  box-shadow: 0 22rpx 54rpx rgba(20, 33, 43, 0.14);
}

.banner-card:active,
.article-card:active,
.ghost-button:active {
  transform: scale(0.985);
  opacity: 0.92;
}

.banner-image,
.banner-overlay {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.banner-overlay {
  background:
    linear-gradient(180deg, rgba(6, 21, 32, 0.08), rgba(6, 21, 32, 0.64)),
    linear-gradient(90deg, rgba(15, 44, 61, 0.8), rgba(15, 44, 61, 0.1));
}

.banner-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 100%;
}

.banner-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: auto;
}

.banner-badge {
  padding: 8rpx 16rpx;
  border: 1rpx solid rgba(255,255,255,0.36);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.2);
  color: #FFFFFF;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.banner-arrow {
  width: 34rpx;
  height: 34rpx;
  padding: 10rpx;
  border-radius: 999rpx;
  background: rgba(255,255,255,0.78);
}

.banner-title {
  color: #FFFFFF;
  font-size: 36rpx;
  line-height: 1.28;
  font-weight: 900;
}

.banner-desc {
  margin-top: 14rpx;
  color: rgba(255,255,255,0.84);
  font-size: 24rpx;
  line-height: 1.45;
}

.briefing-panel {
  gap: 30rpx;
  margin-bottom: 58rpx;
}

.quote-card,
.progress-card,
.article-card {
  border-color: rgba(255,255,255,0.88);
  border-radius: 28rpx;
  background: rgba(255,255,255,0.82);
  box-shadow: 0 24rpx 60rpx rgba(31, 47, 58, 0.1);
}

.quote-card {
  position: relative;
  padding: 42rpx 38rpx 40rpx;
  overflow: hidden;
}

.quote-accent {
  position: absolute;
  top: 0;
  left: 0;
  width: 10rpx;
  height: 100%;
  background: linear-gradient(180deg, #D4AA4E, #1F5F7A);
}

.quote-mark {
  position: absolute;
  top: -22rpx;
  right: 30rpx;
  color: rgba(212, 170, 78, 0.18);
  font-size: 160rpx;
  line-height: 1;
  font-weight: 900;
}

.quote-head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 22rpx;
  margin-bottom: 26rpx;
}

.quote-label {
  display: block;
  color: #1F5F7A;
  font-size: 24rpx;
  line-height: 1.35;
  font-weight: 900;
}

.quote-source {
  display: block;
  max-width: 400rpx;
  margin-top: 8rpx;
  color: #7C8790;
  font-size: 22rpx;
  line-height: 1.45;
}

.quote-tags {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10rpx;
  max-width: 260rpx;
}

.quote-type,
.quote-theme {
  padding: 7rpx 15rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.09);
  color: #1F5F7A;
  font-size: 21rpx;
  line-height: 1.3;
  font-weight: 900;
}

.quote-theme {
  background: rgba(212, 170, 78, 0.16);
  color: #876112;
}

.quote-text {
  position: relative;
  z-index: 1;
  display: block;
  color: #121E29;
  font-size: 38rpx;
  line-height: 1.5;
  font-weight: 900;
}

.quote-explain {
  position: relative;
  z-index: 1;
  margin-top: 30rpx;
  padding-top: 26rpx;
  border-top: 1rpx solid rgba(31,95,122,0.12);
}

.quote-subtitle {
  display: block;
  margin-bottom: 10rpx;
  color: #163F54;
  font-size: 23rpx;
  line-height: 1.35;
  font-weight: 900;
}

.quote-body {
  display: block;
  color: #52616D;
  font-size: 26rpx;
  line-height: 1.68;
}

.progress-card {
  display: flex;
  align-items: center;
  gap: 26rpx;
  padding: 34rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(244,250,250,0.76)),
    linear-gradient(135deg, rgba(31,95,122,0.08), rgba(212,170,78,0.1));
}

.progress-orb {
  position: relative;
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 128rpx;
  height: 128rpx;
  border-radius: 999rpx;
  background:
    radial-gradient(circle at 50% 50%, rgba(255,255,255,0.92) 0, rgba(255,255,255,0.92) 44rpx, transparent 46rpx),
    conic-gradient(#D4AA4E 0deg, #1F5F7A 240deg, rgba(31,95,122,0.12) 240deg);
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.16);
}

.progress-icon {
  position: absolute;
  top: 24rpx;
  width: 30rpx;
  height: 30rpx;
  opacity: 0.72;
}

.progress-number {
  margin-top: 28rpx;
  color: #163F54;
  font-size: 28rpx;
  line-height: 1;
  font-weight: 900;
}

.progress-content {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 14rpx;
}

.progress-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  width: 100%;
}

.progress-title {
  color: #14212B;
  font-size: 29rpx;
  line-height: 1.25;
  font-weight: 900;
}

.progress-state-icon {
  width: 34rpx;
  height: 34rpx;
  opacity: 0.72;
}

.progress-desc {
  color: #66737B;
  font-size: 24rpx;
  line-height: 1.4;
}

.progress-track {
  position: relative;
  width: 100%;
  height: 14rpx;
  border-radius: 999rpx;
  overflow: hidden;
  background: rgba(31,95,122,0.1);
}

.progress-fill {
  height: 100%;
  min-width: 10rpx;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #D4AA4E, #1F5F7A);
  box-shadow: 0 0 20rpx rgba(212, 170, 78, 0.42);
}

.progress-dots {
  display: flex;
  align-items: center;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 12rpx;
  height: 24rpx;
}

.progress-dot {
  width: 14rpx;
  height: 14rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.18);
}

.progress-dot.done {
  width: 32rpx;
  background: #1F5F7A;
}

.article-list {
  gap: 34rpx;
}

.article-section-head {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin-bottom: 4rpx;
}

.section-eyebrow {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.section-heading {
  color: #14212B;
  font-size: 36rpx;
  line-height: 1.3;
  font-weight: 900;
}

.article-card {
  padding: 0 0 34rpx;
  overflow: hidden;
}

.article-media {
  position: relative;
  height: 292rpx;
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
    linear-gradient(180deg, rgba(10, 24, 34, 0.04), rgba(10, 24, 34, 0.58)),
    linear-gradient(90deg, rgba(10, 24, 34, 0.44), rgba(10, 24, 34, 0.04));
}

.article-rank {
  position: absolute;
  left: 28rpx;
  bottom: 24rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 84rpx;
  height: 70rpx;
  border: 1rpx solid rgba(255,255,255,0.52);
  border-radius: 18rpx;
  background: rgba(255,255,255,0.18);
}

.article-rank text {
  color: #FFFFFF;
  font-size: 32rpx;
  line-height: 1;
  font-weight: 900;
}

.article-topic {
  position: absolute;
  top: 24rpx;
  right: 24rpx;
  padding: 8rpx 16rpx;
  border: 1rpx solid rgba(255,255,255,0.46);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.22);
}

.article-topic text {
  color: #FFFFFF;
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.card-head,
.card-foot,
.relation-row,
.read-time-wrap {
  display: flex;
  align-items: center;
}

.card-head {
  justify-content: space-between;
  gap: 24rpx;
  padding: 34rpx 34rpx 0;
}

.tag {
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
}

.read-state,
.read-time {
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.35;
  font-weight: 800;
}

.read-state {
  padding: 6rpx 14rpx;
  border-radius: 999rpx;
  background: rgba(124,135,144,0.1);
}

.read-state.viewed {
  color: #1F5F7A;
  background: rgba(31,95,122,0.12);
}

.article-title {
  display: block;
  padding: 0 34rpx;
  margin-top: 28rpx;
  color: #14212B;
  font-size: 36rpx;
  line-height: 1.35;
  font-weight: 900;
}

.relation-row {
  gap: 18rpx;
  padding: 0 34rpx;
  margin-top: 30rpx;
}

.relation-label {
  flex: 0 0 auto;
  padding: 7rpx 14rpx;
  border-radius: 10rpx;
  background: rgba(212, 170, 78, 0.16);
  color: #876112;
  font-size: 22rpx;
  font-weight: 900;
}

.relation-text {
  flex: 1;
  min-width: 0;
  color: #52616D;
  font-size: 24rpx;
  line-height: 1.5;
}

.card-foot {
  justify-content: space-between;
  gap: 22rpx;
  padding: 28rpx 34rpx 0;
  margin-top: 30rpx;
  border-top: 1rpx solid rgba(31,95,122,0.1);
}

.source-line {
  flex: 1;
  min-width: 0;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.45;
}

.read-time-wrap {
  flex: 0 0 auto;
  gap: 8rpx;
}

.foot-arrow {
  width: 24rpx;
  height: 24rpx;
  opacity: 0.54;
}

.today-end {
  display: flex;
  flex-direction: column;
  gap: 28rpx;
  align-items: center;
  margin-top: 62rpx;
}

.ghost-button {
  border-color: rgba(31,95,122,0.2);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.72);
  box-shadow: 0 16rpx 36rpx rgba(20, 33, 43, 0.08);
}

.font-large .hero-title {
  font-size: 60rpx;
}

.font-large .quote-text {
  font-size: 42rpx;
}

.font-large .quote-body,
.font-large .relation-text {
  font-size: 30rpx;
}

.font-large .article-title {
  font-size: 40rpx;
}

.font-small .hero-title {
  font-size: 50rpx;
}

.font-small .quote-text {
  font-size: 34rpx;
}

.font-small .quote-body,
.font-small .relation-text {
  font-size: 24rpx;
}

.font-small .article-title {
  font-size: 32rpx;
}

.dark-mode.today-page {
  background:
    radial-gradient(circle at 18% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 88% 12%, rgba(75, 154, 187, 0.18) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .hero {
  border-color: rgba(126, 184, 209, 0.12);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .hero-grid {
  opacity: 0.16;
}

.dark-mode .brand-title,
.dark-mode .hero-title,
.dark-mode .section-heading,
.dark-mode .quote-text,
.dark-mode .progress-title,
.dark-mode .article-title {
  color: #F4F7FA !important;
}

.dark-mode .date-text,
.dark-mode .hero-copy,
.dark-mode .quote-source,
.dark-mode .quote-body,
.dark-mode .progress-desc,
.dark-mode .relation-text,
.dark-mode .source-line,
.dark-mode .read-time {
  color: #B6C2CC !important;
}

.dark-mode .brand-mark,
.dark-mode .today-pill,
.dark-mode .stat-chip,
.dark-mode .quote-card,
.dark-mode .progress-card,
.dark-mode .article-card,
.dark-mode .ghost-button {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

.dark-mode .stat-chip.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.9), rgba(16,39,55,0.94)) !important;
}

.dark-mode .stat-value,
.dark-mode .progress-number,
.dark-mode .quote-label,
.dark-mode .quote-subtitle,
.dark-mode .section-eyebrow,
.dark-mode .quote-type {
  color: #7EB8D1 !important;
}

.dark-mode .stat-label,
.dark-mode .read-state {
  color: #B6C2CC !important;
}

.dark-mode .quote-theme,
.dark-mode .relation-label,
.dark-mode .today-pill-text {
  color: #D4AA4E !important;
}

.dark-mode .quote-type,
.dark-mode .tag,
.dark-mode .read-state.viewed {
  background: rgba(126,184,209,0.12) !important;
  color: #7EB8D1 !important;
}

.dark-mode .quote-theme,
.dark-mode .relation-label {
  background: rgba(212,170,78,0.14) !important;
}

.dark-mode .quote-explain,
.dark-mode .card-foot {
  border-top-color: rgba(126,184,209,0.14) !important;
}

.dark-mode .progress-track {
  background: rgba(126,184,209,0.14) !important;
}

.dark-mode .progress-orb {
  background:
    radial-gradient(circle at 50% 50%, rgba(23,35,49,0.96) 0, rgba(23,35,49,0.96) 44rpx, transparent 46rpx),
    conic-gradient(#D4AA4E 0deg, #7EB8D1 240deg, rgba(126,184,209,0.16) 240deg);
}

.major-event {
  display: flex;
  gap: 24rpx;
  align-items: center;
  margin: 28rpx 0 8rpx;
  padding: 24rpx;
  border-radius: 28rpx;
}
.major-event-image {
  flex: 0 0 200rpx;
  width: 200rpx;
  height: 150rpx;
  border-radius: 18rpx;
}
.major-event-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
}
.major-event-eyebrow {
  display: flex;
  align-items: center;
  gap: 14rpx;
  color: #B5413A;
  font-size: 24rpx;
  letter-spacing: 2rpx;
}
.major-event-badge {
  padding: 2rpx 14rpx;
  border-radius: 999rpx;
  background: #B5413A;
  color: #FFFFFF;
  font-size: 22rpx;
  letter-spacing: 0;
}
.major-event-badge.is-closed {
  background: #6C7880;
}
.major-event-title {
  font-size: 32rpx;
  font-weight: 700;
  line-height: 1.4;
}
.major-event-summary {
  color: #4B5A63;
  font-size: 26rpx;
  line-height: 1.65;
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.major-event-meta {
  color: #6C7880;
  font-size: 22rpx;
  font-variant-numeric: tabular-nums;
}
.dark-mode .major-event-summary {
  color: #B9C4CC;
}
.dark-mode .major-event-meta {
  color: #8E9AA3;
}
.dark-mode .major-event-eyebrow {
  color: #E08A82;
}
.dark-mode .major-event-title {
  font-weight: 420;
}
</style>
