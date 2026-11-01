<template>
  <view :class="['page settings-page changelog-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav">
      <button class="back-button" aria-label="返回" @click="goBack"><text class="back-symbol"></text></button>
    </view>
    <view class="settings-head">
      <text class="head-kicker">关于见闻</text>
      <text class="page-title">更新日志</text>
      <text class="subtle">网站与 App 的每一次变化，最新的在最上面。</text>
    </view>
    <view class="filters">
      <button v-for="filter in filters" :key="filter.id" :class="['filter', active === filter.id ? 'selected' : '']" @click="active = filter.id">{{ filter.label }}</button>
    </view>
    <view v-if="loading" class="state" aria-live="polite">正在加载更新日志…</view>
    <view v-else-if="error" class="state" aria-live="polite">
      <text>{{ error }}</text>
      <button class="retry-button" @click="load">重新加载</button>
    </view>
    <template v-else>
      <text class="count">{{ activeLabel }} · {{ itemCount }} 条更新</text>
      <view v-if="!visibleEntries.length" class="state">暂无更新记录</view>
      <view v-for="entry in visibleEntries" :key="entry.date + entry.title" class="card entry">
        <text class="entry-date">{{ entry.date }}</text>
        <text class="entry-title">{{ entry.title }}</text>
        <view v-for="group in entry.groups" :key="group.title" class="group">
          <text class="group-title">{{ group.title }}</text>
          <view v-for="(item, index) in group.items" :key="index" class="item">
            <text class="bullet">·</text><text class="item-text">{{ item.text }}</text>
          </view>
        </view>
      </view>
    </template>
  </view>
</template>

<script>
import { getChangelog } from '@/utils/api.js'

export default {
  data() {
    return {
      darkMode: false, fontSize: 'standard', loading: false, error: '', entries: [], active: 'all',
      filters: [{ id: 'all', label: '全部' }, { id: 'web', label: '网站' }, { id: 'app', label: 'App' }, { id: 'ai', label: '后端与 AI' }]
    }
  },
  computed: {
    visibleEntries() {
      return this.entries.map(entry => ({
        ...entry,
        groups: entry.groups.map(group => ({
          ...group, items: group.items.filter(item => this.active === 'all' || item.types.includes(this.active))
        })).filter(group => group.items.length)
      })).filter(entry => entry.groups.length)
    },
    activeLabel() { return this.filters.find(filter => filter.id === this.active).label },
    itemCount() { return this.visibleEntries.reduce((sum, entry) => sum + entry.groups.reduce((total, group) => total + group.items.length, 0), 0) }
  },
  onLoad() { this.load() },
  onShow() {
    this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
    this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
  },
  methods: {
    async load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        const data = await getChangelog()
        if (!Array.isArray(data.entries)) throw new Error('更新日志内容格式错误')
        this.entries = [...data.entries].sort((a, b) => b.date.localeCompare(a.date))
      } catch (error) { this.error = error.message || '更新日志加载失败，请重试' }
      finally { this.loading = false }
    },
    goBack() {
      if (getCurrentPages().length > 1) uni.navigateBack()
      else uni.switchTab({ url: '/pages/profile/profile' })
    }
  }
}
</script>

<style scoped>
.settings-nav { display: flex; margin-bottom: 34rpx; }
.settings-head { display: flex; flex-direction: column; gap: 18rpx; padding: 34rpx; margin-bottom: 32rpx; }
.head-kicker, .entry-date, .group-title { color: #1f5f7a; font-weight: 700; }
.head-kicker, .entry-date { font-size: 24rpx; }
.filters { display: flex; flex-wrap: wrap; gap: 14rpx; margin-bottom: 24rpx; }
.filter { margin: 0; padding: 0 24rpx; border: 1rpx solid rgba(31,95,122,.2); border-radius: 40rpx; background: transparent; color: #1f5f7a; font-size: 26rpx; line-height: 2.5; }
.filter::after, .retry-button::after { border: 0; }
.filter.selected { background: #1f5f7a; color: #fff; }
.count { display: block; margin-bottom: 26rpx; color: #687984; font-size: 24rpx; }
.entry { display: flex; flex-direction: column; padding: 32rpx; margin-bottom: 28rpx; }
.entry-title { margin-top: 14rpx; font-size: 32rpx; font-weight: 800; color: #14212b; line-height: 1.5; }
.group { margin-top: 28rpx; }
.group-title { display: block; margin-bottom: 12rpx; font-size: 26rpx; }
.item { display: flex; gap: 12rpx; margin-top: 10rpx; color: #3f4f59; font-size: 28rpx; line-height: 1.8; }
.bullet { flex-shrink: 0; }
.item-text { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.state { display: flex; flex-direction: column; align-items: center; gap: 28rpx; padding: 48rpx 0; color: #687984; font-size: 28rpx; text-align: center; }
.retry-button { color: #fff; background: #1f5f7a; border-radius: 40rpx; font-size: 28rpx; }
.font-small .item { font-size: 26rpx; }
.font-large .item { font-size: 34rpx; }
.font-large .entry-title { font-size: 38rpx; }
.font-large .group-title, .font-large .filter { font-size: 30rpx; }
.dark-mode .head-kicker, .dark-mode .entry-date, .dark-mode .group-title, .dark-mode .filter { color: #7eb8d1; }
.dark-mode .filter { border-color: rgba(126,184,209,.3); }
.dark-mode .filter.selected { background: #7eb8d1; color: #0e1720; }
.dark-mode .entry-title { color: #f4f7fa; }
.dark-mode .item { color: #c9d5dd; }
.dark-mode .count, .dark-mode .state { color: #9aaab4; }
</style>
