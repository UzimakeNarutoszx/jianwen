<template>
  <view :class="['page search-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="search-console">
      <view class="search-toolbar card">
        <button class="back-button" @click="goBack">
          <text class="back-symbol"></text>
        </button>
        <view class="search-field">
          <image class="search-icon" src="/static/icons/icon-search.png" mode="aspectFit" />
          <input
            v-model="keyword"
            class="search-input"
            focus
            placeholder="搜政策、新闻、话题"
            confirm-type="search"
            @confirm="loadArticles"
          />
          <button v-if="hasKeyword" class="clear-button" @click.stop="clearKeyword">
            <text class="clear-mark">×</text>
          </button>
        </view>
      </view>

      <view class="console-copy">
        <text class="console-kicker">INFORMATION SEARCH</text>
        <text class="console-title">信息检索台</text>
        <text class="console-desc">{{ consoleDesc }}</text>
      </view>

      <view class="console-stats">
        <view class="stat-cell primary">
          <text class="stat-value">{{ articles.length }}</text>
          <text class="stat-label">{{ hasKeyword ? '匹配文章' : '推荐文章' }}</text>
        </view>
        <view class="stat-cell">
          <text class="stat-value">{{ hasKeyword ? '检索' : '热词' }}</text>
          <text class="stat-label">{{ hasKeyword ? '当前模式' : '快速入口' }}</text>
        </view>
      </view>
    </view>

    <view v-if="!hasKeyword" class="quick-panel">
      <view class="panel-head">
        <text class="section-eyebrow">QUICK START</text>
        <text class="section-heading">推荐热词</text>
      </view>
      <view class="chip-row">
        <view v-for="(row, rowIndex) in hotKeywordRows" :key="`hot-row-${rowIndex}`" class="chip-line">
          <button v-for="word in row" :key="word" class="query-chip" @click="useKeyword(word)">
            <text>{{ word }}</text>
          </button>
        </view>
      </view>
    </view>

    <view class="result-head">
      <view>
        <text class="section-eyebrow">{{ hasKeyword ? 'SEARCH RESULT' : 'RECOMMENDED' }}</text>
        <text class="result-title">{{ resultTitle }}</text>
      </view>
      <text class="result-note">{{ resultNote }}</text>
    </view>

    <view v-if="displayArticles.length" class="article-list">
      <view
        v-for="(item, index) in displayArticles"
        :key="item.id"
        class="article-card card"
        @click="openArticle(item.articleId || item.id)"
      >
        <view class="article-rank">
          <text>{{ articleRank(index) }}</text>
        </view>
        <image class="article-image" :src="item.image" mode="aspectFill" />
        <view class="article-copy">
          <view class="article-head">
            <text class="tag">{{ item.category || item.topic }}</text>
            <text class="read-time">{{ item.readTime }}</text>
          </view>
          <view class="article-title">
            <text
              v-for="(part, partIndex) in item.titleSegments"
              :key="'title-' + item.id + '-' + partIndex"
              :class="part.match ? 'highlight-text' : ''"
            >{{ part.text }}</text>
          </view>
          <view class="article-desc">
            <text
              v-for="(part, partIndex) in item.descSegments"
              :key="'desc-' + item.id + '-' + partIndex"
              :class="part.match ? 'highlight-text' : ''"
            >{{ part.text }}</text>
          </view>
          <view class="card-foot">
            <text class="source-line">{{ item.source || item.sources }}</text>
            <image class="foot-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
          </view>
        </view>
      </view>
    </view>

    <view v-else-if="hasKeyword" class="empty-card card">
      <image class="empty-icon" src="/static/icons/icon-search.png" mode="aspectFit" />
      <text class="empty-title">没有找到相关文章</text>
      <text class="empty-desc">换一个关键词试试，例如“就业”“住房”“医保”。</text>
      <view class="empty-chips">
        <button v-for="word in fallbackKeywords" :key="word" class="query-chip compact" @click="useKeyword(word)">
          <text>{{ word }}</text>
        </button>
      </view>
      <button class="primary-button discover-button" @click="goDiscover">去发现页看看</button>
    </view>
  </view>
</template>

<script>
import { getArticleList } from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'

export default {
  data() {
    return {
      keyword: '',
      darkMode: false,
      fontSize: 'standard',
      articles: [],
      hotKeywords: ['党和国家', '共产党', '时政大事', '就业', '住房', '科技', '医保', '消费', '城市生活'],
      fallbackKeywords: ['就业', '住房', '医保']
    }
  },
  computed: {
    hasKeyword() {
      return !!this.keyword.trim()
    },
    displayArticles() {
      return this.articles.map(item => Object.assign({}, item, {
        titleSegments: this.highlightSegments(item.title),
        descSegments: this.highlightSegments(item.desc)
      }))
    },
    hotKeywordRows() {
      return [
        this.hotKeywords.slice(0, 3),
        this.hotKeywords.slice(3, 7),
        this.hotKeywords.slice(7)
      ]
    },
    consoleDesc() {
      return this.hasKeyword
        ? `正在检索“${this.keyword.trim()}”相关内容`
        : '输入关键词，或从热词开始查看公共议题。'
    },
    resultTitle() {
      return this.hasKeyword ? `搜索结果 ${this.articles.length} 篇` : '推荐文章'
    },
    resultNote() {
      return this.hasKeyword ? '按相关内容快速浏览' : '先从高频议题进入'
    }
  },
  watch: {
    keyword() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.loadArticles(), 300)
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
      try {
        this.articles = await getArticleList({ q: this.keyword.trim() })
      } catch (error) {
        uni.showToast({ title: error.message || '搜索内容加载失败', icon: 'none' })
      }
    },
    highlightSegments(text) {
      const source = `${text || ''}`
      const keyword = this.keyword.trim()
      if (!keyword) return [{ text: source, match: false }]

      const lowerSource = source.toLowerCase()
      const lowerKeyword = keyword.toLowerCase()
      const segments = []
      let cursor = 0
      let matchIndex = lowerSource.indexOf(lowerKeyword)

      while (matchIndex !== -1) {
        if (matchIndex > cursor) {
          segments.push({ text: source.slice(cursor, matchIndex), match: false })
        }
        segments.push({ text: source.slice(matchIndex, matchIndex + keyword.length), match: true })
        cursor = matchIndex + keyword.length
        matchIndex = lowerSource.indexOf(lowerKeyword, cursor)
      }

      if (cursor < source.length) {
        segments.push({ text: source.slice(cursor), match: false })
      }

      return segments.length ? segments : [{ text: source, match: false }]
    },
    clearKeyword() {
      this.keyword = ''
    },
    useKeyword(word) {
      this.keyword = word
    },
    openArticle(id) {
      uni.navigateTo({ url: `/pages/article/detail?id=${id}` })
    },
    articleRank(index) {
      return String(index + 1).padStart(2, '0')
    },
    goDiscover() {
      uni.switchTab({ url: '/pages/discover/discover' })
    },
    goBack() {
      uni.navigateBack()
    }
  }
}
</script>

<style scoped>
.search-page {
  overflow: hidden;
}

.search-console {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 30rpx;
  padding: 28rpx 28rpx 34rpx;
  margin: -24rpx -18rpx 46rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.84);
  border-radius: 34rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.5)),
    linear-gradient(135deg, rgba(245,235,207,0.86), rgba(226,240,244,0.72));
  box-shadow: 0 28rpx 78rpx rgba(48, 65, 72, 0.12);
}

.search-console::after {
  content: '';
  position: absolute;
  top: -94rpx;
  right: -64rpx;
  width: 240rpx;
  height: 240rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.2);
  pointer-events: none;
}

.search-toolbar,
.search-field,
.console-copy,
.console-stats,
.stat-cell,
.quick-panel,
.panel-head,
.result-head,
.article-list,
.article-card,
.article-copy,
.article-head,
.card-foot,
.empty-card,
.empty-chips {
  display: flex;
}

.search-toolbar {
  position: relative;
  z-index: 1;
  align-items: center;
  gap: 18rpx;
  min-height: 108rpx;
  padding: 16rpx;
  border-radius: 28rpx;
  background: rgba(255,255,255,0.7) !important;
}

.search-field {
  flex: 1;
  align-items: center;
  gap: 20rpx;
  min-width: 0;
  min-height: 76rpx;
  padding: 0 22rpx;
  border: 1rpx solid rgba(31,95,122,0.08);
  border-radius: 22rpx;
  background: rgba(255,255,255,0.72);
}

.search-icon {
  flex: 0 0 auto;
  width: 36rpx;
  height: 36rpx;
}

.search-input {
  flex: 1;
  min-width: 0;
  color: #14212B;
  font-size: 29rpx;
  font-weight: 800;
}

.clear-button {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 44rpx;
  height: 44rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
}

.clear-mark {
  color: #1F5F7A;
  font-size: 34rpx;
  line-height: 1;
  font-weight: 700;
}

.console-copy {
  position: relative;
  z-index: 1;
  flex-direction: column;
  gap: 14rpx;
}

.console-kicker,
.section-eyebrow {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
}

.console-title {
  color: #101D28;
  font-size: 50rpx;
  line-height: 1.16;
  font-weight: 900;
}

.console-desc {
  color: #52616D;
  font-size: 26rpx;
  line-height: 1.55;
}

.console-stats {
  position: relative;
  z-index: 1;
  gap: 16rpx;
}

.stat-cell {
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 7rpx;
  padding: 20rpx 22rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.64);
  box-shadow: 0 14rpx 34rpx rgba(20, 33, 43, 0.07);
}

.stat-cell.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.94), rgba(18,55,75,0.9));
}

.stat-value {
  color: #132A38;
  font-size: 31rpx;
  line-height: 1.1;
  font-weight: 900;
}

.stat-label {
  color: #6C7880;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 800;
}

.stat-cell.primary .stat-value,
.stat-cell.primary .stat-label {
  color: #FFFFFF;
}

.quick-panel {
  flex-direction: column;
  gap: 24rpx;
  margin-bottom: 52rpx;
}

.panel-head {
  flex-direction: column;
  gap: 8rpx;
}

.section-heading,
.result-title {
  color: #14212B;
  font-size: 34rpx;
  line-height: 1.3;
  font-weight: 900;
}

.chip-row,
.empty-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 18rpx;
}

.chip-row {
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 12rpx;
  padding: 4rpx 8rpx 2rpx;
}

.chip-line {
  display: flex;
  justify-content: center;
  gap: 14rpx;
  width: 100%;
}

.query-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 132rpx;
  min-height: 64rpx;
  padding: 0 28rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.74);
  color: #143E52;
  font-size: 26rpx;
  font-weight: 900;
  box-shadow: 0 12rpx 28rpx rgba(20, 33, 43, 0.06);
  white-space: nowrap;
}

.query-chip.compact {
  min-height: 54rpx;
  padding: 0 22rpx;
  font-size: 23rpx;
}

.result-head {
  align-items: flex-end;
  justify-content: space-between;
  gap: 24rpx;
  min-height: 82rpx;
  margin-bottom: 26rpx;
}

.result-head > view {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  min-width: 0;
}

.result-note {
  flex: 0 0 auto;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.35;
}

.article-list {
  flex-direction: column;
  gap: 26rpx;
}

.article-card {
  position: relative;
  align-items: stretch;
  gap: 24rpx;
  min-height: 214rpx;
  padding: 24rpx 24rpx 24rpx 30rpx;
  overflow: hidden;
}

.article-rank {
  position: absolute;
  top: 24rpx;
  left: 24rpx;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 54rpx;
  height: 42rpx;
  border: 1rpx solid rgba(255,255,255,0.56);
  border-radius: 14rpx;
  background: rgba(31,95,122,0.74);
}

.article-rank text {
  color: #FFFFFF;
  font-size: 20rpx;
  line-height: 1;
  font-weight: 900;
}

.article-image {
  flex: 0 0 auto;
  width: 168rpx;
  height: 168rpx;
  border-radius: 20rpx;
  background: #DCE5EA;
}

.article-copy {
  flex: 1;
  min-width: 0;
  flex-direction: column;
}

.article-head {
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  margin-bottom: 18rpx;
}

.read-time {
  flex: 0 0 auto;
  color: #8A949E;
  font-size: 22rpx;
  line-height: 1.35;
  font-weight: 800;
}

.article-title {
  display: block;
  margin-bottom: 12rpx;
  color: #14212B;
  font-size: 30rpx;
  line-height: 1.38;
  font-weight: 900;
}

.article-desc {
  display: block;
  color: #3F4F59;
  font-size: 24rpx;
  line-height: 1.52;
}

.highlight-text {
  padding: 0 3rpx;
  border-radius: 6rpx;
  background: rgba(212, 170, 78, 0.2);
  color: #876112;
}

.card-foot {
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  padding-top: 18rpx;
  margin-top: auto;
}

.source-line {
  flex: 1;
  min-width: 0;
  font-size: 22rpx;
}

.foot-arrow {
  flex: 0 0 auto;
  width: 24rpx;
  height: 24rpx;
  opacity: 0.56;
}

.empty-card {
  flex-direction: column;
  align-items: center;
  padding: 54rpx 42rpx;
  text-align: center;
}

.empty-icon {
  width: 72rpx;
  height: 72rpx;
  padding: 20rpx;
  border-radius: 999rpx;
  margin-bottom: 26rpx;
  background: rgba(31,95,122,0.09);
}

.empty-title {
  margin-bottom: 14rpx;
  color: #14212B;
  font-size: 31rpx;
  line-height: 1.32;
  font-weight: 900;
}

.empty-desc {
  max-width: 520rpx;
  color: #7C8790;
  font-size: 25rpx;
  line-height: 1.55;
}

.empty-chips {
  justify-content: center;
  margin-top: 28rpx;
}

.discover-button {
  width: 100%;
  margin-top: 34rpx;
}

.font-large .console-title {
  font-size: 54rpx;
}

.font-large .search-input,
.font-large .article-title,
.font-large .empty-title {
  font-size: 34rpx;
}

.font-large .article-desc,
.font-large .empty-desc {
  font-size: 29rpx;
}

.font-small .console-title {
  font-size: 46rpx;
}

.font-small .search-input,
.font-small .article-title,
.font-small .empty-title {
  font-size: 27rpx;
}

.font-small .article-desc,
.font-small .empty-desc {
  font-size: 23rpx;
}

.dark-mode .search-console {
  border-color: rgba(126,184,209,0.14);
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08));
  box-shadow: 0 28rpx 80rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .search-console::after {
  background: rgba(187, 141, 45, 0.14);
}

.dark-mode .search-toolbar,
.dark-mode .search-field,
.dark-mode .stat-cell,
.dark-mode .query-chip,
.dark-mode .empty-card,
.dark-mode .article-card {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

.dark-mode .clear-button,
.dark-mode .empty-icon {
  background: rgba(126,184,209,0.12) !important;
}

.dark-mode .console-title,
.dark-mode .section-heading,
.dark-mode .result-title,
.dark-mode .article-title,
.dark-mode .empty-title {
  color: #F4F7FA !important;
}

.dark-mode .console-desc,
.dark-mode .result-note,
.dark-mode .article-desc,
.dark-mode .read-time,
.dark-mode .source-line,
.dark-mode .empty-desc {
  color: #B6C2CC !important;
}

.dark-mode .console-kicker,
.dark-mode .section-eyebrow {
  color: #D4AA4E !important;
}

.dark-mode .stat-value,
.dark-mode .query-chip,
.dark-mode .clear-mark {
  color: #7EB8D1 !important;
}

.dark-mode .stat-label {
  color: #B6C2CC !important;
}

.dark-mode .stat-cell.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.9), rgba(16,39,55,0.94)) !important;
}

.dark-mode .highlight-text {
  background: rgba(212,170,78,0.16);
  color: #D4AA4E;
}
</style>
