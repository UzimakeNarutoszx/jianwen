<template>
  <view :class="['reader-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="reader-topbar">
      <button class="back-button reader-back-button" @click="goBack">
        <text class="back-symbol"></text>
      </button>
      <view class="top-copy">
        <text class="top-title">{{ book ? book.title : '电子书' }}</text>
        <text v-if="pages.length" class="top-state">第 {{ currentPage + 1 }} 页</text>
      </view>
    </view>

    <swiper
      v-if="pages.length"
      class="book-swiper"
      :current="currentPage"
      :duration="320"
      @change="handlePageChange"
    >
      <swiper-item v-for="(page, index) in pages" :key="page.key">
        <view class="book-shell">
          <view :class="['paper-page', page.type]">
            <view class="paper-header">
              <text class="paper-book">{{ book.title }}</text>
              <text class="paper-page-no">{{ index + 1 }} / {{ pages.length }}</text>
            </view>

            <view v-if="page.type === 'cover'" class="cover-content">
              <view class="cover-frame">
                <text class="cover-kicker">{{ page.category }}</text>
                <text class="cover-title">{{ page.title }}</text>
                <text class="cover-author">{{ page.author }}</text>
                <view class="cover-line"></view>
                <text class="cover-source">{{ page.sourceOrg }}</text>
                <text class="cover-imprint">见闻经典文献</text>
              </view>
            </view>

            <view v-else class="reading-content">
              <text class="page-label">{{ page.label }}</text>
              <text class="page-title">{{ page.title }}</text>
              <view class="paragraph-list">
                <text v-for="(paragraph, paragraphIndex) in page.paragraphs" :key="paragraphIndex" class="paragraph">
                  {{ paragraph }}
                </text>
              </view>
            </view>

            <view class="paper-footer">
              <text>{{ page.footer }}</text>
            </view>
          </view>
        </view>
      </swiper-item>
    </swiper>

    <view v-if="pages.length" class="reader-progress">
      <view class="progress-meta">
        <text class="progress-chapter">{{ currentPageData.footer || '见闻经典文献' }}</text>
        <text class="progress-text">第 {{ currentPage + 1 }} 页 / 共 {{ pages.length }} 页</text>
      </view>
      <view class="progress-track-wrap">
        <view class="progress-track">
          <view class="progress-fill" :style="{ width: progressWidth }"></view>
          <view class="progress-ticks">
            <view
              v-for="(page, index) in pages"
              :key="`tick-${page.key}`"
              :class="['progress-tick', index <= currentPage ? 'active' : '']"
            ></view>
          </view>
        </view>
      </view>
    </view>

    <view v-if="!pages.length && !loading" class="empty-card">
      <text class="empty-title">暂时无法打开电子书</text>
      <text class="empty-desc">请返回经典文献详情页重新进入。</text>
    </view>
  </view>
</template>

<script>
import { getClassicBookChapter, getClassicBookDetail } from '@/utils/api.js'

const BODY_LIMIT = 210
const SUMMARY_LIMIT = 260

function normalizeParagraphs(text) {
  if (!text) return []
  return String(text)
    .split(/\n+/)
    .map(item => item.trim())
    .filter(Boolean)
}

function splitText(text, limit) {
  const paragraphs = normalizeParagraphs(text)
  const chunks = []
  paragraphs.forEach(paragraph => {
    let rest = paragraph
    while (rest.length > limit) {
      chunks.push(rest.slice(0, limit))
      rest = rest.slice(limit)
    }
    if (rest) chunks.push(rest)
  })
  return chunks.length ? chunks : ['暂无正文内容。']
}

export default {
  data() {
    return {
      bookId: '',
      chapterId: '',
      book: null,
      pages: [],
      currentPage: 0,
      loading: true,
      loadingChapterIds: {},
      loadedChapterIds: {},
      darkMode: false,
      fontSize: 'standard'
    }
  },
  computed: {
    currentPageData() {
      return this.pages[this.currentPage] || {}
    },
    progressWidth() {
      if (!this.pages.length) return '0%'
      return `${Math.round(((this.currentPage + 1) / this.pages.length) * 100)}%`
    },
  },
  onLoad(options) {
    this.bookId = decodeURIComponent(options.bookId || '')
    this.chapterId = decodeURIComponent(options.chapterId || '')
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.loadBook()
  },
  onHide() {
    this.saveReadingPosition()
  },
  onUnload() {
    this.saveReadingPosition()
  },
  methods: {
    async loadBook() {
      this.loading = true
      try {
        this.book = await getClassicBookDetail(this.bookId)
        this.pages = this.buildPages(this.book)
        this.currentPage = this.initialPageIndex()
        this.saveReadingPosition()
        this.loadChapterForCurrentPage()
      } catch (error) {
        uni.showToast({ title: error.message || '电子书加载失败', icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    buildPages(book) {
      if (!book) return []
      const pages = [
        {
          key: 'cover',
          type: 'cover',
          title: book.title,
          author: book.author,
          category: book.category,
          sourceOrg: book.sourceOrg,
          footer: '见闻经典文献'
        },
        {
          key: 'intro',
          type: 'intro',
          label: '简介',
          title: book.title,
          paragraphs: splitText(`${book.description}\n\n来源：${book.sourceOrg}\n\n第一版提供目录摘要和权威阅读入口；后续补充全文后，会在本阅读器内直接展示正文。`, SUMMARY_LIMIT),
          footer: '书籍简介'
        }
      ]

      ;(book.chapters || []).forEach(chapter => {
        if (chapter.content) {
          splitText(chapter.content, BODY_LIMIT).forEach((paragraph, index) => {
            pages.push({
              key: `chapter-${chapter.id}-${index}`,
              type: 'chapter',
              chapterId: `${chapter.id}`,
              label: index === 0 ? `第 ${chapter.chapterOrder} 章` : `第 ${chapter.chapterOrder} 章 续`,
              title: chapter.title,
              paragraphs: [paragraph],
              footer: chapter.title
            })
          })
          return
        }

        pages.push({
          key: `chapter-${chapter.id}`,
          type: 'chapter',
          chapterId: `${chapter.id}`,
          label: `第 ${chapter.chapterOrder} 章`,
          title: chapter.title,
          paragraphs: splitText(chapter.summary || '暂无章节摘要。', SUMMARY_LIMIT),
          footer: '目录摘要'
        })
      })

      return pages
    },
    initialPageIndex() {
      if (this.chapterId) {
        const index = this.pages.findIndex(page => page.chapterId === this.chapterId)
        return index >= 0 ? index : 0
      }
      const saved = this.getSavedReadingPosition()
      if (!saved) return 0
      if (saved.pageKey) {
        const pageIndex = this.pages.findIndex(page => page.key === saved.pageKey)
        if (pageIndex >= 0) return pageIndex
      }
      if (Number.isInteger(saved.currentPage) && saved.currentPage >= 0 && saved.currentPage < this.pages.length) {
        return saved.currentPage
      }
      return 0
    },
    readingPositionKey() {
      return this.bookId ? `jianwen_classic_reader_position_${encodeURIComponent(this.bookId)}` : ''
    },
    getSavedReadingPosition() {
      const key = this.readingPositionKey()
      if (!key) return null
      const saved = uni.getStorageSync(key)
      if (!saved || typeof saved !== 'object') return null
      return saved
    },
    saveReadingPosition() {
      const key = this.readingPositionKey()
      if (!key || !this.pages.length) return
      const page = this.currentPageData
      uni.setStorageSync(key, {
        bookId: this.bookId,
        currentPage: this.currentPage,
        pageKey: page.key || '',
        chapterId: page.chapterId || '',
        updatedAt: Date.now()
      })
    },
    getChapter(chapterId) {
      if (!this.book || !Array.isArray(this.book.chapters)) return null
      return this.book.chapters.find(chapter => `${chapter.id}` === `${chapterId}`) || null
    },
    mergeChapterContent(chapter) {
      if (!chapter || !this.book || !Array.isArray(this.book.chapters)) return
      const index = this.book.chapters.findIndex(item => `${item.id}` === `${chapter.id}`)
      if (index < 0) return
      this.book.chapters.splice(index, 1, {
        ...this.book.chapters[index],
        ...chapter
      })
    },
    async loadChapterForCurrentPage() {
      const page = this.currentPageData
      if (!page || !page.chapterId || !this.bookId) return
      const chapter = this.getChapter(page.chapterId)
      if (!chapter || chapter.content || this.loadingChapterIds[page.chapterId] || this.loadedChapterIds[page.chapterId]) return

      const requestedPageKey = page.key
      this.loadingChapterIds[page.chapterId] = true
      try {
        const loadedChapter = await getClassicBookChapter(this.bookId, page.chapterId)
        this.loadedChapterIds[page.chapterId] = true
        if (!loadedChapter || !loadedChapter.content) return

        const targetChapterId = page.chapterId
        const activePageKey = this.currentPageData.key
        this.mergeChapterContent(loadedChapter)
        this.pages = this.buildPages(this.book)
        const nextPageIndex = activePageKey === requestedPageKey
          ? this.pages.findIndex(item => item.chapterId === targetChapterId)
          : this.pages.findIndex(item => item.key === activePageKey)
        if (nextPageIndex >= 0) {
          this.currentPage = nextPageIndex
          this.saveReadingPosition()
        }
      } catch (error) {
        uni.showToast({ title: error.message || '章节加载失败', icon: 'none' })
      } finally {
        delete this.loadingChapterIds[page.chapterId]
      }
    },
    handlePageChange(event) {
      this.currentPage = event.detail.current
      this.saveReadingPosition()
      this.loadChapterForCurrentPage()
    },
    goBack() {
      this.saveReadingPosition()
      uni.navigateBack({
        fail: () => uni.switchTab({ url: '/pages/discover/discover' })
      })
    }
  }
}
</script>

<style scoped>
.reader-page {
  min-height: 100vh;
  padding: calc(132rpx + constant(safe-area-inset-top)) 30rpx calc(134rpx + constant(safe-area-inset-bottom));
  padding: calc(132rpx + env(safe-area-inset-top)) 30rpx calc(134rpx + env(safe-area-inset-bottom));
  background:
    radial-gradient(circle at 18% 0%, rgba(212, 170, 78, 0.22) 0, rgba(212, 170, 78, 0) 260rpx),
    radial-gradient(circle at 88% 8%, rgba(31, 95, 122, 0.14) 0, rgba(31, 95, 122, 0) 320rpx),
    linear-gradient(180deg, #EFE6D4 0%, #E7E0D1 46%, #DDD4C2 100%);
}

.reader-topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: center;
  height: calc(116rpx + constant(safe-area-inset-top));
  height: calc(116rpx + env(safe-area-inset-top));
  padding: calc(28rpx + constant(safe-area-inset-top)) 28rpx 0;
  padding: calc(28rpx + env(safe-area-inset-top)) 28rpx 0;
  border-bottom: 1rpx solid rgba(132, 101, 58, 0.12);
  background:
    linear-gradient(135deg, rgba(255, 249, 234, 0.9), rgba(232, 225, 210, 0.74)),
    rgba(239, 230, 212, 0.86);
  box-shadow: 0 16rpx 44rpx rgba(79, 58, 34, 0.08);
  backdrop-filter: blur(12rpx);
}

.reader-page .reader-back-button {
  position: absolute;
  left: 28rpx;
  bottom: 16rpx;
}

.top-copy {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4rpx;
  max-width: 430rpx;
  min-width: 0;
}

.top-title {
  display: block;
  max-width: 100%;
  color: #4F3A22;
  font-size: 28rpx;
  font-weight: 900;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-state {
  color: #9B8567;
  font-size: 20rpx;
  font-weight: 800;
  line-height: 1.2;
}

.book-swiper {
  height: calc(100vh - 274rpx - constant(safe-area-inset-top) - constant(safe-area-inset-bottom));
  height: calc(100vh - 274rpx - env(safe-area-inset-top) - env(safe-area-inset-bottom));
  min-height: 560rpx;
}

.book-shell {
  display: flex;
  align-items: stretch;
  justify-content: center;
  height: 100%;
  padding: 10rpx 4rpx 18rpx;
}

.paper-page {
  position: relative;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 690rpx;
  min-height: 100%;
  padding: 34rpx 38rpx 28rpx 44rpx;
  border: 1rpx solid rgba(141, 107, 67, 0.2);
  border-radius: 24rpx 14rpx 14rpx 24rpx;
  background:
    linear-gradient(90deg, rgba(118, 82, 42, 0.08), rgba(118, 82, 42, 0) 54rpx),
    linear-gradient(180deg, #FFF9EC 0%, #FFF4E0 100%);
  box-shadow:
    0 24rpx 52rpx rgba(79, 58, 34, 0.2),
    12rpx 0 28rpx rgba(255, 255, 255, 0.42) inset,
    -10rpx 0 22rpx rgba(111, 76, 38, 0.05) inset;
  overflow: hidden;
}

.paper-page::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 24rpx;
  width: 2rpx;
  background: linear-gradient(180deg, rgba(129, 91, 48, 0), rgba(129, 91, 48, 0.2), rgba(129, 91, 48, 0));
}

.paper-page::after {
  content: '';
  position: absolute;
  top: 18rpx;
  right: 16rpx;
  bottom: 18rpx;
  width: 1rpx;
  background: rgba(129, 91, 48, 0.08);
}

.paper-header,
.paper-footer {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20rpx;
  color: #8B7659;
  font-size: 22rpx;
  line-height: 1.3;
}

.paper-header {
  padding-bottom: 18rpx;
  border-bottom: 1rpx solid rgba(141, 107, 67, 0.14);
}

.paper-footer {
  padding-top: 18rpx;
  border-top: 1rpx solid rgba(141, 107, 67, 0.12);
}

.paper-book {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cover-content,
.reading-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 1;
  flex-direction: column;
}

.cover-content {
  align-items: center;
  justify-content: center;
  padding: 32rpx 0;
  text-align: center;
}

.cover-frame {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  min-height: 78%;
  justify-content: center;
  gap: 24rpx;
  padding: 42rpx 30rpx;
  border: 1rpx solid rgba(141, 107, 67, 0.2);
  border-radius: 18rpx;
  background: rgba(255, 250, 238, 0.42);
}

.cover-kicker,
.page-label {
  color: #9A6E27;
  font-size: 24rpx;
  font-weight: 900;
}

.cover-title {
  color: #3A2A1A;
  font-size: 52rpx;
  line-height: 1.22;
  font-weight: 900;
}

.cover-author,
.cover-source {
  color: #6B4F2F;
  font-size: 27rpx;
  font-weight: 800;
  line-height: 1.45;
}

.cover-line {
  width: 168rpx;
  height: 2rpx;
  margin: 8rpx 0;
  border-radius: 999rpx;
  background: linear-gradient(90deg, rgba(212, 170, 78, 0), #D4AA4E, rgba(212, 170, 78, 0));
}

.cover-imprint {
  margin-top: 18rpx;
  color: #9B8567;
  font-size: 22rpx;
  font-weight: 800;
  letter-spacing: 0;
}

.reading-content {
  gap: 16rpx;
  padding: 30rpx 2rpx 22rpx;
}

.page-title {
  color: #3A2A1A;
  font-size: 34rpx;
  line-height: 1.32;
  font-weight: 900;
}

.paragraph-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 16rpx;
  overflow: hidden;
}

.paragraph {
  color: #4E4032;
  font-size: 28rpx;
  line-height: 1.78;
  text-align: justify;
}

.reader-progress {
  position: fixed;
  left: 30rpx;
  right: 30rpx;
  bottom: calc(24rpx + constant(safe-area-inset-bottom));
  bottom: calc(24rpx + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: 14rpx;
  padding: 18rpx 22rpx;
  border: 1rpx solid rgba(255, 249, 234, 0.72);
  border-radius: 22rpx;
  background: rgba(255, 248, 234, 0.76);
  box-shadow: 0 16rpx 44rpx rgba(79, 58, 34, 0.12);
  backdrop-filter: blur(12rpx);
}

.progress-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 16rpx;
}

.progress-chapter {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  color: #5B4227;
  font-size: 23rpx;
  font-weight: 900;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-text {
  flex: 0 0 auto;
  color: #8B7659;
  font-size: 22rpx;
  font-weight: 800;
  line-height: 1.3;
  white-space: nowrap;
}

.font-large .progress-meta {
  align-items: flex-start;
  flex-direction: column;
  gap: 8rpx;
}

.progress-track-wrap {
  width: 100%;
}

.progress-track {
  position: relative;
  height: 10rpx;
  border-radius: 999rpx;
  background: rgba(107, 79, 47, 0.16);
  overflow: hidden;
}

.progress-fill {
  position: relative;
  z-index: 1;
  height: 100%;
  border-radius: 999rpx;
  background: linear-gradient(90deg, #1F5F7A, #D4AA4E);
}

.progress-ticks {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  justify-content: space-between;
  pointer-events: none;
}

.progress-tick {
  width: 2rpx;
  height: 10rpx;
  background: rgba(255, 248, 234, 0.7);
}

.progress-tick.active {
  background: rgba(255, 255, 255, 0.86);
}

.empty-card {
  display: flex;
  flex-direction: column;
  gap: 18rpx;
  padding: 44rpx;
  border: 1rpx solid rgba(141, 107, 67, 0.18);
  border-radius: 24rpx;
  background: rgba(255, 248, 234, 0.84);
  box-shadow: 0 20rpx 48rpx rgba(79, 58, 34, 0.12);
}

.empty-title {
  color: #3A2A1A;
  font-size: 32rpx;
  font-weight: 900;
}

.empty-desc {
  color: #6B4F2F;
  font-size: 26rpx;
}

.font-large .paragraph {
  font-size: 31rpx;
  line-height: 1.72;
}

.font-large .reading-content {
  gap: 14rpx;
  padding-top: 26rpx;
}

.font-large .page-title {
  font-size: 32rpx;
}

.font-small .paragraph {
  font-size: 26rpx;
  line-height: 1.82;
}

.dark-mode.reader-page {
  background:
    radial-gradient(circle at 18% 0%, rgba(166, 117, 47, 0.14) 0, rgba(166, 117, 47, 0) 260rpx),
    radial-gradient(circle at 88% 8%, rgba(75, 154, 187, 0.1) 0, rgba(75, 154, 187, 0) 320rpx),
    linear-gradient(180deg, #17130F 0%, #120F0C 100%);
}

.dark-mode .reader-topbar {
  border-bottom-color: rgba(216, 190, 146, 0.1);
  background:
    linear-gradient(135deg, rgba(38, 31, 23, 0.9), rgba(23, 20, 15, 0.76)),
    rgba(23, 20, 15, 0.88);
  box-shadow: 0 16rpx 44rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .paper-page,
.dark-mode .empty-card {
  border-color: rgba(216, 190, 146, 0.12);
  background:
    linear-gradient(90deg, rgba(255, 246, 226, 0.035), rgba(255, 246, 226, 0) 54rpx),
    linear-gradient(180deg, #2A231A 0%, #211A14 100%);
  box-shadow:
    0 24rpx 56rpx rgba(0, 0, 0, 0.32),
    10rpx 0 22rpx rgba(255, 246, 226, 0.03) inset;
}

.dark-mode .paper-page::before {
  background: linear-gradient(180deg, rgba(216, 190, 146, 0), rgba(216, 190, 146, 0.14), rgba(216, 190, 146, 0));
}

.dark-mode .paper-page::after {
  background: rgba(216, 190, 146, 0.06);
}

.dark-mode .paper-header,
.dark-mode .paper-footer {
  border-color: rgba(216, 190, 146, 0.1);
}

.dark-mode .top-title,
.dark-mode .cover-title,
.dark-mode .page-title,
.dark-mode .empty-title {
  color: #F2E5CE;
}

.dark-mode .top-state,
.dark-mode .cover-imprint {
  color: #AA8D65;
}

.dark-mode .paragraph,
.dark-mode .cover-author,
.dark-mode .cover-source,
.dark-mode .empty-desc,
.dark-mode .progress-text {
  color: #D8C8AE;
}

.dark-mode .paper-header,
.dark-mode .paper-footer,
.dark-mode .cover-kicker,
.dark-mode .page-label {
  color: #B99261;
}

.dark-mode .cover-frame {
  border-color: rgba(216, 190, 146, 0.12);
  background: rgba(255, 246, 226, 0.03);
}

.dark-mode .reader-progress {
  border-color: rgba(216, 190, 146, 0.1);
  background: rgba(38, 31, 23, 0.78);
  box-shadow: 0 16rpx 44rpx rgba(0, 0, 0, 0.28);
}

.dark-mode .progress-chapter {
  color: #F2E5CE;
}

.dark-mode .progress-track {
  background: rgba(216, 190, 146, 0.14);
}

.dark-mode .progress-tick {
  background: rgba(38, 31, 23, 0.78);
}
</style>
