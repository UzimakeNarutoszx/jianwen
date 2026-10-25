<template>
  <view :class="['page report', { 'dark-mode': darkMode }]">
    <text v-if="error" role="alert">{{ error }}</text>
    <template v-else-if="report">
      <text class="label">大事报道 · 来源摘要</text>
      <text class="title">{{ report.title }}</text>
      <text class="date">最新报道 {{ report.latest_reported_at.replace('T', ' ') }}</text>
      <view v-for="source in report.sources" :key="source.name" class="source card">
        <text class="name">{{ source.name }}</text>
        <text class="source-title">{{ source.title }}</text>
        <text class="excerpt">{{ source.summary }}</text>
        <text class="date">{{ source.published_at.replace('T', ' ') }}</text>
        <button class="link" @click="openSource(source.url)">查看原文</button>
      </view>
    </template>
    <text v-else>正在加载来源摘要…</text>
  </view>
</template>
<script>
import { getBreakingNewsDetail } from '@/utils/api.js'
export default {
  data: () => ({ report: null, error: '', darkMode: false }),
  async onLoad(options) {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    if (!options.key) { this.error = '未指定大事报道'; return }
    try { this.report = await getBreakingNewsDetail(options.key) }
    catch { this.error = '大事报道暂时不可用，请稍后重试。' }
  },
  methods: {
    openSource(url) {
      if (!/^https:\/\//.test(url)) return
      // #ifdef H5
      window.open(url, '_blank', 'noopener,noreferrer')
      return
      // #endif
      // #ifdef APP-PLUS
      plus.runtime.openURL(url)
      return
      // #endif
      // #ifndef H5
      // #ifndef APP-PLUS
      uni.setClipboardData({ data: url })
      // #endif
      // #endif
    }
  }
}
</script>
<style scoped>
.report { display:flex; flex-direction:column; gap:26rpx; }
.title { font-size:42rpx; font-weight:600; line-height:1.4; text-wrap:balance; }
.label,.name { color:#866121; font-weight:500; }
.source { display:flex; flex-direction:column; gap:22rpx; padding:28rpx; }
.source-title { font-size:32rpx; line-height:1.5; }
.excerpt { font-size:29rpx; line-height:1.9; text-wrap:pretty; }
.date { color:#708087; font-size:24rpx; font-variant-numeric:tabular-nums; }
.link { margin:0; font-size:28rpx; color:#32647c; }
.dark-mode .title { font-weight:360; }.dark-mode .label,.dark-mode .name { font-weight:300; }
</style>

