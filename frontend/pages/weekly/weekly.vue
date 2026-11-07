<template>
  <view :class="['page with-tabbar weekly-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="weekly-head">
      <text class="page-title">每周</text>
      <text class="subtle">回看这一周，也看看自己的收获</text>
    </view>
    <view class="tabs" role="tablist" aria-label="每周内容">
      <button :class="['tab', tab === 'video' && 'active']" role="tab" :aria-selected="tab === 'video'" @click="switchTab('video')">每周视频</button>
      <button :class="['tab', tab === 'report' && 'active']" role="tab" :aria-selected="tab === 'report'" @click="switchTab('report')">我的周报</button>
    </view>

    <view v-if="tab === 'video'" class="video-panel">
      <view v-if="catalogLoading" class="status card"><text>正在加载每周节目…</text></view>
      <StateView v-else-if="catalogError" state="error" :message="catalogError" :dark-mode="darkMode" @retry="loadCatalog" />
      <template v-else-if="selection.selected">
        <view class="episode-meta"><text class="episode-label">{{ selection.label }}</text><text>第 {{ episode.number }} 期 · {{ episode.weekStart }} — {{ episode.weekEnd }}</text></view>
        <text v-if="selection.unknownId" class="notice">没有找到这期节目，已展示最近可用的节目。</text>
        <video v-if="!playbackError" id="weekly-video" :key="episode.id + ':' + playbackVersion" class="episode-video" :src="media(episode.video)" :poster="media(episode.poster)" controls :autoplay="false" :show-center-play-btn="true" :enable-play-gesture="true" @error="playbackError = true" @loadedmetadata="onVideoReady" />
        <view v-else class="status card"><text>视频暂时无法播放，可以先阅读下方文章与来源。</text><button class="secondary" @click="retryPlayback">重试播放</button></view>
        <view class="episode-copy"><text class="episode-title">{{ episode.title }}</text><text class="description">{{ episode.description }}</text><text class="subtle">{{ timestamp(episode.durationSeconds) }} · 中文旁白</text></view>
        <view v-if="episode.chapters && episode.chapters.length" class="chapter-list">
          <button v-for="(chapter, index) in episode.chapters" :key="index" class="chapter-row" :disabled="playbackError" @click="seek(chapter.seconds)"><text>{{ chapter.title }}</text><text class="chapter-time">{{ timestamp(chapter.seconds) }}</text></button>
        </view>
        <button v-if="selection.pinned && episode.id !== selection.pinned.id" class="secondary return-latest" @click="chooseEpisode(selection.pinned.id)">返回最新节目</button>
        <view class="reference-section"><text class="section-title">延伸阅读</text><text v-if="!episode.articles || !episode.articles.length" class="subtle">本期暂无延伸文章。</text><button v-for="(item, index) in episode.articles || []" :key="index" class="reference-row" @click="openLink(item.url)"><text>{{ item.title }}</text><text v-if="item.date" class="subtle">{{ item.date }}</text></button></view>
        <view class="reference-section"><text class="section-title">事实来源</text><text v-if="!episode.sources || !episode.sources.length" class="subtle">本期暂无补充来源。</text><button v-for="(item, index) in episode.sources || []" :key="index" class="reference-row" @click="openLink(item.url)"><text>{{ item.title }}</text><text v-if="item.date" class="subtle">{{ item.date }}</text></button><button v-if="episode.captions" class="reference-row" @click="openLink(media(episode.captions))">查看中文字幕文件</button></view>
      </template>
      <view v-else class="status card"><text class="episode-title">每周见闻，正在筹备</text><text class="subtle">节目发布后将在这里展示。重点文章、见闻更新与本周大事，一次回看。</text></view>
      <view v-if="!catalogLoading && !catalogError" class="archive-section">
        <text class="section-title">往期节目</text>
        <text v-if="!selection.archive.length" class="subtle">还没有往期节目，每一期发布后都会留在这里。</text>
        <button v-for="item in selection.archive" :key="item.id" :class="['archive-row', item.id === selectedId && 'selected']" @click="chooseEpisode(item.id)"><image v-if="media(item.poster)" class="archive-cover" :src="media(item.poster)" mode="aspectFill" lazy-load /><view class="archive-copy"><text class="subtle">第 {{ item.number }} 期 · {{ item.weekStart }}</text><text class="archive-title">{{ item.title }}</text><text class="subtle">{{ timestamp(item.durationSeconds) }}{{ item.id === selectedId ? ' · 正在观看' : '' }}</text></view></button>
      </view>
    </view>

    <view v-else class="report-panel">
      <view v-if="!hasAuth || authExpired" class="status card"><text class="episode-title">{{ authExpired ? '登录已过期' : '你的每周阅读，值得回看' }}</text><text class="subtle">登录后查看自己的阅读、提问记录与完整周报。</text><button class="primary-button" @click="login">{{ authExpired ? '重新登录' : '登录查看周报' }}</button></view>
      <template v-else>
        <view class="week-controls"><button class="week-button" :disabled="selectedWeek <= '2000-01-03'" @click="changeWeek(-7)">上一周</button><picker mode="date" :value="selectedWeek" start="2000-01-03" :end="currentWeek" @change="chooseDate"><view class="week-picker">{{ selectedWeek }} 起<text class="picker-hint">选择日期</text></view></picker><button class="week-button" :disabled="selectedWeek >= currentWeek" @click="changeWeek(7)">下一周</button></view>
        <button v-if="selectedWeek !== currentWeek" class="back-current" @click="setWeek(currentWeek)">回到本周</button>
        <text class="week-note">北京时间 · 周一至周日</text>
        <view v-if="reportLoading" class="status card"><text>正在整理你的周报…</text></view>
        <StateView v-else-if="reportError" state="error" :message="reportError" :dark-mode="darkMode" @retry="loadReport" />
        <template v-else-if="report"><text v-if="!report.summary.active_days" class="notice">这一周还没有使用记录，阅读或提问后会在这里显示。</text><WeeklyReport :key="identity + selectedWeek" :report="report" :identity="identity" :dark-mode="darkMode" :font-size="fontSize" /></template>
      </template>
    </view>
  </view>
</template>

<script>
import { getWeeklyReport, getWeeklyCatalog, getAuthToken, buildPublicUrl, isUnauthorized } from '@/utils/api.js'
import { beijingWeekStart, shiftDate, weekForDate, selectEpisodes, timestamp, safePublicPath } from '@/utils/weekly-model.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import WeeklyReport from '@/components/WeeklyReport.vue'
import StateView from '@/components/StateView.vue'

export default {
  components: { WeeklyReport, StateView },
  data() {
    return { tab: 'video', darkMode: false, fontSize: 'standard', visible: false,
      catalog: {}, catalogLoading: false, catalogError: '', selectedId: '', catalogVersion: 0,
      playbackError: false, playbackVersion: 0, pendingSeek: null,
      identity: '', hasAuth: false, authExpired: false, selectedWeek: beijingWeekStart(), currentWeek: beijingWeekStart(),
      report: null, reportLoading: false, reportError: '', reportVersion: 0 }
  },
  computed: {
    selection() { return selectEpisodes(this.catalog, this.selectedId) },
    episode() { return this.selection.selected || {} }
  },
  onLoad(query) {
    if (query && query.episode) this.selectedId = query.episode
    if (query && /^\d{4}-\d{2}-\d{2}$/.test(query.week_start || '')) {
      let date
      try { date = weekForDate(query.week_start) } catch (_) { return }
      if (date <= this.currentWeek && date >= '2000-01-03') this.selectedWeek = date
    }
  },
  onShow() {
    this.visible = true
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    this.currentWeek = beijingWeekStart()
    this.syncIdentity()
    applyTabBarTheme(this.darkMode)
    this.loadCatalog()
    if (this.tab === 'report' && this.hasAuth) this.loadReport()
  },
  onHide() { this.leavePage() },
  onUnload() { this.leavePage() },
  mounted() {
    // H5 tabs share the session store. Clear private data immediately on logout elsewhere.
    // #ifdef H5
    this._sessionChanged = () => {
      const previous = this.identity
      this.syncIdentity()
      if (previous !== this.identity && this.visible && this.tab === 'report' && this.hasAuth) this.loadReport()
    }
    window.addEventListener('storage', this._sessionChanged)
    window.addEventListener('focus', this._sessionChanged)
    // #endif
  },
  beforeUnmount() {
    // #ifdef H5
    window.removeEventListener('storage', this._sessionChanged)
    window.removeEventListener('focus', this._sessionChanged)
    // #endif
  },
  methods: {
    timestamp,
    media(value) { const path = safePublicPath(value); return path ? buildPublicUrl(path) : '' },
    syncIdentity() {
      const token = getAuthToken()
      if (this.identity !== token) { this.reportVersion++; this.report = null; this.reportError = ''; this.authExpired = false }
      this.identity = token; this.hasAuth = !!token
    },
    leavePage() {
      this.visible = false; this.pauseVideo(); this.pendingSeek = null; this.reportVersion++; this.catalogVersion++
      this.report = null; this.reportLoading = false; this.catalogLoading = false
    },
    pauseVideo() { try { uni.createVideoContext('weekly-video', this).pause() } catch (_) {} },
    playVideo(context) {
      // H5's media promise rejects when a tab switch intentionally pauses playback.
      // #ifdef H5
      const video = document.getElementById('weekly-video')?.querySelector('video')
      if (video) video.play().catch(error => {
        if (error.name === 'NotSupportedError' && this.visible && this.tab === 'video') this.playbackError = true
      })
      // #endif
      // #ifndef H5
      context.play()
      // #endif
    },
    switchTab(tab) {
      if (this.tab === tab) return
      this.pauseVideo(); this.pendingSeek = null; this.tab = tab; this.syncIdentity()
      if (tab === 'report' && this.hasAuth && !this.authExpired) this.loadReport()
      if (tab === 'video') { this.reportVersion++; this.report = null; this.reportLoading = false }
    },
    async loadCatalog() {
      const version = ++this.catalogVersion
      this.catalogLoading = true; this.catalogError = ''
      try {
        const catalog = await getWeeklyCatalog()
        if (version !== this.catalogVersion || !this.visible) return
        this.catalog = catalog || {}
      } catch (error) {
        if (version === this.catalogVersion && this.visible) this.catalogError = error.message || '节目列表暂时无法加载，请重试。'
      } finally { if (version === this.catalogVersion) this.catalogLoading = false }
    },
    chooseEpisode(id) { this.pauseVideo(); this.pendingSeek = null; this.selectedId = id; this.playbackError = false; this.playbackVersion++; uni.pageScrollTo({ scrollTop: 0, duration: 200 }) },
    seek(value) {
      if (this.playbackError) return
      this.pendingSeek = Math.max(0, Number(value) || 0)
      const context = uni.createVideoContext('weekly-video', this)
      context.seek(this.pendingSeek); this.playVideo(context)
    },
    onVideoReady() {
      if (!this.visible || this.tab !== 'video') { this.pauseVideo(); return }
      if (this.pendingSeek !== null) { const context = uni.createVideoContext('weekly-video', this); context.seek(this.pendingSeek); this.playVideo(context); this.pendingSeek = null }
    },
    retryPlayback() { this.playbackError = false; this.pendingSeek = null; this.playbackVersion++ },
    login() { uni.navigateTo({ url: '/pages/auth/login' }) },
    changeWeek(days) { this.setWeek(shiftDate(this.selectedWeek, days)) },
    chooseDate(event) { this.setWeek(weekForDate(event.detail.value)) },
    setWeek(date) { if (date > this.currentWeek || date < '2000-01-03') return; this.selectedWeek = date; this.loadReport() },
    async loadReport() {
      this.syncIdentity()
      const version = ++this.reportVersion, token = this.identity, week = this.selectedWeek
      this.report = null; this.reportError = ''; this.reportLoading = false
      if (!token || this.authExpired || !this.visible) return
      this.reportLoading = true
      try {
        const report = await getWeeklyReport(week)
        if (version !== this.reportVersion || token !== getAuthToken() || !this.visible) return
        this.report = report
      } catch (error) {
        if (version !== this.reportVersion || token !== getAuthToken() || !this.visible) return
        // 401 is handled centrally in utils/api.js (clears session + opens login with redirect).
        if (isUnauthorized(error)) this.authExpired = true
        else this.reportError = error.message || '周报加载失败，请重试。'
      } finally { if (version === this.reportVersion) this.reportLoading = false }
    },
    openArticle(item) { uni.navigateTo({ url: `/pages/article/detail?id=${encodeURIComponent(item.content_id || item.id)}` }) },
    openClassic(item) { uni.navigateTo({ url: `/pages/classics/reader?bookId=${encodeURIComponent(item.book_id)}&chapterId=${encodeURIComponent(item.content_id)}` }) },
    openLink(value) {
      const safe = safePublicPath(value)
      if (!safe) { uni.showToast({ title: '链接暂时不可用', icon: 'none' }); return }
      // Catalogue-relative links are the website's own routes.
      if (!/^https?:\/\//i.test(safe)) {
        const article = safe.match(/(?:^|\/)article\.html\?[^#]*\bid=([^&#]+)/)
        if (article) { try { this.openArticle({ content_id: decodeURIComponent(article[1]) }); return } catch (_) {} }
        if (/(?:^|\/)changelog\.html(?:[?#]|$)/.test(safe)) { uni.navigateTo({ url: '/pages/settings/changelog' }); return }
      }
      const url = /^https?:\/\//i.test(safe) ? safe : buildPublicUrl(safe)
      // #ifdef H5
      window.open(url, '_blank', 'noopener,noreferrer')
      // #endif
      // #ifdef APP-PLUS
      plus.runtime.openURL(url, () => uni.showToast({ title: '链接打开失败，请重试', icon: 'none' }))
      // #endif
    }
  }
}
</script>

<style scoped>
.weekly-head { display:flex; flex-direction:column; gap:14rpx; margin:10rpx 0 38rpx; }
.tabs { display:flex; padding:7rpx; gap:7rpx; border-radius:18rpx; background:#E7EFF0; margin-bottom:36rpx; }
.tab { flex:1; margin:0; background:transparent; border-radius:13rpx; font-size:28rpx; color:#53666C; line-height:2.6; }
.tab::after,.chapter-row::after,.reference-row::after,.archive-row::after,.week-button::after,.back-current::after,.secondary::after { border:0; }
.tab.active { color:#fff; background:#1F5F7A; font-weight:700; }
.status { display:flex; flex-direction:column; gap:28rpx; padding:38rpx; font-size:28rpx; line-height:1.65; }
.episode-meta { display:flex; flex-wrap:wrap; gap:14rpx; align-items:center; font-size:22rpx; line-height:1.5; color:#53666C; margin-bottom:22rpx; }
.episode-label { color:#1F5F7A; font-weight:700; }
.episode-video { width:100%; height:375rpx; background:#14212B; border-radius:20rpx; overflow:hidden; }
.episode-copy { display:flex; flex-direction:column; gap:20rpx; margin:30rpx 0; }
.episode-title { font-size:38rpx; font-weight:800; line-height:1.45; color:#14212B; }
.description { font-size:28rpx; line-height:1.8; color:#53666C; }
.chapter-list { border-top:1rpx solid #D8E3E5; }
.chapter-row { display:flex; align-items:center; justify-content:space-between; gap:28rpx; width:100%; text-align:left; border-radius:0; margin:0; padding:24rpx 4rpx; font-size:26rpx; line-height:1.5; background:transparent; color:#1F5F7A; border-bottom:1rpx solid #D8E3E5; }
.chapter-time { flex-shrink:0; font-variant-numeric:tabular-nums; color:#53666C; }
.section-title { display:block; font-size:32rpx; font-weight:800; margin:0 0 22rpx; color:#14212B; }
.reference-section,.archive-section { margin-top:54rpx; }
.reference-row { display:flex; flex-direction:column; gap:10rpx; text-align:left; padding:23rpx 0; margin:0; border-radius:0; font-size:27rpx; line-height:1.65; color:#1F5F7A; background:transparent; border-bottom:1rpx solid #D8E3E5; }
.archive-row { display:flex; align-items:center; gap:24rpx; padding:25rpx 0; margin:0; text-align:left; background:transparent; border-radius:0; border-bottom:1rpx solid #D8E3E5; }
.archive-cover { flex-shrink:0; width:180rpx; height:112rpx; border-radius:12rpx; }
.archive-copy { display:flex; flex-direction:column; gap:9rpx; min-width:0; }
.archive-title { font-size:28rpx; line-height:1.55; color:#14212B; font-weight:700; }
.archive-row.selected .archive-title { color:#1F5F7A; }
.week-controls { display:flex; gap:12rpx; align-items:center; justify-content:space-between; }
.week-button { margin:0; padding:16rpx 10rpx; font-size:25rpx; line-height:1.5; background:transparent; color:#1F5F7A; flex-shrink:0; }
.week-picker { font-size:26rpx; font-weight:700; line-height:1.5; text-align:center; color:#14212B; }
.picker-hint { display:block; font-size:21rpx; font-weight:400; color:#53666C; }
.week-note { display:block; text-align:center; margin:20rpx 0 32rpx; color:#53666C; font-size:23rpx; }
.back-current { background:transparent; color:#1F5F7A; font-size:25rpx; line-height:2; margin-top:12rpx; }
.notice { display:block; padding:24rpx; margin:20rpx 0; background:#EDF2E7; font-size:25rpx; color:#486036; line-height:1.65; border-radius:12rpx; }
.secondary { padding:16rpx 24rpx; background:#E8F0F3; color:#1F5F7A; font-size:26rpx; line-height:1.6; margin:0; }
.return-latest { margin:24rpx 0; }
button[disabled] { opacity:.45; }
button:focus-visible { outline:0; box-shadow:0 0 0 2rpx rgba(40,100,94,.2), 0 0 0 8rpx rgba(40,100,94,.08); }
.font-large .description,.font-large .reference-row,.font-large .chapter-row,.font-large .archive-title { font-size:31rpx; }
.font-small .description,.font-small .reference-row,.font-small .chapter-row,.font-small .archive-title { font-size:25rpx; }
.dark-mode .tabs { background:#20313E; }
.dark-mode .tab { color:#B6C2CC; }
.dark-mode .tab.active { background:#28647E; color:#fff; }
.dark-mode .episode-title,.dark-mode .section-title,.dark-mode .archive-title,.dark-mode .week-picker { color:#F4F7FA; }
.dark-mode .description,.dark-mode .episode-meta,.dark-mode .chapter-time,.dark-mode .picker-hint,.dark-mode .week-note { color:#B6C2CC; }
.dark-mode .episode-label,.dark-mode .chapter-row,.dark-mode .reference-row,.dark-mode .week-button,.dark-mode .back-current,.dark-mode .archive-row.selected .archive-title { color:#8DC4DC; }
.dark-mode .chapter-list,.dark-mode .chapter-row,.dark-mode .reference-row,.dark-mode .archive-row { border-color:#304451; }
.dark-mode .secondary { background:#20384A; color:#8DC4DC; }
.dark-mode .notice { background:#243A2A; color:#C3D8B5; }
</style>
