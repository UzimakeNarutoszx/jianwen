<template>
  <view :class="['page issue-policy-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="settings-nav ip-nav"><button class="back-button" aria-label="返回" @click="back"><text class="back-symbol"></text></button></view><text v-if="loading" class="ip-muted" role="status">正在加载时间线…</text>
    <text v-if="error" class="ip-error" role="alert">{{ error }}</text><button v-if="error" class="ip-button" @click="load">重新加载</button>
    <template v-if="issue">
      <text class="ip-muted">{{ stageLabel(issue.stage) }}</text><text class="ip-heading">{{ issue.title }}</text><text class="ip-body">{{ issue.status_line }}</text>
      <view class="ip-actions"><button class="ip-button primary" :disabled="busy" @click="toggleFollow">{{ issue.is_following ? '取消关注' : '关注议题' }}</button><button class="ip-button" @click="ask">围绕议题问问</button><button v-if="issue.is_following" class="ip-button" :disabled="busy" @click="seen">标记当前进展已读</button></view>
      <text class="ip-muted" role="status">{{ message }}</text>
      <view v-for="policy in issue.policy_checks || []" :key="policy.policy_key" class="ip-card"><text class="ip-title">{{ policy.title }}</text><button class="ip-button" @click="openPolicy(policy.policy_key)">匿名政策自查</button></view>
      <text class="ip-title">进展时间线</text><text v-if="issue.is_following && seenBoundary" class="ip-muted">上次看到这里：发布版本 {{ seenBoundary }}；标有「有新进展」的是此后新增或修订的内容。</text><view class="ip-timeline">
        <view v-for="(event, index) in issue.events" :key="event.event_id" :class="['ip-card', 'ip-event', index > 1 && !expandedEvents[event.event_id] ? 'is-collapsed' : '']"><text class="ip-muted">{{ event.event_date }}{{ event.updated_version > seenBoundary ? ' · 有新进展' : '' }}{{ event.historical ? ' · 历史进展' : '' }}</text><text class="ip-title">第 {{ event.position }} 条进展</text><view class="ip-event-body"><view><text class="ip-body">{{ event.delta_summary }}</text><button v-if="event.article_id" class="ip-button" @click="article(event.article_id)">阅读关联文章</button><button v-for="(source, sourceIndex) in event.references || []" :key="sourceIndex" class="ip-button" @click="official(source.url)">{{ source.title || source.org || '官方依据' }}</button></view></view><button v-if="index > 1" class="ip-button" @click="toggleEvent(event.event_id)">{{ expandedEvents[event.event_id] ? '收起' : '展开' }}</button></view>
      </view><text v-if="!issue.events.length" class="ip-muted">暂无已发布进展。</text>
    </template>
  </view>
</template>
<script>
import { getIssue, followIssue, markIssueSeen, getAuthToken } from '@/utils/api.js'
import { pendingQuestion, openOfficialUrl, stageLabel } from '@/utils/issue-policy.js'
export default {
  data: () => ({ key: '', issue: null, loading: false, busy: false, error: '', message: '', darkMode: false, fontSize: 'standard', generation: 0, seenBoundary: 0, expandedEvents: {} }),
  onLoad(options) { this.key = options.key || '' },
  onShow() { this.darkMode = !!uni.getStorageSync('jianwen_dark_mode'); this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'; this.load() },
  onHide() { this.generation++; this.issue = null },
  methods: {
    stageLabel,
    official: openOfficialUrl,
    back() { const fallback = () => uni.redirectTo({ url: '/pages/issues/index' }); if (getCurrentPages().length > 1) uni.navigateBack({ fail: fallback }); else fallback() },
    article(id) { uni.navigateTo({ url: `/pages/article/detail?id=${encodeURIComponent(id)}` }) },
    openPolicy(key) { uni.navigateTo({ url: `/pages/policy/detail?key=${encodeURIComponent(key)}` }) },
    ask() { pendingQuestion('issue', this.issue.issue_key || this.key, this.issue.title) },
    toggleEvent(id) { this.expandedEvents[id] = !this.expandedEvents[id] },
    login() { if (getAuthToken()) return true; uni.navigateTo({ url: '/pages/auth/login' }); return false },
    async load() { const generation = ++this.generation; this.loading = true; this.error = ''; try { const data = await getIssue(this.key); if (generation === this.generation) { this.issue = data; this.key = data.issue_key || this.key; this.seenBoundary = Number(data.last_seen_version || 0); this.expandedEvents = {}; if (data.is_following && data.published_version) markIssueSeen(this.key, data.published_version).catch(() => {}) } } catch (e) { if (generation === this.generation) this.error = e.message } finally { if (generation === this.generation) this.loading = false } },
    async toggleFollow() { if (!this.login() || this.busy) return; this.busy = true; const current = this.issue; try { const data = await followIssue(this.key, !current.is_following); if (this.issue === current) { current.is_following = data.is_following; this.message = data.is_following ? '已关注，今日会提醒新进展。' : '已取消关注。' } } catch (e) { this.message = [409, 410].includes(e.status) ? '议题版本已变化，请重新加载后再操作。' : e.message } finally { this.busy = false } },
    async seen() { if (!this.login() || this.busy) return; this.busy = true; const current = this.issue; const version = current.published_version; try { const data = await markIssueSeen(this.key, version); if (this.issue === current) { current.last_seen_version = data.last_seen_version; this.message = '当前进展已读；后续发布仍会提醒。' } } catch (e) { this.message = [409, 410].includes(e.status) ? '议题版本已变化，请重新加载后再操作。' : e.message } finally { this.busy = false } }
  }
}
</script>
<style src="../../styles/issue-policy.css"></style>
