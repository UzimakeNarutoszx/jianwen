<template>
  <view :class="['page issue-policy-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav ip-nav"><button class="back-button" aria-label="返回" @click="back"><text class="back-symbol"></text></button></view><text class="ip-heading">{{ mine ? '我关注的议题' : '议题追踪' }}</text>
    <text class="ip-muted">沿着时间线，看清进展、变化和依据。</text>
    <view class="ip-actions"><button class="ip-button" @click="toggleMode">{{ mine ? '浏览全部议题' : '我的关注' }}</button></view>
    <text v-if="loading" role="status" class="ip-muted">正在加载议题…</text><text v-if="error" role="alert" class="ip-error">{{ error }}</text>
    <button v-if="error" class="ip-button" @click="load">重试</button>
    <button v-if="needsLogin" class="ip-button primary" @click="login">登录查看关注议题</button>
    <view v-for="item in items" :key="item.issue_key" class="ip-card">
      <text class="ip-muted">{{ stageLabel(item.stage) }}</text><text class="ip-title">{{ item.title }}</text><text class="ip-body">{{ item.status_line }}</text>
      <text class="ip-muted ip-count">{{ item.event_count }} 条进展</text><button class="ip-button primary" @click="open(item.issue_key)">查看时间线</button>
    </view><text v-if="!loading && !error && !needsLogin && !items.length" class="ip-muted">{{ mine ? '还没有关注议题，浏览全部议题后选择关注。' : '议题正在整理，发布后会出现在这里。' }}</text>
  </view>
</template>
<script>
import { getIssues, getFollowedIssues, getAuthToken } from '@/utils/api.js'
import { stageLabel } from '@/utils/issue-policy.js'
export default {
  data: () => ({ mine: false, items: [], loading: false, needsLogin: false, error: '', darkMode: false, fontSize: 'standard', generation: 0 }),
  onLoad(options) { this.mine = options.mine === '1' },
  onShow() { this.darkMode = !!uni.getStorageSync('jianwen_dark_mode'); this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'; this.load() },
  onHide() { this.generation++; this.items = [] },
  methods: {
    stageLabel,
    login() { uni.navigateTo({ url: '/pages/auth/login' }) },
    back() { const fallback = () => uni.switchTab({ url: '/pages/discover/discover' }); if (getCurrentPages().length > 1) uni.navigateBack({ fail: fallback }); else fallback() },
    open(key) { uni.navigateTo({ url: `/pages/issues/detail?key=${encodeURIComponent(key)}` }) },
    toggleMode() { this.mine = !this.mine; this.load() },
    async load() {
      const generation = ++this.generation; this.items = []; this.error = ''; this.loading = true; this.needsLogin = false
      if (this.mine && !getAuthToken()) { this.loading = false; this.needsLogin = true; return }
      try { const data = await (this.mine ? getFollowedIssues() : getIssues()); if (generation === this.generation) this.items = data.map(i => i.issue || i) }
      catch (error) { if (generation === this.generation) this.error = error.message }
      finally { if (generation === this.generation) this.loading = false }
    }
  }
}
</script>
<style src="../../styles/issue-policy.css"></style>
