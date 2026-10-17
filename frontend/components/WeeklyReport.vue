<template>
  <view :class="['weekly-paper', { 'report-dark': darkMode }, `report-font-${fontSize}`]">
    <view class="report-cover">
      <text class="report-title">{{ model.title }}</text>
      <text class="report-period">{{ model.period }}</text>
      <text class="report-badge">{{ model.badge }}</text>
      <text class="report-copy">{{ model.active }}</text>
    </view>
    <view class="report-stats">
      <view v-for="stat in model.stats" :key="stat[0]" class="report-stat"><text class="report-meta">{{ stat[0] }}</text><text class="report-stat-value">{{ stat[1] }}</text></view>
    </view>
    <view v-for="chart in charts" :key="chart.key" class="report-section report-chart">
      <text class="section-title">{{ chart.title }}</text>
      <canvas :id="canvasId(chart.key)" :canvas-id="canvasId(chart.key)" :style="{ width: chartWidth + 'px', height: getChartHeight(chart.key) + 'px' }" :width="chartWidth" :height="getChartHeight(chart.key)" />
      <text class="report-meta">{{ chart.caption }}</text>
    </view>
    <view class="report-section">
      <button class="data-toggle" @click="showData = !showData">{{ showData ? '收起图表数据' : '查看图表数据' }}</button>
      <view v-if="showData" class="report-data">
        <view v-for="day in report.days" :key="day.date" class="data-day">
          <text>{{ day.date }}</text><text class="report-meta">文章 {{ day.articles }} · 章节 {{ day.chapters }} · 问问 {{ day.ask }} · 阿烬 {{ day.ajin }} · 停留 {{ formatMinutes(day.reading_seconds) }} 分钟</text>
        </view>
        <text v-for="topic in report.topics" :key="topic.name" class="report-meta">{{ topic.name }} {{ topic.count }} 篇</text>
      </view>
    </view>
    <view v-for="section in model.sections" :key="section.title" class="report-section">
      <text class="section-title">{{ section.title }}</text>
      <text v-if="section.intro" class="report-meta">{{ section.intro }}</text>
      <text v-if="!section.items.length" class="report-meta report-empty">{{ section.empty }}</text>
      <view v-for="(item, index) in section.items" :key="index" class="report-row" :class="{ 'report-link': !!item.kind }" @click="openItem(item)">
        <text class="row-title">{{ item.title }}<text v-if="item.kind" class="row-arrow"> ›</text></text><text class="report-meta">{{ item.meta }}</text>
      </view>
    </view>
    <view class="report-section report-notes"><text v-for="note in model.notes" :key="note" class="report-meta">{{ note }}</text></view>
    <view class="report-export">
      <button :disabled="exporting" class="export-button" @click="exportImage">{{ exporting ? '正在生成完整长图…' : '导出完整周报长图' }}</button>
      <text v-if="exportError" class="export-error">{{ exportError }}</text>
      <view v-if="exportPath" class="export-result">
        <text class="report-meta">完整长图已生成，可预览或保存。所有明细均已包含。</text>
        <button class="data-toggle" @click="previewImage">预览完整长图</button>
        <button class="data-toggle" @click="saveImage">{{ isWeb ? '下载完整长图' : '保存到相册' }}</button>
      </view>
    </view>
    <canvas :id="canvasId('export')" :canvas-id="canvasId('export')" class="export-canvas" :style="{ width: exportWidth + 'px', height: exportHeight + 'px' }" :width="exportWidth" :height="exportHeight" />
  </view>
</template>

<script>
import { CHARTS, reportModel, minutes, chartScene, chartHeight, exportScene, paintScene } from '../utils/weekly-report.js'
let nextCanvasId = 0
export default {
  name: 'WeeklyReport',
  props: {
    report: { type: Object, required: true },
    identity: { type: [String, Number], default: '' },
    darkMode: { type: Boolean, default: false },
    fontSize: { type: String, default: 'standard' }
  },
  emits: ['open-article', 'open-classic'],
  data() {
    return { charts: CHARTS, instanceId: `weekly-report-${++nextCanvasId}`, chartWidth: 280, showData: false, exporting: false, exportPath: '', exportError: '', exportWidth: 720, exportHeight: 1, revision: 0, resizeHandler: null, isWeb: false }
  },
  computed: { model() { return reportModel(this.report) } },
  watch: {
    report() { this.invalidate(); this.$nextTick(this.drawCharts) },
    identity() { this.invalidate() },
    darkMode() { this.$nextTick(this.drawCharts) },
    fontSize() { this.$nextTick(this.drawCharts) }
  },
  mounted() {
    // #ifdef H5
    this.isWeb = true
    // #endif
    this.resizeHandler = () => { this.chartWidth = Math.max(220, Math.min(680, uni.getSystemInfoSync().windowWidth - 80)); this.$nextTick(this.drawCharts) }
    this.resizeHandler()
    if (uni.onWindowResize) uni.onWindowResize(this.resizeHandler)
  },
  beforeUnmount() { this.invalidate(); if (uni.offWindowResize && this.resizeHandler) uni.offWindowResize(this.resizeHandler) },
  methods: {
    formatMinutes: minutes,
    canvasId(key) { return `${this.instanceId}-${key}` },
    getChartHeight(key) { return chartHeight(key, this.report) },
    invalidate() { this.revision++; this.exportPath = ''; this.exportError = '' },
    drawCharts() {
      CHARTS.forEach(chart => {
        const height = this.getChartHeight(chart.key)
        const ctx = uni.createCanvasContext(this.canvasId(chart.key), this)
        paintScene(ctx, chartScene(chart.key, this.report, this.chartWidth, height, this.darkMode), this.chartWidth, height, this.darkMode ? '#18232d' : '#fffef9')
        ctx.draw()
      })
    },
    openItem(item) {
      if (item.kind === 'article') this.$emit('open-article', item.source)
      if (item.kind === 'classic') this.$emit('open-classic', item.source)
    },
    async exportImage() {
      if (this.exporting) return
      const revision = this.revision, identity = this.identity
      this.exporting = true; this.exportError = ''; this.exportPath = ''
      try {
        const scene = exportScene(this.report)
        this.exportWidth = scene.width; this.exportHeight = scene.height
        await this.$nextTick()
        // uni-canvas applies layout through its resize observer / native view bridge.
        // Vue's nextTick alone can still leave a one-pixel backing store.
        await new Promise(resolve => setTimeout(resolve, 100))
        if (revision !== this.revision || identity !== this.identity) return
        const ctx = uni.createCanvasContext(this.canvasId('export'), this)
        paintScene(ctx, scene.ops, scene.width, scene.height)
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => reject(new Error('设备未能完成长图绘制，请重试。')), 20000)
          ctx.draw(false, () => { clearTimeout(timeout); resolve() })
        })
        if (revision !== this.revision || identity !== this.identity) return
        const result = await new Promise((resolve, reject) => uni.canvasToTempFilePath({ canvasId: this.canvasId('export'), x: 0, y: 0, width: scene.width, height: scene.height, destWidth: scene.width, destHeight: scene.height, fileType: 'png', success: resolve, fail: reject }, this))
        if (revision !== this.revision || identity !== this.identity) return
        if (!result.tempFilePath) throw new Error('设备未能生成完整长图，请重试。')
        const info = await new Promise((resolve, reject) => uni.getImageInfo({ src: result.tempFilePath, success: resolve, fail: reject }))
        if (revision !== this.revision || identity !== this.identity) return
        if (info.width !== scene.width || info.height !== scene.height) throw new Error('设备无法保存完整尺寸的长图，请换用内存更充足的设备。')
        this.exportPath = result.tempFilePath
        // #ifdef H5
        this.downloadImage()
        // #endif
      } catch (error) {
        if (revision === this.revision) this.exportError = `长图生成失败：${error.message || error.errMsg || '设备容量不足，请重试。'}`
      } finally {
        this.exporting = false
        // Release the large backing canvas after the platform has produced a file.
        this.exportHeight = 1
      }
    },
    previewImage() { if (this.exportPath) uni.previewImage({ urls: [this.exportPath], current: this.exportPath }) },
    downloadImage() {
      // #ifdef H5
      if (!this.exportPath) return
      const link = document.createElement('a')
      link.href = this.exportPath; link.download = `见闻周报_${this.report.week_start}_${this.report.week_end}.png`
      document.body.appendChild(link); link.click(); link.remove()
      // #endif
    },
    saveImage() {
      if (!this.exportPath) return
      // #ifdef H5
      this.downloadImage()
      // #endif
      // #ifndef H5
      const revision = this.revision
      uni.saveImageToPhotosAlbum({ filePath: this.exportPath, success: () => { if (revision === this.revision) this.exportError = ''; uni.showToast({ title: '已保存到相册', icon: 'success' }) }, fail: error => { if (revision === this.revision) this.exportError = `保存失败：${error.errMsg || '请允许相册权限后重试，或打开预览保存。'}` } })
      // #endif
    }
  }
}
</script>

<style scoped>
.weekly-paper { --ink: #152c31; --muted: #657779; --line: #e2e9e5; --paper: #fffef9; background: var(--paper); color: var(--ink); border-radius: 22rpx; overflow: hidden; font-size: 28rpx; }
.report-dark { --ink: #dce8e9; --muted: #9baeb7; --line: #33434d; --paper: #18232d; }
.report-font-small { font-size: 25rpx; }.report-font-large { font-size: 32rpx; }
.report-cover { padding: 40rpx 30rpx 30rpx; display: flex; flex-direction: column; gap: 16rpx; }
.report-title { font-size: 1.5em; font-weight: 700; line-height: 1.4; overflow-wrap: anywhere; }.report-period { color: var(--muted); font-size: .9em; }
.report-badge { color: #568f85; font-size: .85em; }.report-copy { line-height: 1.7; }
.report-stats { display: flex; flex-wrap: wrap; padding: 0 30rpx 20rpx; gap: 20rpx; }.report-stat { min-width: 42%; display: flex; flex-direction: column; gap: 8rpx; }.report-stat-value { font-size: 1.25em; font-weight: 600; }
.report-section { margin: 0 30rpx; padding: 28rpx 0; border-top: 1rpx solid var(--line); }.section-title { display: block; font-size: 1.08em; font-weight: 600; line-height: 1.6; margin-bottom: 16rpx; }
.report-meta { display: block; font-size: .86em; color: var(--muted); line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.report-row { padding: 20rpx 0; border-bottom: 1rpx solid var(--line); }.report-row:last-child { border-bottom: 0; }.row-title { line-height: 1.8; white-space: pre-wrap; overflow-wrap: anywhere; }.report-link .row-title { color: #4e8a98; }.row-arrow { font-weight: 600; }
.data-toggle { background: transparent; color: #4e8a98; font-size: .9em; text-align: left; padding: 10rpx 0; line-height: 1.7; margin: 0; }.data-toggle::after { border: 0; }.data-day { padding: 12rpx 0; }.report-notes .report-meta { margin-bottom: 14rpx; }.report-empty { padding: 12rpx 0; }
.report-export { padding: 0 30rpx 32rpx; }.export-button { background: #28645e; color: #fff; border-radius: 14rpx; font-size: 1em; }.export-button[disabled] { opacity: .5; background: #28645e; color: #fff; }.export-error { display: block; color: #b65d52; font-size: .9em; line-height: 1.8; margin-top: 20rpx; }.export-result { margin-top: 20rpx; }
.export-canvas { position: fixed; left: -10000px; top: 0; pointer-events: none; }
</style>
