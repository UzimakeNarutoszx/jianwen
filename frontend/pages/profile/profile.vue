<template>
  <view :class="['page with-tabbar profile-page', settingValues.darkMode ? 'dark-mode' : '', `font-${settingValues.fontSize}`]">
    <view class="topbar profile-topbar">
      <view>
        <text class="page-title">我的</text>
        <text class="subtle">个人资产、兴趣主题和阅读偏好</text>
      </view>
    </view>

    <view class="identity-card card">
      <view class="identity-glow gold"></view>
      <view class="identity-glow blue"></view>
      <view class="identity-main">
        <view class="avatar-shell" @click="chooseAvatar">
          <image class="avatar-image" :src="avatarImage" mode="aspectFill" />
          <view class="avatar-ring"></view>
        </view>
        <view class="account-copy">
          <view class="account-title-row">
            <text class="account-title">{{ accountTitle }}</text>
            <text class="account-badge">{{ accountStatusLabel }}</text>
          </view>
          <text class="account-desc">{{ accountDesc }}</text>
          <view class="sync-row">
            <text class="sync-dot"></text>
            <text class="sync-text">{{ syncStatusText }}</text>
          </view>
        </view>
        <button class="login-button" @click="handleAccountAction">{{ accountActionText }}</button>
      </view>

      <view class="identity-stats">
        <view v-for="item in profileStats" :key="item.label" class="identity-stat">
          <text class="stat-value">{{ item.value }}</text>
          <text class="stat-label">{{ item.label }}</text>
        </view>
      </view>
    </view>

    <view v-if="showProfileEditor" class="edit-card card">
      <view class="field-group">
        <text class="field-label">昵称</text>
        <input v-model.trim="profileForm.nickname" class="field-input" maxlength="16" placeholder="请输入昵称" />
      </view>
      <view class="field-group">
        <text class="field-label">简介</text>
        <textarea v-model.trim="profileForm.bio" class="field-textarea" maxlength="160" placeholder="写一句个人简介" />
      </view>
      <view class="edit-actions">
        <button class="text-button" @click="showProfileEditor = false">取消</button>
        <button class="primary-button save-button" :disabled="profileSaving" @click="saveProfile">
          {{ profileSaving ? '保存中...' : '保存' }}
        </button>
      </view>
    </view>

    <view class="section-head">
      <text class="section-title inline-title">功能</text>
      <text class="section-note">常用入口</text>
    </view>
    <view class="function-row">
      <view v-for="item in menus" :key="item.label" class="function-item" @click="openFeature(item)">
        <view class="function-icon-wrap">
          <image class="function-icon" :src="item.icon" mode="aspectFit" />
        </view>
        <text class="function-label">{{ item.label }}</text>
        <image class="function-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
      </view>
    </view>

    <view class="section-head">
      <text class="section-title inline-title">关注主题</text>
      <text class="section-note">{{ selectedTopics.length }} 个已关注</text>
    </view>
    <view class="topic-cloud card">
      <button
        v-for="(topic, index) in topics"
        :key="topic"
        :class="['topic-pill', topicTone(index), selectedTopics.includes(topic) ? 'selected' : '']"
        hover-class="none"
        @click="toggleTopic(topic)"
      >
        <text>{{ topic }}</text>
      </button>
    </view>

    <view class="section-head">
      <text class="section-title inline-title">设置</text>
      <text class="section-note">阅读 / AI / 合规 / 账号</text>
    </view>
    <view class="settings-stack">
      <view v-for="group in groupedSettings" :key="group.title" class="menu-card card">
        <view class="group-head">
          <text class="group-title">{{ group.title }}</text>
          <text class="group-desc">{{ group.desc }}</text>
        </view>
        <view v-for="item in group.items" :key="item.key" class="menu-item" @click="openSetting(item)">
          <view class="menu-copy">
            <text class="menu-label">{{ item.label }}</text>
            <text v-if="item.desc" class="menu-desc">{{ item.desc }}</text>
          </view>
          <switch v-if="item.type === 'switch'" class="setting-switch" :checked="settingValues[item.key]" color="#1F5F7A" @change="changeSwitch(item.key, $event)" @click.stop="noop" />
          <view v-else-if="item.value" class="setting-value-wrap">
            <text class="setting-value">{{ item.value }}</text>
            <image class="menu-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
          </view>
          <image v-else class="menu-arrow" src="/static/icons/icon-arrow-right.png" mode="aspectFit" />
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import {
  buildFileUrl,
  getCategories,
  getMyProfile,
  getRemoteFollowTopics,
  saveRemoteFollowTopics,
  updateMyProfile,
  uploadMyAvatar
} from '@/utils/api.js'
import { applyTabBarTheme } from '@/utils/theme.js'

const LOCAL_TOPICS_KEY = 'jianwen_follow_topics'

export default {
  data() {
    return {
      menus: [
        { label: '我的收藏', icon: '/static/icons/func-favorite.png', url: '/pages/profile/favorites' },
        { label: '最近看过', icon: '/static/icons/func-history.png', url: '/pages/profile/history' },
        { label: '问问记录', icon: '/static/icons/func-chat.png', url: '/pages/profile/ask-records' }
      ],
      topics: [],
      selectedTopics: [],
      authUser: null,
      showProfileEditor: false,
      profileSaving: false,
      topicSaving: false,
      profileForm: { nickname: '', bio: '' },
      settingValues: { darkMode: false, showSources: true, fontSize: 'standard' }
    }
  },
  computed: {
    fontSizeLabel() {
      const labels = { small: '小字', standard: '标准', large: '大字' }
      return labels[this.settingValues.fontSize] || labels.standard
    },
    accountStatusLabel() { return this.authUser ? '已登录' : '未登录' },
    syncStatusText() {
      if (!this.authUser) return '本机保存，登录后开启云端同步'
      return this.topicSaving ? '关注主题同步中' : '收藏、历史和主题已连接云端'
    },
    profileStats() {
      return [
        { label: '关注主题', value: this.selectedTopics.length || 0 },
        { label: '阅读字号', value: this.fontSizeLabel },
        { label: '资料状态', value: this.authUser ? '云端' : '本机' }
      ]
    },
    accountTitle() { return this.authUser ? this.authUser.nickname : '未登录' },
    accountDesc() {
      if (!this.authUser) return '登录后可同步收藏、阅读历史、关注主题和对话记录。'
      return this.authUser.bio || `手机号 ${this.authUser.phone}`
    },
    accountActionText() { return this.authUser ? '编辑' : '登录' },
    avatarImage() {
      return this.authUser && this.authUser.avatar_path ? buildFileUrl(this.authUser.avatar_path) : '/static/brand-icon.png'
    },
    groupedSettings() {
      const groups = [
        {
          title: '阅读',
          desc: '字号和夜间阅读',
          items: [
            { key: 'fontSize', label: '字号', type: 'select', value: this.fontSizeLabel },
            { key: 'darkMode', label: '深色模式', type: 'switch', desc: '切换为低亮度深蓝黑界面' }
          ]
        },
        {
          title: 'AI',
          desc: '回答展示偏好',
          items: [
            { key: 'showSources', label: 'AI回答默认显示来源', type: 'switch', desc: '保留依据与出处，方便核对' }
          ]
        },
        {
          title: '合规',
          desc: '来源和协议',
          items: [
            { key: 'legal', label: '隐私政策与用户协议', type: 'link' },
            { key: 'sources', label: '内容来源说明', type: 'link' }
          ]
        }
      ]
      groups.push({ title: '关于见闻', desc: '产品动态', items: [{ key: 'changelog', label: '更新日志', type: 'link' }] })
      groups.push({
        title: '账号',
        desc: this.authUser ? '登录状态' : '云端同步',
        items: this.authUser
          ? [{ key: 'logout', label: '退出登录', type: 'link' }]
          : [{ key: 'login', label: '登录 / 同步资料', type: 'link', desc: '同步收藏、历史、关注主题和问问记录' }]
      })
      return groups
    }
  },
  onShow() {
    this.loadSettings()
    this.loadAuthUser()
    this.loadTopics()
    applyTabBarTheme(this.settingValues.darkMode)
  },
  methods: {
    loadAuthUser() {
      this.authUser = uni.getStorageSync('jianwen_auth_user') || null
      if (this.authUser) {
        this.profileForm.nickname = this.authUser.nickname || ''
        this.profileForm.bio = this.authUser.bio || ''
        this.refreshProfile()
      }
    },
    async loadTopics() {
      try {
        const categories = await getCategories()
        this.topics = categories.map(item => item.name)
      } catch (error) {
        this.topics = ['党和国家', '共产党', '时政大事', '就业', '住房', '科技']
      }

      const localTopics = uni.getStorageSync(LOCAL_TOPICS_KEY)
      if (Array.isArray(localTopics) && localTopics.length) {
        this.selectedTopics = localTopics
      } else if (!this.selectedTopics.length) {
        this.selectedTopics = this.topics.slice(0, 3)
      }

      if (this.authUser) {
        try {
          const remoteTopics = await getRemoteFollowTopics()
          if (Array.isArray(remoteTopics) && remoteTopics.length) {
            this.selectedTopics = remoteTopics
            uni.setStorageSync(LOCAL_TOPICS_KEY, remoteTopics)
          } else {
            await this.persistTopics()
          }
        } catch (error) {}
      }
    },
    async refreshProfile() {
      try {
        const profile = await getMyProfile()
        this.authUser = profile
        uni.setStorageSync('jianwen_auth_user', profile)
        this.profileForm.nickname = profile.nickname || ''
        this.profileForm.bio = profile.bio || ''
        if (Array.isArray(profile.followed_topics) && profile.followed_topics.length) {
          this.selectedTopics = profile.followed_topics
          uni.setStorageSync(LOCAL_TOPICS_KEY, profile.followed_topics)
        }
        } catch (error) {
          uni.removeStorageSync('jianwen_auth_token')
          uni.removeStorageSync('jianwen_auth_user')
          uni.removeStorageSync('jianwen_login_expires_at')
          this.authUser = null
        }
    },
    loadSettings() {
      const showSources = uni.getStorageSync('jianwen_show_sources')
      this.settingValues.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
      this.settingValues.showSources = showSources === '' ? true : showSources !== false
      this.settingValues.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
    },
    handleAccountAction() {
      if (this.authUser) {
        this.profileForm.nickname = this.authUser.nickname || ''
        this.profileForm.bio = this.authUser.bio || ''
        this.showProfileEditor = !this.showProfileEditor
        return
      }
      uni.navigateTo({ url: '/pages/auth/login' })
    },
    async saveProfile() {
      if (!this.profileForm.nickname) {
        uni.showToast({ title: '请填写昵称', icon: 'none' })
        return
      }
      this.profileSaving = true
      try {
        const profile = await updateMyProfile({ nickname: this.profileForm.nickname, bio: this.profileForm.bio })
        this.authUser = profile
        uni.setStorageSync('jianwen_auth_user', profile)
        this.showProfileEditor = false
        uni.showToast({ title: '已保存', icon: 'success' })
      } catch (error) {
        uni.showToast({ title: error.message || '保存失败', icon: 'none' })
      } finally {
        this.profileSaving = false
      }
    },
    chooseAvatar() {
      if (!this.authUser) {
        this.handleAccountAction()
        return
      }
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: async result => {
          const filePath = result.tempFilePaths && result.tempFilePaths[0]
          if (!filePath) return
          try {
            const profile = await uploadMyAvatar(filePath)
            this.authUser = profile
            uni.setStorageSync('jianwen_auth_user', profile)
            uni.showToast({ title: '头像已更新', icon: 'success' })
          } catch (error) {
            uni.showToast({ title: error.message || '头像上传失败', icon: 'none' })
          }
        }
      })
    },
    async toggleTopic(topic) {
      this.selectedTopics = this.selectedTopics.includes(topic)
        ? this.selectedTopics.filter(item => item !== topic)
        : this.selectedTopics.concat(topic)
      await this.persistTopics()
    },
    async persistTopics() {
      uni.setStorageSync(LOCAL_TOPICS_KEY, this.selectedTopics)
      if (!this.authUser || this.topicSaving) return

      this.topicSaving = true
      try {
        const saved = await saveRemoteFollowTopics(this.selectedTopics)
        uni.setStorageSync(LOCAL_TOPICS_KEY, saved)
      } catch (error) {
        uni.showToast({ title: '关注主题暂未同步，已保存在本机', icon: 'none' })
      } finally {
        this.topicSaving = false
      }
    },
    topicTone(index) {
      return `tone-${index % 5}`
    },
    openFeature(item) { uni.navigateTo({ url: item.url }) },
    changeSwitch(key, event) {
      this.settingValues[key] = event.detail.value
      this.saveSwitch(key)
    },
    noop() {},
    saveSwitch(key) {
      const storageKeys = { darkMode: 'jianwen_dark_mode', showSources: 'jianwen_show_sources' }
      if (storageKeys[key]) uni.setStorageSync(storageKeys[key], this.settingValues[key])
      if (key === 'darkMode') applyTabBarTheme(this.settingValues.darkMode)
    },
    openSetting(item) {
      if (item.type === 'switch') {
        this.settingValues[item.key] = !this.settingValues[item.key]
        this.saveSwitch(item.key)
        return
      }
      const pageMap = { changelog: '/pages/settings/changelog', fontSize: '/pages/settings/font-size', legal: '/pages/settings/legal', sources: '/pages/settings/sources' }
      if (item.key === 'login') {
        uni.navigateTo({ url: '/pages/auth/login' })
        return
      }
      if (item.key === 'logout') {
        uni.removeStorageSync('jianwen_auth_token')
        uni.removeStorageSync('jianwen_auth_user')
        uni.removeStorageSync('jianwen_login_expires_at')
        this.authUser = null
        this.showProfileEditor = false
        uni.showToast({ title: '已退出登录', icon: 'none' })
        return
      }
      if (pageMap[item.key]) uni.navigateTo({ url: pageMap[item.key] })
    }
  }
}
</script>

<style scoped>
.profile-page {
  overflow: hidden;
  background:
    radial-gradient(circle at 16% 0%, rgba(214, 184, 112, 0.3) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(31, 95, 122, 0.2) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 470rpx, #F5F7F4 100%);
}

.topbar > view,
.account-copy,
.edit-card,
.field-group,
.menu-copy,
.identity-card,
.settings-stack,
.group-head {
  display: flex;
  flex-direction: column;
}

.profile-topbar {
  gap: 24rpx;
}

.topbar > view {
  gap: 12rpx;
}

.topbar-status,
.account-title-row,
.sync-row,
.identity-main,
.identity-stats,
.section-head,
.function-row,
.function-item,
.function-icon-wrap,
.setting-value-wrap,
.menu-item {
  display: flex;
  align-items: center;
}

.topbar-status {
  display: inline-flex;
  align-items: center;
  position: relative;
  z-index: 1;
  flex: 0 0 auto;
  flex-wrap: nowrap;
  gap: 10rpx;
  min-height: 52rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(212, 170, 78, 0.34);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.66);
  color: #7C5C18;
  font-size: 22rpx;
  font-weight: 900;
  word-break: keep-all;
  overflow-wrap: normal;
  white-space: nowrap;
}

.status-dot,
.sync-dot {
  flex: 0 0 12rpx;
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
  box-shadow: 0 0 18rpx rgba(212, 170, 78, 0.66);
}

.identity-card {
  position: relative;
  gap: 34rpx;
  padding: 34rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.58)),
    linear-gradient(135deg, rgba(31,95,122,0.08), rgba(212,170,78,0.12));
}

.identity-glow {
  position: absolute;
  border-radius: 999rpx;
  pointer-events: none;
}

.identity-glow.gold {
  top: -92rpx;
  right: -82rpx;
  width: 250rpx;
  height: 250rpx;
  background: rgba(212, 170, 78, 0.2);
}

.identity-glow.blue {
  left: -86rpx;
  bottom: 22rpx;
  width: 200rpx;
  height: 200rpx;
  background: rgba(31, 95, 122, 0.12);
}

.identity-main {
  position: relative;
  z-index: 1;
  gap: 28rpx;
  width: 100%;
}

.avatar-shell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 116rpx;
  width: 116rpx;
  height: 116rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 30rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(230,240,244,0.78)),
    linear-gradient(135deg, rgba(212,170,78,0.16), transparent);
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.14);
  overflow: hidden;
}

.avatar-image {
  width: 98rpx;
  height: 98rpx;
  border-radius: 24rpx;
}

.avatar-ring {
  position: absolute;
  inset: 8rpx;
  border: 2rpx solid rgba(212, 170, 78, 0.38);
  border-radius: 24rpx;
  pointer-events: none;
}

.account-copy {
  flex: 1;
  min-width: 0;
  gap: 12rpx;
}

.account-title-row {
  flex-wrap: nowrap;
  gap: 12rpx;
  min-width: 0;
}

.account-title {
  flex: 0 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #14212B;
  font-size: 36rpx;
  line-height: 1.2;
  font-weight: 900;
}

.account-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-width: 76rpx;
  height: 38rpx;
  min-height: 38rpx;
  padding: 0 14rpx;
  border: 1rpx solid rgba(31,95,122,0.16);
  border-radius: 999rpx;
  background: rgba(31,95,122,0.09);
  color: #1F5F7A;
  font-size: 21rpx;
  line-height: 38rpx;
  font-weight: 900;
  word-break: keep-all;
  overflow-wrap: normal;
  white-space: nowrap;
}

.status-text {
  display: block;
  flex: 0 0 auto;
  word-break: keep-all;
  overflow-wrap: normal;
  white-space: nowrap;
}

.account-desc {
  color: #5C6873;
  font-size: 24rpx;
  line-height: 1.55;
}

.sync-row {
  flex-wrap: nowrap;
  gap: 10rpx;
  min-width: 0;
  max-width: 100%;
  color: #7C8790;
  font-size: 22rpx;
  line-height: 1.35;
  font-weight: 800;
  word-break: keep-all;
  overflow-wrap: normal;
  white-space: nowrap;
}

.sync-text {
  display: block;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: keep-all;
  overflow-wrap: normal;
  white-space: nowrap;
}

.login-button {
  flex: 0 0 auto;
  min-width: 112rpx;
  min-height: 66rpx;
  padding: 0 22rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  font-size: 26rpx;
  font-weight: 900;
  box-shadow: 0 16rpx 34rpx rgba(31, 95, 122, 0.22);
}

.identity-stats {
  position: relative;
  z-index: 1;
  gap: 16rpx;
}

.identity-stat {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 8rpx;
  padding: 22rpx 18rpx;
  border: 1rpx solid rgba(255,255,255,0.74);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.58);
  box-shadow: 0 14rpx 34rpx rgba(20, 33, 43, 0.06);
}

.stat-value {
  color: #143E52;
  font-size: 30rpx;
  line-height: 1;
  font-weight: 900;
}

.stat-label {
  color: #7C8790;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 800;
}

.edit-card {
  position: relative;
  gap: 28rpx;
  margin-top: 30rpx;
  padding: 36rpx;
  border-color: rgba(255,255,255,0.92);
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(247,250,252,0.72)),
    linear-gradient(135deg, rgba(31,95,122,0.06), rgba(212,170,78,0.08));
}

.field-group {
  gap: 12rpx;
}

.field-label {
  color: #14212B;
  font-size: 25rpx;
  font-weight: 800;
}

.field-input,
.field-textarea {
  width: 100%;
  padding: 0 22rpx;
  border: 1rpx solid rgba(31,95,122,0.14);
  border-radius: 18rpx;
  background: rgba(247,250,252,0.84);
  color: #14212B;
  font-size: 27rpx;
}

.field-input {
  height: 78rpx;
}

.field-textarea {
  min-height: 132rpx;
  padding-top: 18rpx;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 16rpx;
}

.text-button,
.save-button {
  flex: 0 0 144rpx;
  min-height: 64rpx;
  border-radius: 999rpx;
  font-size: 25rpx;
  font-weight: 900;
}

.text-button {
  border: 1rpx solid rgba(31,95,122,0.16);
  background: rgba(230,240,244,0.82);
  color: #1F5F7A;
}

.section-head {
  justify-content: space-between;
  gap: 24rpx;
  margin: 70rpx 0 30rpx;
}

.inline-title {
  margin: 0;
}

.section-note {
  flex: 0 0 auto;
  color: #8A949E;
  font-size: 23rpx;
  line-height: 1.35;
  text-align: right;
  white-space: nowrap;
}

.function-row {
  gap: 22rpx;
}

.function-item {
  position: relative;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 22rpx;
  min-height: 208rpx;
  padding: 28rpx 22rpx;
  border: 1rpx solid rgba(255,255,255,0.88);
  border-radius: 28rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.84), rgba(255,255,255,0.58)),
    linear-gradient(135deg, rgba(31,95,122,0.08), rgba(212,170,78,0.1));
  box-shadow: 0 20rpx 48rpx rgba(31, 47, 58, 0.09);
  overflow: hidden;
}

.function-item::after {
  content: '';
  position: absolute;
  top: -34rpx;
  right: -34rpx;
  width: 102rpx;
  height: 102rpx;
  border-radius: 999rpx;
  background: rgba(212, 170, 78, 0.13);
}

.function-icon-wrap {
  justify-content: center;
  width: 96rpx;
  height: 96rpx;
  border: 1rpx solid rgba(31,95,122,0.1);
  border-radius: 24rpx;
  background: rgba(230,240,244,0.86);
  box-shadow: inset 0 0 0 1rpx rgba(255,255,255,0.62);
}

.function-icon {
  width: 56rpx;
  height: 56rpx;
}

.function-label {
  position: relative;
  z-index: 1;
  color: #14212B;
  font-size: 26rpx;
  line-height: 1.25;
  font-weight: 900;
}

.function-arrow {
  position: absolute;
  right: 20rpx;
  bottom: 22rpx;
  width: 28rpx;
  height: 28rpx;
  opacity: 0.5;
}

.topic-cloud {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 18rpx 16rpx;
  min-height: 212rpx;
  padding: 34rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.86), rgba(255,255,255,0.58)),
    radial-gradient(circle at 88% 18%, rgba(212,170,78,0.16), transparent 220rpx),
    radial-gradient(circle at 10% 90%, rgba(31,95,122,0.1), transparent 220rpx);
}

.topic-pill {
  flex: 0 0 auto;
  min-width: 126rpx;
  height: 72rpx;
  min-height: 72rpx;
  padding: 0 24rpx;
  border: 1rpx solid rgba(31,95,122,0.1);
  border-radius: 999rpx;
  background: rgba(247,250,252,0.78);
  color: #52616D;
  font-size: 25rpx;
  line-height: 72rpx;
  font-weight: 900;
  box-shadow: 0 10rpx 24rpx rgba(20, 33, 43, 0.05);
  white-space: nowrap;
}

.topic-pill.tone-1,
.topic-pill.tone-4 {
  font-size: 27rpx;
}

.topic-pill.tone-2 {
  min-width: 150rpx;
}

.topic-pill.tone-3 {
  border-color: rgba(212,170,78,0.22);
  background: rgba(250,246,235,0.82);
}

.topic-pill.selected {
  border-color: rgba(212,170,78,0.72);
  background:
    linear-gradient(135deg, #1F5F7A, #143E52),
    linear-gradient(135deg, rgba(212,170,78,0.18), transparent);
  color: #FFFFFF;
  box-shadow: 0 16rpx 32rpx rgba(31, 95, 122, 0.2);
  transform: none;
}

.topic-pill text {
  white-space: nowrap;
}

.settings-stack {
  gap: 28rpx;
}

.menu-card {
  padding: 28rpx 32rpx 6rpx;
  overflow: hidden;
}

.group-head {
  gap: 8rpx;
  padding-bottom: 22rpx;
  border-bottom: 1rpx solid rgba(31,95,122,0.1);
}

.group-title {
  color: #1F5F7A;
  font-size: 25rpx;
  line-height: 1.35;
  font-weight: 900;
}

.group-desc {
  color: #8A949E;
  font-size: 22rpx;
  line-height: 1.35;
}

.menu-item {
  justify-content: space-between;
  gap: 24rpx;
  min-height: 104rpx;
  border-bottom: 1rpx solid rgba(31,95,122,0.1);
}

.menu-item:last-child {
  border-bottom: none;
}

.menu-copy {
  flex: 1;
  gap: 6rpx;
  min-width: 0;
  padding: 20rpx 0;
}

.menu-label {
  color: #14212B;
  font-size: 28rpx;
}

.menu-desc,
.setting-value {
  color: #8A949E;
  font-size: 24rpx;
}

.setting-value-wrap {
  gap: 10rpx;
}

.menu-arrow {
  width: 30rpx;
  height: 30rpx;
  opacity: 0.58;
}

.font-large .account-title {
  font-size: 40rpx;
}

.font-large .account-desc,
.font-large .menu-label,
.font-large .topic-pill,
.font-large .function-label {
  font-size: 29rpx;
}

.font-large .topic-pill {
  min-height: 72rpx;
  line-height: 72rpx;
}

.font-small .account-title {
  font-size: 32rpx;
}

.font-small .account-desc,
.font-small .menu-label,
.font-small .topic-pill,
.font-small .function-label {
  font-size: 24rpx;
}

.dark-mode.profile-page {
  background:
    radial-gradient(circle at 16% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .topbar-status,
.dark-mode .identity-card,
.dark-mode .edit-card,
.dark-mode .function-item,
.dark-mode .topic-cloud,
.dark-mode .menu-card,
.dark-mode .identity-stat {
  border-color: rgba(126,184,209,0.16) !important;
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.76)),
    linear-gradient(135deg, rgba(126,184,209,0.1), rgba(187,141,45,0.08)) !important;
  box-shadow: 0 24rpx 62rpx rgba(0, 0, 0, 0.24) !important;
}

.dark-mode .avatar-shell,
.dark-mode .function-icon-wrap,
.dark-mode .field-input,
.dark-mode .field-textarea,
.dark-mode .text-button {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(32,56,74,0.72) !important;
}

.dark-mode .account-badge,
.dark-mode .topic-pill {
  border-color: rgba(126,184,209,0.2) !important;
  background: rgba(32,56,74,0.82) !important;
  color: #7EB8D1 !important;
}

.dark-mode .topic-pill.selected {
  border-color: rgba(212,170,78,0.64) !important;
  background: linear-gradient(135deg, rgba(31,95,122,0.9), rgba(16,39,55,0.94)) !important;
  color: #FFFFFF !important;
}

.dark-mode .account-title,
.dark-mode .stat-value,
.dark-mode .field-label,
.dark-mode .function-label,
.dark-mode .menu-label {
  color: #F4F7FA !important;
}

.dark-mode .account-desc,
.dark-mode .sync-row,
.dark-mode .stat-label,
.dark-mode .section-note,
.dark-mode .menu-desc,
.dark-mode .setting-value,
.dark-mode .group-desc,
.dark-mode .field-input,
.dark-mode .field-textarea {
  color: #B6C2CC !important;
}

.dark-mode .group-title {
  color: #7EB8D1 !important;
}

.dark-mode .topbar-status {
  color: #D4AA4E !important;
}

.dark-mode .group-head,
.dark-mode .menu-item {
  border-bottom-color: rgba(126,184,209,0.14) !important;
}
</style>
