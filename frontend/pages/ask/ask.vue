<template>
  <view :class="['ask-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="ask-scroll">
      <view class="topbar ask-topbar">
        <view>
          <text class="page-title">问问见闻</text>
          <text class="subtle">政策研究助理工作台</text>
        </view>
        <view class="top-status">
          <text class="status-dot"></text>
          <text class="status-text">可提问</text>
        </view>
      </view>

      <view class="ask-hero">
        <view class="hero-grid"></view>
        <view class="hero-accent-line"></view>
        <view class="ask-orb">
          <image class="ask-orb-icon" src="/static/brand-icon.png" mode="aspectFit" />
        </view>
        <view class="ask-hero-copy">
          <text class="hero-kicker">AI RESEARCH DESK</text>
          <text class="hero-title">问清楚，看明白</text>
          <text class="hero-copy">追问文章，保留依据入口。</text>
        </view>
        <view class="hero-metrics">
          <view class="metric-chip primary">
            <text class="metric-value">AI</text>
            <text class="metric-label">梳理脉络</text>
          </view>
          <view class="metric-chip">
            <text class="metric-value">来源</text>
            <text class="metric-label">保留依据</text>
          </view>
          <view class="metric-chip">
            <text class="metric-value">追问</text>
            <text class="metric-label">继续展开</text>
          </view>
        </view>
      </view>

      <view class="section-head">
        <text class="section-eyebrow">PROMPTS</text>
        <text class="section-title">今日可聊</text>
      </view>
      <scroll-view class="prompt-scroll" scroll-x>
        <view class="prompt-row">
          <button v-for="(prompt, index) in prompts" :key="prompt" class="prompt-card" @click="askPrompt(prompt)">
            <view class="prompt-icon-wrap">
              <text class="prompt-index">{{ promptNumber(index) }}</text>
            </view>
            <text class="prompt-text">{{ prompt }}</text>
          </button>
        </view>
      </scroll-view>

      <view v-if="messages.length" class="chat-card card">
        <view class="chat-card-head">
          <view>
            <text class="chat-eyebrow">CONVERSATION</text>
            <text class="chat-title">研究对话</text>
          </view>
          <text class="chat-state">{{ messages.length }} 条</text>
        </view>
        <view
          v-for="message in messages"
          :id="`message-${message.id}`"
          :key="message.id"
          :class="['message', message.role]"
        >
          <view class="message-meta">
            <view class="message-avatar">
              <image
                v-if="message.role === 'assistant'"
                class="message-avatar-icon"
                src="/static/icons/tab-ask-active.png"
                mode="aspectFit"
              />
              <text v-else>{{ message.role === 'user' ? '你' : '文' }}</text>
            </view>
            <text class="message-label">{{ message.role === 'user' ? '你' : message.role === 'context' ? '文章上下文' : '见闻助理' }}</text>
          </view>
          <view class="message-bubble">
            <rich-text
              v-if="message.role === 'assistant'"
              class="message-text markdown-message"
              :nodes="renderMarkdown(message.text)"
            />
            <text v-else class="message-text">{{ message.text }}</text>
            <view v-if="message.role === 'assistant' && message.thinkingLabel" class="thinking-bar">
              <text class="thinking-pulse"></text>
              <text class="message-thinking">{{ message.thinkingLabel }}</text>
            </view>
            <view v-if="message.sources && showSources" class="message-source">
              <view class="source-head">
                <image class="source-icon" src="/static/icons/icon-search.png" mode="aspectFit" />
                <text>来源入口</text>
              </view>
              <text class="source-text">{{ message.sources }}</text>
            </view>
          </view>
        </view>
      </view>

      <view v-if="hasAsked && followups.length" class="followup-card">
        <text class="followup-title">下一步可以问</text>
        <scroll-view class="followup-scroll" scroll-x>
          <view class="followup-row">
            <button v-for="item in followups" :key="item" class="followup-chip" @click="askPrompt(item)">
              {{ item }}
            </button>
          </view>
        </scroll-view>
      </view>
    </view>

    <view v-if="chatNavItems.length > 1" class="chat-nav-panel">
      <button
        v-for="item in chatNavItems"
        :key="item.id"
        :class="['chat-nav-item', activeNavId === item.id ? 'active' : '']"
        @click="scrollToMessage(item.id)"
      >
        <text class="chat-nav-title">{{ item.title }}</text>
        <text class="chat-nav-subtitle">{{ item.subtitle }}</text>
      </button>
    </view>

    <view v-if="chatNavItems.length > 1" class="chat-nav-rail">
      <button
        v-for="item in chatNavItems"
        :key="item.id"
        :class="['chat-nav-mark', activeNavId === item.id ? 'active' : '']"
        @click="scrollToMessage(item.id)"
      />
    </view>

    <view class="composer">
      <button class="tool-button" @click="showSoon">
        <image class="tool-icon" src="/static/icons/icon-add.png" mode="aspectFit" />
      </button>
      <input v-model="draft" class="composer-input" placeholder="问点什么" confirm-type="send" @confirm="sendMessage" />
      <button class="send-button" @click="sendMessage">
        <image class="send-icon" src="/static/icons/icon-send.png" mode="aspectFit" />
        <text class="send-text">发送</text>
      </button>
    </view>
  </view>
</template>

<script>
import { askQuestion, askQuestionStream, getAskBootstrap, getAuthToken } from '@/utils/api.js'
import { markdownToHtml } from '@/utils/markdown.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import { addAskRecord, getAskSession, saveAskSession } from '@/utils/user-data.js'

let messageId = 3

export default {
  data() {
    return {
      draft: '',
      darkMode: false,
      fontSize: 'standard',
      showSources: true,
      hasAsked: false,
      prompts: [],
      followups: [],
      messages: [],
      linkedArticle: null,
      thinkingTimer: null,
      thinkingStartedAt: 0,
      thinkingMessageId: null,
      streamRenderTimer: null,
      streamRenderMessageId: null,
      streamRenderText: '',
      bottomScrollTimer: null,
      activeNavId: null
    }
  },
  computed: {
    chatNavItems() {
      return this.messages
        .filter(message => message.role === 'user')
        .map(message => {
          const assistant = this.messages.find(item => item.role === 'assistant' && item.id > message.id)
          return {
            id: message.id,
            title: this.navText(message.text, 20),
            subtitle: assistant && assistant.text ? this.navText(assistant.text, 24) : '等待回答'
          }
        })
    }
  },
  onHide() {
    saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
    this.stopThinkingTimer()
    this.clearStreamRenderTimer()
    this.clearBottomScrollTimer()
  },
  onUnload() {
    saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
    this.stopThinkingTimer()
    this.clearStreamRenderTimer()
    this.clearBottomScrollTimer()
  },
  onShow() {
    if (!this.messages.length) {
      const session = getAskSession()
      this.messages = Array.isArray(session.messages) ? session.messages : []
      this.linkedArticle = session.linkedArticle || null
      this.hasAsked = this.messages.some(message => message.role === 'user')
      const lastUser = [...this.messages].reverse().find(message => message.role === 'user')
      if (lastUser) this.activeNavId = lastUser.id
    }
    this.loadSettings()
    this.loadContent()
    this.consumePendingAskContext()
    this.ensureLoggedIn()
    applyTabBarTheme(this.darkMode)
  },
  methods: {
    ensureLoggedIn() {
      if (getAuthToken()) return true
      uni.showToast({ title: '请先登录后使用 AI 问问', icon: 'none' })
      setTimeout(() => {
        uni.navigateTo({ url: '/pages/auth/login' })
      }, 400)
      return false
    },
    loadSettings() {
      const showSources = uni.getStorageSync('jianwen_show_sources')
      this.darkMode = !!uni.getStorageSync('jianwen_dark_mode')
      this.fontSize = uni.getStorageSync('jianwen_font_size') || 'standard'
      this.showSources = showSources === '' ? true : showSources !== false
    },
    async loadContent() {
      try {
        const data = await getAskBootstrap()
        this.prompts = data.prompts || []
        this.followups = data.followups || []
      } catch (error) {
        uni.showToast({ title: error.message || '问问内容加载失败', icon: 'none' })
      }
    },
    askPrompt(prompt) {
      this.draft = prompt
      this.sendMessage()
    },
    renderMarkdown(text) {
      return markdownToHtml(text)
    },
    navText(text, maxLength) {
      const normalized = String(text || '')
        .replace(/```[\s\S]*?```/g, '代码片段')
        .replace(/[#>*_`~\-[\]()]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
      if (!normalized) return '新的问题'
      return normalized.length > maxLength ? `${normalized.slice(0, maxLength)}...` : normalized
    },
    promptNumber(index) {
      const value = index + 1
      return value < 10 ? `0${value}` : String(value)
    },
    consumePendingAskContext() {
      const pending = uni.getStorageSync('jianwen_pending_ask_context')
      if (!pending || (!pending.articleId && !pending.issueKey && !pending.policyKey && !pending.fromRecord)) return

      uni.removeStorageSync('jianwen_pending_ask_context')
      this.linkedArticle = (pending.articleId || pending.issueKey || pending.policyKey)
        ? {
            articleId: pending.articleId,
            issueKey: pending.issueKey || '',
            policyKey: pending.policyKey || '',
            title: pending.title || '',
            topic: pending.topic || '',
            sources: pending.sources || ''
          }
        : null
      this.messages.push({
        id: messageId++,
        role: 'context',
        text: pending.articleId
          ? `来自文章页：正在围绕《${this.linkedArticle.title || '当前文章'}》继续问问${this.linkedArticle.topic ? ` · ${this.linkedArticle.topic}` : ''}`
          : pending.issueKey || pending.policyKey ? `正在围绕「${pending.title}」问问，仅带入公开内容。` : `来自问问记录：正在围绕「${pending.title || '历史问题'}」继续追问`,
        sources: pending.sources || ''
      })
      saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
      this.scrollToBottom({ duration: 0 })
      if (pending.question) {
        this.draft = pending.question
        this.$nextTick(() => this.sendMessage())
      }
    },
    async sendMessage() {
      if (!this.ensureLoggedIn()) return
      const text = this.draft.trim()
      if (!text) {
        uni.showToast({ title: '先输入一个问题', icon: 'none' })
        return
      }
      this.stopThinkingTimer()
      this.clearStreamRenderTimer()
      this.clearBottomScrollTimer()
      this.thinkingStartedAt = Date.now()
      const pendingId = messageId++
      const userId = messageId++
      this.messages.push({ id: userId, role: 'user', text })
      this.activeNavId = userId
      this.draft = ''
      this.messages.push({
        id: pendingId,
        role: 'assistant',
        text: '正在思考…',
        sources: '',
        thinkingLabel: '已思考 0 秒'
      })
      saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
      this.scrollToBottom({ duration: 120 })
      this.thinkingMessageId = pendingId
      this.startThinkingTimer()
      try {
        let answer = ''
        let responseSources = ''
        const articleId = this.linkedArticle && this.linkedArticle.articleId
        try {
          let streamedText = ''
          await askQuestionStream(text, { articleId, issueKey: this.linkedArticle?.issueKey, policyKey: this.linkedArticle?.policyKey }, chunk => {
            streamedText += chunk
            this.queueAssistantText(pendingId, streamedText)
            this.scheduleBottomScroll()
          })
          this.flushAssistantText()
          answer = streamedText
        } catch (streamError) {
          this.flushAssistantText()
          const result = await askQuestion(text, { articleId, issueKey: this.linkedArticle?.issueKey, policyKey: this.linkedArticle?.policyKey })
          answer = result.answer || ''
          responseSources = result.sources || ''
          await this.typeAssistantMessage(pendingId, answer)
        }
        const displaySources = responseSources || (this.linkedArticle && this.linkedArticle.sources) || ''
        const thinkingSeconds = Math.max(1, Math.round((Date.now() - this.thinkingStartedAt) / 1000))
        this.replaceAssistantMessage(pendingId, {
          text: answer,
          sources: displaySources,
          thinkingLabel: `已思考 ${thinkingSeconds} 秒`
        })
        this.clearBottomScrollTimer()
        this.scrollToBottom({ duration: 160 })
        addAskRecord(text, answer, displaySources)
      } catch (error) {
        this.replaceAssistantMessage(pendingId, {
          text: error.message || '回答生成失败',
          sources: '',
          thinkingLabel: `已思考 ${Math.max(1, Math.round((Date.now() - this.thinkingStartedAt) / 1000))} 秒`
        })
        this.clearBottomScrollTimer()
        this.scrollToBottom({ duration: 160 })
      }
      this.stopThinkingTimer()
      this.hasAsked = true
      this.scrollToBottom({ duration: 120 })
    },
    startThinkingTimer() {
      this.thinkingTimer = setInterval(() => {
        const message = this.messages.find(item => item.id === this.thinkingMessageId)
        if (!message) return
        const seconds = Math.max(0, Math.floor((Date.now() - this.thinkingStartedAt) / 1000))
        message.thinkingLabel = `已思考 ${seconds} 秒`
      }, 1000)
    },
    stopThinkingTimer() {
      if (this.thinkingTimer) {
        clearInterval(this.thinkingTimer)
        this.thinkingTimer = null
      }
      this.thinkingStartedAt = 0
      this.thinkingMessageId = null
    },
    replaceAssistantMessage(id, patch) {
      const index = this.messages.findIndex(item => item.id === id)
      if (index === -1) return
      this.messages.splice(index, 1, {
        ...this.messages[index],
        ...patch
      })
      saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
    },
    queueAssistantText(id, text) {
      this.streamRenderMessageId = id
      this.streamRenderText = text
      if (this.streamRenderTimer) return
      this.streamRenderTimer = setTimeout(() => {
        this.flushAssistantText()
      }, 80)
    },
    flushAssistantText() {
      if (this.streamRenderTimer) {
        clearTimeout(this.streamRenderTimer)
        this.streamRenderTimer = null
      }
      if (!this.streamRenderMessageId) return
      this.replaceAssistantMessage(this.streamRenderMessageId, { text: this.streamRenderText })
      this.streamRenderMessageId = null
      this.streamRenderText = ''
    },
    clearStreamRenderTimer() {
      if (this.streamRenderTimer) {
        clearTimeout(this.streamRenderTimer)
        this.streamRenderTimer = null
      }
      this.streamRenderMessageId = null
      this.streamRenderText = ''
    },
    typeAssistantMessage(id, text) {
      return new Promise(resolve => {
        const chars = Array.from(text || '')
        let index = 0
        const step = () => {
          index += 8
          this.replaceAssistantMessage(id, { text: chars.slice(0, index).join('') })
          this.scheduleBottomScroll()
          if (index >= chars.length) {
            this.scrollToBottom({ duration: 120 })
            resolve()
            return
          }
          setTimeout(step, 36)
        }
        step()
      })
    },
    scheduleBottomScroll() {
      if (this.bottomScrollTimer) return
      this.bottomScrollTimer = setTimeout(() => {
        this.bottomScrollTimer = null
        this.scrollToBottom({ duration: 0 })
      }, 260)
    },
    clearBottomScrollTimer() {
      if (this.bottomScrollTimer) {
        clearTimeout(this.bottomScrollTimer)
        this.bottomScrollTimer = null
      }
    },
    scrollToBottom(options = {}) {
      const duration = typeof options.duration === 'number' ? options.duration : 0
      this.$nextTick(() => {
        uni.pageScrollTo({ scrollTop: 999999, duration })
      })
    },
    scrollToMessage(id) {
      this.activeNavId = id
      this.$nextTick(() => {
        uni.pageScrollTo({
          selector: `#message-${id}`,
          duration: 220,
          fail: () => uni.pageScrollTo({ scrollTop: 0, duration: 220 })
        })
      })
    },
    showSoon() {
      uni.showToast({ title: '链接和语音功能预留中', icon: 'none' })
    }
  }
}
</script>

<style scoped>
.ask-page {
  min-height: 100vh;
  padding-bottom: calc(248rpx + env(safe-area-inset-bottom));
  background:
    radial-gradient(circle at 16% 0%, rgba(214, 184, 112, 0.28) 0, rgba(214, 184, 112, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(31, 95, 122, 0.18) 0, rgba(31, 95, 122, 0) 330rpx),
    linear-gradient(180deg, #F8F5EC 0%, #EDF5F7 460rpx, #F5F7F4 100%);
}

.ask-scroll {
  padding: calc(96rpx + env(safe-area-inset-top)) 48rpx 72rpx;
}

.topbar > view {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.section-title {
  display: block;
  margin: 64rpx 0 34rpx;
  color: #14212B;
  font-size: 34rpx;
  font-weight: 900;
}

.ask-hero {
  display: flex;
  align-items: center;
  gap: 28rpx;
  padding: 38rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(31,95,122,0.94), rgba(18,55,75,0.9)),
    linear-gradient(135deg, rgba(212,170,78,0.2), transparent);
}

.ask-orb {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 120rpx;
  height: 120rpx;
  border: 1rpx solid rgba(255,255,255,0.36);
  border-radius: 34rpx;
  background: rgba(255,255,255,0.16);
}

.ask-orb-icon {
  width: 66rpx;
  height: 66rpx;
}

.ask-hero-copy {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 12rpx;
}

.hero-kicker {
  color: #D4AA4E;
  font-size: 20rpx;
  font-weight: 900;
}

.hero-title {
  color: #FFFFFF;
  font-size: 36rpx;
  line-height: 1.26;
  font-weight: 900;
}

.hero-copy {
  color: rgba(255,255,255,0.82);
  font-size: 24rpx;
  line-height: 1.55;
}

.prompt-scroll {
  width: 100%;
  white-space: nowrap;
}

.prompt-row {
  display: inline-flex;
  gap: 34rpx;
  padding-bottom: 22rpx;
}

.prompt-card {
  width: 344rpx;
  min-height: 154rpx;
  padding: 36rpx;
  border: 1rpx solid rgba(255,255,255,0.88);
  border-radius: 28rpx;
  background: rgba(255,255,255,0.82);
  color: #143E52;
  font-size: 27rpx;
  line-height: 1.45;
  text-align: left;
  white-space: normal;
  font-weight: 900;
  box-shadow: 0 18rpx 42rpx rgba(31, 47, 58, 0.09);
}

.followup-card,
.chat-card {
  margin-top: 40rpx;
  padding: 38rpx;
  border-radius: 28rpx;
}

.followup-card {
  padding: 28rpx 0 26rpx 28rpx;
  overflow: hidden;
}

.followup-title {
  display: block;
  margin: 0 28rpx 18rpx 0;
  color: #14212B;
  font-size: 25rpx;
  font-weight: 900;
}

.followup-scroll {
  width: 100%;
  white-space: nowrap;
}

.followup-row {
  display: inline-flex;
  gap: 14rpx;
  padding-right: 28rpx;
}

.followup-chip {
  flex: 0 0 auto;
  min-height: 58rpx;
  max-width: 280rpx;
  margin: 0;
  padding: 0 22rpx;
  border: 1rpx solid #CFE0E7;
  border-radius: 999rpx;
  background: #F2F7F9;
  color: #1F5F7A;
  font-size: 24rpx;
  font-weight: 800;
  line-height: 58rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.followup-chip::after {
  border: 0;
}

.message {
  max-width: 88%;
  margin-bottom: 42rpx;
}

.message.user {
  margin-left: auto;
  text-align: right;
}

.message.context {
  max-width: 100%;
  margin-right: 0;
  text-align: left;
}

.message-label {
  display: block;
  margin-bottom: 16rpx;
  color: #8A949E;
  font-size: 22rpx;
}

.message-text {
  display: inline-block;
  padding: 34rpx 36rpx;
  border-radius: 24rpx;
  background: rgba(247,250,252,0.88);
  color: #14212B;
  font-size: 30rpx;
  line-height: 1.65;
  text-align: left;
}

.message.assistant .message-text {
  display: block;
  width: 100%;
  box-sizing: border-box;
}

.message-thinking {
  display: block;
  margin-top: 12rpx;
  color: #8A949E;
  font-size: 22rpx;
  line-height: 1.4;
}

.message.user .message-text {
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
}

.message.context .message-label {
  display: none;
}

.message.context .message-text {
  display: block;
  border: 1rpx solid #DCE5EA;
  background: #E6F0F4;
  color: #1F5F7A;
  font-size: 25rpx;
  font-weight: 800;
}

.message-source {
  margin-top: 22rpx;
  color: #8A949E;
  font-size: 23rpx;
  line-height: 1.45;
}

.composer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 124rpx;
  display: flex;
  align-items: center;
  gap: 18rpx;
  padding: 22rpx 32rpx calc(20rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid rgba(255,255,255,0.72);
  background: rgba(255,255,255,0.92);
  box-shadow: 0 -18rpx 50rpx rgba(20, 33, 43, 0.1);
}

.tool-button {
  flex: 0 0 78rpx;
  height: 78rpx;
  border-radius: 22rpx;
  background: rgba(31,95,122,0.1);
}

.tool-icon {
  width: 30rpx;
  height: 30rpx;
}

.composer-input {
  flex: 1;
  min-height: 78rpx;
  padding: 0 24rpx;
  border: 1rpx solid rgba(31,95,122,0.12);
  border-radius: 22rpx;
  background: rgba(247,250,252,0.92);
  color: #14212B;
  font-size: 26rpx;
}

.send-button {
  flex: 0 0 112rpx;
  min-height: 78rpx;
  border-radius: 999rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
  color: #FFFFFF;
  font-size: 25rpx;
  font-weight: 800;
  white-space: nowrap;
}

.dark-mode.ask-page {
  background:
    radial-gradient(circle at 16% 0%, rgba(187, 141, 45, 0.18) 0, rgba(187, 141, 45, 0) 280rpx),
    radial-gradient(circle at 88% 8%, rgba(75, 154, 187, 0.16) 0, rgba(75, 154, 187, 0) 330rpx),
    linear-gradient(180deg, #0E1720 0%, #101820 100%) !important;
}

.dark-mode .ask-hero {
  background:
    linear-gradient(135deg, rgba(31,95,122,0.86), rgba(16,39,55,0.94)),
    linear-gradient(135deg, rgba(212,170,78,0.14), transparent) !important;
}

.dark-mode .composer {
  border-top-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.94) !important;
}

.chat-nav-panel {
  position: fixed;
  top: 50%;
  right: 28rpx;
  z-index: 8;
  display: flex;
  flex-direction: column;
  gap: 10rpx;
  width: 260rpx;
  max-height: 360rpx;
  padding: 12rpx;
  border: 1rpx solid #E1E7EC;
  border-radius: 16rpx;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 12rpx 36rpx rgba(20, 33, 43, 0.12);
  transform: translateY(-50%);
}

.chat-nav-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8rpx;
  min-height: 74rpx;
  padding: 12rpx 14rpx;
  border-radius: 12rpx;
  background: transparent;
  color: #8A949E;
  text-align: left;
}

.chat-nav-item.active {
  background: #EDF5F7;
  color: #1F5F7A;
}

.chat-nav-title,
.chat-nav-subtitle {
  display: block;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.25;
}

.chat-nav-title {
  color: #14212B;
  font-size: 23rpx;
  font-weight: 800;
}

.chat-nav-subtitle {
  color: #8A949E;
  font-size: 21rpx;
}

.chat-nav-item.active .chat-nav-title,
.chat-nav-item.active .chat-nav-subtitle {
  color: #1F5F7A;
}

.chat-nav-rail {
  position: fixed;
  top: 50%;
  right: 8rpx;
  z-index: 9;
  display: none;
  flex-direction: column;
  align-items: flex-end;
  gap: 22rpx;
  padding: 14rpx 6rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.42);
  transform: translateY(-50%);
  opacity: 0.72;
}

.chat-nav-mark {
  width: 12rpx;
  height: 5rpx;
  min-height: 5rpx;
  line-height: 5rpx;
  margin: 0;
  padding: 0;
  border-radius: 999rpx;
  background: #BAC7CF;
}

.chat-nav-mark::after {
  border: 0;
}

.chat-nav-mark.active {
  width: 18rpx;
  background: #1F5F7A;
}

.ask-page {
  padding-bottom: calc(258rpx + env(safe-area-inset-bottom));
}

.ask-scroll {
  padding: calc(92rpx + env(safe-area-inset-top)) 40rpx 96rpx;
}

.ask-topbar {
  min-height: 138rpx;
  margin: -16rpx -10rpx 34rpx;
}

.ask-topbar .subtle {
  margin-top: 8rpx;
}

.top-status {
  position: relative;
  z-index: 1;
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 10rpx;
  min-height: 52rpx;
  padding: 0 18rpx;
  border: 1rpx solid rgba(212, 170, 78, 0.34);
  border-radius: 999rpx;
  background: rgba(255,255,255,0.66);
}

.ask-topbar > .top-status {
  flex-direction: row;
  gap: 10rpx;
}

.status-dot {
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
  box-shadow: 0 0 18rpx rgba(212, 170, 78, 0.7);
}

.status-text {
  color: #7C5C18;
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.ask-hero {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 26rpx;
  padding: 36rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 34rpx;
  overflow: hidden;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.88), rgba(255,255,255,0.48)),
    linear-gradient(135deg, rgba(245,235,207,0.9), rgba(226,240,244,0.78));
  box-shadow: 0 28rpx 80rpx rgba(48, 65, 72, 0.12);
}

.hero-grid,
.hero-accent-line {
  position: absolute;
  pointer-events: none;
}

.hero-grid {
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  opacity: 0.24;
  background-image:
    linear-gradient(rgba(31,95,122,0.08) 1rpx, transparent 1rpx),
    linear-gradient(90deg, rgba(31,95,122,0.08) 1rpx, transparent 1rpx);
  background-size: 62rpx 62rpx;
}

.hero-accent-line {
  top: 0;
  left: 0;
  width: 10rpx;
  height: 100%;
  background: linear-gradient(180deg, #D4AA4E, #1F5F7A);
}

.ask-orb {
  position: relative;
  z-index: 1;
  width: 112rpx;
  height: 112rpx;
  border-color: rgba(31,95,122,0.14);
  border-radius: 28rpx;
  background:
    linear-gradient(135deg, rgba(31,95,122,0.12), rgba(212,170,78,0.1)),
    rgba(255,255,255,0.72);
  box-shadow: 0 18rpx 42rpx rgba(31, 95, 122, 0.12);
}

.ask-orb-icon {
  width: 78rpx;
  height: 78rpx;
}

.ask-hero-copy {
  position: relative;
  z-index: 1;
  flex: 1 1 360rpx;
}

.hero-kicker {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  letter-spacing: 0;
}

.hero-title {
  color: #101D28;
  font-size: 38rpx;
  line-height: 1.22;
}

.hero-copy {
  color: #52616D;
  font-size: 24rpx;
  line-height: 1.42;
}

.hero-metrics {
  position: relative;
  z-index: 1;
  display: flex;
  gap: 14rpx;
  width: 100%;
}

.metric-chip {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 6rpx;
  padding: 18rpx 16rpx;
  border: 1rpx solid rgba(255,255,255,0.78);
  border-radius: 20rpx;
  background: rgba(255,255,255,0.64);
  box-shadow: 0 14rpx 34rpx rgba(20, 33, 43, 0.07);
}

.metric-chip.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.94), rgba(18,55,75,0.9));
}

.metric-value {
  color: #132A38;
  font-size: 27rpx;
  line-height: 1;
  font-weight: 900;
}

.metric-label {
  color: #6C7880;
  font-size: 20rpx;
  line-height: 1.25;
  font-weight: 800;
}

.metric-chip.primary .metric-value,
.metric-chip.primary .metric-label {
  color: #FFFFFF;
}

.section-head {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
  margin: 58rpx 0 28rpx;
}

.section-eyebrow,
.chat-eyebrow {
  color: #987221;
  font-size: 21rpx;
  line-height: 1.25;
  font-weight: 900;
  letter-spacing: 0;
}

.section-title {
  margin: 0;
  color: #14212B;
  font-size: 34rpx;
  line-height: 1.3;
}

.prompt-row {
  gap: 20rpx;
  padding-bottom: 22rpx;
}

.prompt-card {
  display: inline-flex;
  align-items: center;
  gap: 18rpx;
  width: 430rpx;
  min-height: 112rpx;
  padding: 22rpx 24rpx;
  border: 1rpx solid rgba(255,255,255,0.88);
  border-radius: 999rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.9), rgba(244,250,250,0.74)),
    linear-gradient(135deg, rgba(31,95,122,0.08), rgba(212,170,78,0.1));
  box-shadow: 0 18rpx 42rpx rgba(31, 47, 58, 0.09);
}

.prompt-card:active,
.followup-chip:active,
.tool-button:active,
.send-button:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.prompt-icon-wrap {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 64rpx;
  height: 64rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
}

.prompt-index {
  color: #1F5F7A;
  font-size: 21rpx;
  line-height: 1;
  font-weight: 900;
}

.prompt-text {
  flex: 1;
  min-width: 0;
  color: #143E52;
  font-size: 25rpx;
  line-height: 1.45;
  font-weight: 900;
  white-space: normal;
  text-align: left;
}

.chat-card {
  padding: 34rpx;
  margin-top: 42rpx;
}

.chat-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24rpx;
  padding-bottom: 30rpx;
  margin-bottom: 34rpx;
  border-bottom: 1rpx solid rgba(31,95,122,0.1);
}

.chat-title {
  display: block;
  margin-top: 8rpx;
  color: #14212B;
  font-size: 31rpx;
  line-height: 1.25;
  font-weight: 900;
}

.chat-state {
  flex: 0 0 auto;
  padding: 8rpx 16rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1.25;
  font-weight: 900;
}

.message {
  display: flex;
  width: 100%;
  max-width: 100%;
  flex-direction: column;
  gap: 12rpx;
  margin-bottom: 36rpx;
}

.message:last-child {
  margin-bottom: 0;
}

.message.user {
  align-items: flex-end;
}

.message.context {
  align-items: stretch;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 12rpx;
}

.message.user .message-meta {
  flex-direction: row-reverse;
}

.message.context .message-meta {
  display: none;
}

.message-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 46rpx;
  height: 46rpx;
  border-radius: 16rpx;
  background: rgba(31,95,122,0.1);
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1;
  font-weight: 900;
}

.message.user .message-avatar {
  background: #1F5F7A;
  color: #FFFFFF;
}

.message-avatar-icon {
  width: 28rpx;
  height: 28rpx;
}

.message-label {
  margin: 0;
  color: #7C8790;
  font-size: 22rpx;
}

.message-bubble {
  max-width: 92%;
  padding: 30rpx 32rpx;
  border: 1rpx solid rgba(31,95,122,0.1);
  border-radius: 26rpx;
  background: rgba(255,255,255,0.82);
  box-shadow: 0 18rpx 42rpx rgba(20, 33, 43, 0.07);
}

.message.assistant .message-bubble {
  width: 100%;
  max-width: 100%;
}

.message.user .message-bubble {
  border-color: rgba(31,95,122,0.08);
  border-bottom-right-radius: 10rpx;
  background: linear-gradient(135deg, #1F5F7A, #143E52);
}

.message.assistant .message-bubble {
  border-bottom-left-radius: 10rpx;
  background:
    linear-gradient(135deg, rgba(255,255,255,0.94), rgba(247,250,252,0.86)),
    rgba(255,255,255,0.86);
}

.message.context .message-bubble {
  max-width: 100%;
  border-color: rgba(212,170,78,0.2);
  border-radius: 20rpx;
  background: rgba(212,170,78,0.1);
  box-shadow: none;
}

.message-text {
  display: block;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: #14212B;
  font-size: 29rpx;
  line-height: 1.7;
}

.message.assistant .message-text {
  width: 100%;
}

.message.user .message-text {
  background: transparent;
  color: #FFFFFF;
}

.message.context .message-text {
  border: 0;
  background: transparent;
  color: #725516;
  font-size: 25rpx;
}

.thinking-bar {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-height: 52rpx;
  padding: 0 18rpx;
  margin-top: 22rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.08);
}

.thinking-pulse {
  width: 12rpx;
  height: 12rpx;
  border-radius: 999rpx;
  background: #D4AA4E;
  box-shadow: 0 0 18rpx rgba(212,170,78,0.62);
}

.message-thinking {
  margin: 0;
  color: #66737B;
  font-size: 22rpx;
}

.message-source {
  margin-top: 24rpx;
  padding-top: 22rpx;
  border-top: 1rpx solid rgba(31,95,122,0.1);
}

.source-head {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-bottom: 10rpx;
  color: #1F5F7A;
  font-size: 22rpx;
  line-height: 1.3;
  font-weight: 900;
}

.source-icon {
  width: 24rpx;
  height: 24rpx;
}

.source-text {
  display: block;
  color: #7C8790;
  font-size: 23rpx;
  line-height: 1.5;
}

.followup-card {
  position: sticky;
  bottom: calc(230rpx + env(safe-area-inset-bottom));
  z-index: 3;
  margin-top: 34rpx;
  padding: 22rpx 0 22rpx 24rpx;
  border: 1rpx solid rgba(255,255,255,0.82);
  border-radius: 28rpx;
  overflow: hidden;
  background: rgba(255,255,255,0.88);
  box-shadow: 0 18rpx 48rpx rgba(20, 33, 43, 0.11);
}

.followup-title {
  margin-bottom: 16rpx;
  color: #14212B;
}

.followup-chip {
  min-height: 60rpx;
  max-width: 330rpx;
  border-color: rgba(31,95,122,0.14);
  background: rgba(31,95,122,0.08);
  line-height: 60rpx;
}

.composer {
  left: 22rpx;
  right: 22rpx;
  bottom: calc(124rpx + env(safe-area-inset-bottom));
  gap: 16rpx;
  padding: 18rpx;
  border: 1rpx solid rgba(255,255,255,0.86);
  border-radius: 34rpx;
  background: rgba(255,255,255,0.92);
  box-shadow: 0 -14rpx 44rpx rgba(20, 33, 43, 0.12);
}

.tool-button,
.send-button {
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-button {
  flex-basis: 76rpx;
  height: 76rpx;
  border-radius: 24rpx;
}

.composer-input {
  min-height: 76rpx;
  border-color: rgba(31,95,122,0.12);
  border-radius: 24rpx;
  background: rgba(247,250,252,0.92);
}

.send-button {
  flex: 0 0 128rpx;
  flex-direction: row;
  flex-wrap: nowrap;
  gap: 8rpx;
  width: 128rpx;
  min-height: 76rpx;
  border-radius: 24rpx;
  white-space: nowrap;
}

.send-icon {
  flex: 0 0 30rpx;
  width: 30rpx;
  height: 30rpx;
}

.send-text {
  flex: 0 0 auto;
  color: #FFFFFF;
  font-size: 24rpx;
  line-height: 1;
  font-weight: 900;
  white-space: nowrap;
}

.font-large .hero-title {
  font-size: 46rpx;
}

.font-large .message-text {
  font-size: 32rpx;
}

.font-large .prompt-text {
  font-size: 27rpx;
}

.font-small .hero-title {
  font-size: 38rpx;
}

.font-small .message-text {
  font-size: 27rpx;
}

.font-small .prompt-text {
  font-size: 23rpx;
}

.dark-mode .ask-topbar,
.dark-mode .ask-hero {
  border-color: rgba(126,184,209,0.14) !important;
  background:
    linear-gradient(135deg, rgba(23,35,49,0.9), rgba(17,27,39,0.74)),
    linear-gradient(135deg, rgba(126,184,209,0.12), rgba(187,141,45,0.08)) !important;
}

.dark-mode .hero-grid {
  opacity: 0.16;
}

.dark-mode .ask-orb,
.dark-mode .metric-chip,
.dark-mode .top-status,
.dark-mode .prompt-card,
.dark-mode .message-bubble,
.dark-mode .followup-card,
.dark-mode .composer,
.dark-mode .composer-input {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

.dark-mode .metric-chip.primary,
.dark-mode .message.user .message-bubble,
.dark-mode .send-button {
  background: linear-gradient(135deg, rgba(31,95,122,0.9), rgba(16,39,55,0.94)) !important;
}

.dark-mode .page-title,
.dark-mode .hero-title,
.dark-mode .section-title,
.dark-mode .chat-title,
.dark-mode .followup-title,
.dark-mode .message-text,
.dark-mode .metric-value {
  color: #F4F7FA !important;
}

.dark-mode .hero-copy,
.dark-mode .message-label,
.dark-mode .message-thinking,
.dark-mode .source-text,
.dark-mode .metric-label {
  color: #B6C2CC !important;
}

.dark-mode .hero-kicker,
.dark-mode .section-eyebrow,
.dark-mode .chat-eyebrow,
.dark-mode .status-text {
  color: #D4AA4E !important;
}

.dark-mode .prompt-text,
.dark-mode .prompt-index,
.dark-mode .chat-state,
.dark-mode .source-head {
  color: #7EB8D1 !important;
}

.dark-mode .prompt-icon-wrap,
.dark-mode .thinking-bar,
.dark-mode .followup-chip,
.dark-mode .tool-button {
  background: rgba(126,184,209,0.12) !important;
}

.dark-mode .message.context .message-bubble {
  background: rgba(212,170,78,0.12) !important;
}

.dark-mode .message.context .message-text {
  color: #D4AA4E !important;
}

.dark-mode .chat-card-head,
.dark-mode .message-source {
  border-color: rgba(126,184,209,0.14) !important;
}

@media screen and (max-width: 900px) {
  .chat-nav-panel {
    display: none;
  }

  .chat-nav-rail {
    display: flex;
  }
}
</style>
