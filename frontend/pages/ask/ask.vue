<template>
  <view :class="['ask-page', darkMode ? 'dark-mode' : '', `font-${fontSize}`]">
    <view class="ask-scroll">
      <view class="topbar ask-topbar">
        <view>
          <text class="page-title">问问见闻</text>
          <text class="subtle">政策研究助理工作台 · {{ quotaLabel }}</text>
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
          <text class="chat-state">最近 {{ chatNavItems.length }} 轮</text>
        </view>
        <view v-if="hiddenRoundCount" class="chat-earlier" @click="openAskRecords">
          <text>更早的 {{ hiddenRoundCount }} 轮已收起，在“问问记录”中查看</text>
        </view>
        <template v-for="message in visibleMessages" :key="message.id">
          <AskMessage
            :message="message"
            :show-sources="showSources"
            :dark-mode="darkMode"
            :font-size="fontSize"
          />
          <!-- 引用的原文依据；放在气泡外，避免改变 AskMessage 的内部结构。 -->
          <view
            v-if="message.role === 'assistant' && showSources && citationItems(message).length"
            class="citation-card"
            :aria-label="`回答依据，共 ${citationItems(message).length} 篇原文`"
          >
            <view class="citation-head">
              <text class="citation-title">依据</text>
              <text class="citation-count">{{ citationItems(message).length }} 篇原文</text>
            </view>
            <button
              v-for="(item, index) in citationItems(message)"
              :key="`${message.id}-${item.article_id}`"
              class="citation-row"
              hover-class="citation-row-hover"
              @click="openCitation(item)"
            >
              <text class="citation-index">{{ citationNumber(index) }}</text>
              <view class="citation-main">
                <text class="citation-name">{{ item.title }}</text>
                <text v-if="item.quote" class="citation-quote">{{ item.quote }}</text>
              </view>
              <text class="citation-arrow" aria-hidden="true">→</text>
            </button>
          </view>
        </template>
      </view>

      <view v-if="hasAsked && followups.length" class="followup-card">
        <text class="followup-title">下一步可以问</text>
        <scroll-view class="followup-scroll" scroll-x>
          <view class="followup-row">
            <button v-for="item in followups" :key="item" class="followup-chip" @click="askPrompt(item)">
              <text class="followup-chip-text">{{ item }}</text>
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
        hover-class="none"
        :aria-label="'跳到：' + item.title"
        @click="scrollToMessage(item.id)"
      />
    </view>

    <AskComposer v-model="draft" :sending="sending" :dark-mode="darkMode" :quota-label="quotaLabel" @send="sendMessage" @tool="showSoon" />
  </view>
</template>

<script>
import { askQuestion, askQuestionStream, getAiQuota, getAskBootstrap, authRequest } from '@/utils/api.js'
import { markdownToHtml } from '@/utils/markdown.js'
import { applyTabBarTheme } from '@/utils/theme.js'
import { addAskRecord, getAskSession, saveAskSession } from '@/utils/user-data.js'
import AskComposer from '@/components/AskComposer.vue'
import AskMessage from '@/components/AskMessage.vue'

let messageId = 3
// 对话区只显示最近 7 轮问答。
const VISIBLE_ROUNDS = 7

// 流式接口逐字返回纯文本，无法在流里附带结构化来源；回答接收完后用最终
// 文本回查一次引用。失败就当没有引用，不影响回答本身。
async function requestCitations(question, articleId, answer) {
  const text = String(answer || '').trim()
  if (!text) return []
  try {
    const data = await authRequest({
      url: '/api/v1/content/ask/citations',
      method: 'POST',
      data: { question, article_id: articleId || '', answer: text }
    })
    return Array.isArray(data && data.citations) ? data.citations : []
  } catch (error) {
    return []
  }
}

// 新消息 id 必须大于已有消息（包括从本地恢复的会话），否则会和旧消息撞号：
// 回答写进旧气泡，新气泡永远停在“正在思考… 已思考 0 秒”。
function syncMessageId(messages) {
  const maxId = (messages || []).reduce((max, item) => Math.max(max, Number(item && item.id) || 0), 0)
  if (messageId <= maxId) messageId = maxId + 1
}

// 上次离开时还在生成的回答，恢复后不会再有数据进来，直接标记为已中断。
function settleStaleMessages(messages) {
  return (messages || []).map(item => {
    if (!item || item.role !== 'assistant') return item
    const pending = item.streaming || item.text === '正在思考…'
    if (!pending) {
      const elapsed = /^已思考 (\d+) 秒$/.exec(item.thinkingLabel || '')
      return elapsed && Number(elapsed[1]) > 86400 ? { ...item, thinkingLabel: '' } : item
    }
    const text = item.text && item.text !== '正在思考…' ? item.text : '上次回答在生成中被中断，可以重新提问。'
    return { ...item, text, streaming: false, liveBlock: '', thinkingLabel: '已中断' }
  })
}

// 旧会话可能有撞号 bug 留下的重复 id，恢复时按顺序重编号。
function renumberIfDuplicated(messages) {
  const ids = messages.map(item => item && item.id)
  if (new Set(ids).size === ids.length) return messages
  return messages.map((item, index) => ({ ...item, id: index + 1 }))
}

// 半流式节奏与网页 webpage/js/ask.js 保持一致：
// 每 16ms 至少显示 2 个字，落后时按积压量提速，始终匀速追平。
// 网络分块再大，画面也按固定节奏推进，不会整段跳出。
const REVEAL_TICK_MS = 16
const REVEAL_CHARS_PER_TICK = 2
// 积压按约 90 帧（约 1.5 秒）均匀消化；模型出字比显示快时也不会越积越多。
const REVEAL_BACKLOG_TICKS = 90
// 已完成块（以空行分隔）的 HTML 缓存，避免整篇 markdown 反复重解析。
function splitBlocks(text) {
  return String(text || '').split(/\n{2,}/)
}

// 小程序端可能没有 AbortController；没有就退化为无法中断（不影响功能）。
function createAbortController() {
  if (typeof AbortController === 'function') return new AbortController()
  return null
}

export default {
  components: { AskComposer, AskMessage },
  data() {
    return {
      draft: '',
      sending: false,
      darkMode: false,
      fontSize: 'standard',
      showSources: true,
      hasAsked: false,
      prompts: [],
      followups: [],
      quotaRemaining: null,
      quotaLimit: 20,
      messages: [],
      linkedArticle: null,
      thinkingTimer: null,
      thinkingStartedAt: 0,
      thinkingMessageId: null,
      streamRenderTimer: null,
      streamRenderMessageId: null,
      streamRenderText: '',
      revealMessageId: null,
      revealTarget: '',
      revealShown: 0,
      revealEnded: false,
      revealWaiters: [],
      streamAbort: null,
      typeTimer: null,
      typeResolve: null,
      bottomScrollTimer: null,
      activeNavId: null,
      navLockUntil: 0,
      navScrollTimer: null
    }
  },
  computed: {
    quotaLabel() {
      const remaining = this.quotaRemaining === null ? 0 : Math.max(0, this.quotaRemaining)
      return remaining === 0 ? `今日额度已耗尽 0/${this.quotaLimit}` : `今日剩余次数 ${remaining}/${this.quotaLimit}`
    },
    // 界面只保留最近 7 轮（一问一答为一轮），更早的仍保存在本地和“问问记录”里。
    visibleStartIndex() {
      const userIndexes = []
      this.messages.forEach((message, index) => {
        if (message.role === 'user') userIndexes.push(index)
      })
      if (userIndexes.length <= VISIBLE_ROUNDS) return 0
      return userIndexes[userIndexes.length - VISIBLE_ROUNDS]
    },
    visibleMessages() {
      return this.messages.slice(this.visibleStartIndex)
    },
    hiddenRoundCount() {
      return this.messages.slice(0, this.visibleStartIndex).filter(message => message.role === 'user').length
    },
    chatNavItems() {
      const list = this.visibleMessages
      return list
        .map((message, index) => ({ message, index }))
        .filter(({ message }) => message.role === 'user')
        .map(({ message, index }) => {
          // 按位置找紧跟在这条提问后面的回答（回答的 id 比提问小，不能按 id 比较）。
          const assistant = list.slice(index + 1).find(item => item.role === 'assistant')
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
    this.clearTypeTimer()
    this.clearBottomScrollTimer()
  },
  onUnload() {
    saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
    this.stopThinkingTimer()
    this.clearStreamRenderTimer()
    this.clearTypeTimer()
    this.clearBottomScrollTimer()
    this.abortStream()
    clearTimeout(this.navScrollTimer)
    this.navScrollTimer = null
  },
  onPageScroll() {
    if (this.navScrollTimer) return
    this.navScrollTimer = setTimeout(() => {
      this.navScrollTimer = null
      this.updateActiveNav()
    }, 120)
  },
  onShow() {
    if (!this.messages.length) {
      const session = getAskSession()
      this.messages = renumberIfDuplicated(settleStaleMessages(Array.isArray(session.messages) ? session.messages : []))
      this.linkedArticle = session.linkedArticle || null
      this.hasAsked = this.messages.some(message => message.role === 'user')
      const lastUser = [...this.messages].reverse().find(message => message.role === 'user')
      if (lastUser) this.activeNavId = lastUser.id
    }
    syncMessageId(this.messages)
    this.backfillCitations()
    this.loadSettings()
    this.loadQuota()
    // 进入问问默认停在最底部；提示词卡片和图片加载会把内容撑高，加载完再对齐一次。
    this.scrollToBottom({ duration: 0 })
    this.loadContent().then(() => this.scrollToBottom({ duration: 0 }))
    setTimeout(() => this.scrollToBottom({ duration: 0 }), 300)
    this.consumePendingAskContext()
    this.ensureLoggedIn()
    applyTabBarTheme(this.darkMode)
  },
  methods: {
    async loadQuota() {
      try {
        const quota = await getAiQuota()
        this.quotaLimit = Number(quota.limit) || 20
        this.quotaRemaining = Number(quota.remaining)
      } catch (error) {
        this.quotaRemaining = 0
      }
    },
    ensureLoggedIn() {
      if (uni.getStorageSync('jianwen_auth_token')) return true
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
      if (!pending || (!pending.articleId && !pending.fromRecord)) return

      uni.removeStorageSync('jianwen_pending_ask_context')
      this.linkedArticle = pending.articleId
        ? {
            articleId: pending.articleId,
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
          : `来自问问记录：正在围绕「${pending.title || '历史问题'}」继续追问`,
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
      this.clearTypeTimer()
      this.clearBottomScrollTimer()
      this.thinkingStartedAt = Date.now()
      const requestStartedAt = this.thinkingStartedAt
      syncMessageId(this.messages)
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
        citations: [],
        thinkingLabel: '已思考 0 秒'
      })
      saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
      this.scrollToBottom({ duration: 120 })
      this.thinkingMessageId = pendingId
      this.startThinkingTimer()
      this.sending = true
      try {
        let answer = ''
        let responseSources = ''
        let citations = []
        let citationPromise = null
        const articleId = this.linkedArticle && this.linkedArticle.articleId
        try {
          let streamedText = ''
          const controller = createAbortController()
          this.streamAbort = controller ? controller.abort.bind(controller) : null
          await askQuestionStream(text, { articleId, signal: controller && controller.signal }, chunk => {
            streamedText += chunk
            this.queueAssistantText(pendingId, streamedText)
            this.scheduleBottomScroll()
          })
          // 流式接口只有纯文本：接收完后再按同一份文章上下文回查引用，
          // 不阻塞定稿，引用回来就补到这条消息上。
          citationPromise = requestCitations(text, articleId, streamedText)
          // 接收完毕后先把剩余内容按节奏追平，再定稿成完整 markdown。
          await this.finishReveal()
          this.clearStreamRenderTimer()
          answer = streamedText
        } catch (streamError) {
          this.flushAssistantText()
          this.clearStreamRenderTimer()
          // 用户离开页面主动 abort 时不再回退到普通请求。
          if (streamError && streamError.name === 'AbortError') throw streamError
          const result = await askQuestion(text, { articleId })
          answer = result.answer || ''
          responseSources = result.sources || ''
          citations = Array.isArray(result.citations) ? result.citations : []
          // 非流式兜底也走同一套半流式节奏：一次拿到全文，按“接收结束”的追平速度显示。
          this.queueAssistantText(pendingId, answer)
          await this.finishReveal()
          this.clearStreamRenderTimer()
        } finally {
          this.streamAbort = null
        }
        const displaySources = responseSources || (this.linkedArticle && this.linkedArticle.sources) || ''
        const thinkingSeconds = Math.max(1, Math.round((Date.now() - requestStartedAt) / 1000))
        this.replaceAssistantMessage(pendingId, {
          text: answer,
          sources: displaySources,
          citations,
          thinkingLabel: `已思考 ${thinkingSeconds} 秒`,
          streaming: false,
          renderBlocks: '',
          liveBlock: ''
        })
        if (citationPromise) {
          citationPromise.then(list => {
            if (Array.isArray(list) && list.length) {
              this.replaceAssistantMessage(pendingId, { citations: list })
            }
          })
        }
        this.clearBottomScrollTimer()
        this.scrollToBottom({ duration: 160 })
        addAskRecord(text, answer, displaySources)
      } catch (error) {
        if (error && error.name === 'AbortError') {
          // 离开页面中断：把已收到的内容定稿，避免留下 streaming 状态的半截消息。
          this.stopThinkingTimer()
          this.sending = false
          const index = this.messages.findIndex(item => item.id === pendingId)
          if (index !== -1) {
            const partial = this.messages[index]
            this.messages.splice(index, 1, {
              ...partial,
              text: partial.text === '正在思考…' ? '已停止生成，可以重新提问。' : partial.text,
              citations: [],
              thinkingLabel: '',
              streaming: false,
              renderBlocks: '',
              liveBlock: ''
            })
          }
          saveAskSession({ messages: this.messages, linkedArticle: this.linkedArticle })
          this.loadQuota()
          return
        }
        this.replaceAssistantMessage(pendingId, {
          text: error.message || '回答生成失败',
          sources: '',
          citations: [],
          thinkingLabel: `已思考 ${Math.max(1, Math.round((Date.now() - requestStartedAt) / 1000))} 秒`,
          streaming: false,
          renderBlocks: '',
          liveBlock: ''
        })
        this.clearBottomScrollTimer()
        this.scrollToBottom({ duration: 160 })
      }
      this.stopThinkingTimer()
      this.sending = false
      this.hasAsked = true
      this.loadQuota()
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
      // 停止计时后清掉占位消息的关联，避免定时器空转；文本由各路径负责替换。
      this.thinkingMessageId = null
      this.thinkingStartedAt = 0
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
    // 收到新分块：只更新目标文本，由 revealStep 按固定节奏推进显示。
    queueAssistantText(id, text) {
      // 新的一条回答才从头显示；切后台暂停后回来，接着已显示的位置继续。
      if (this.revealMessageId !== id) {
        this.revealMessageId = id
        this.revealShown = 0
        this.revealEnded = false
      }
      this.streamRenderMessageId = id
      this.revealTarget = text
      this.startReveal()
    },
    startReveal() {
      if (this.streamRenderTimer) return
      this.streamRenderTimer = setTimeout(() => this.revealStep(), REVEAL_TICK_MS)
    },
    revealStep() {
      this.streamRenderTimer = null
      const chars = Array.from(this.revealTarget || '')
      const rest = chars.length - this.revealShown
      if (rest <= 0) {
        this.resolveRevealWaiters()
        return
      }
      // 与网页一致：按积压自适应，接收中和结束后用同一速度，结尾不再整块倒出。
      const size = Math.max(REVEAL_CHARS_PER_TICK, Math.ceil(rest / REVEAL_BACKLOG_TICKS))
      this.revealShown = Math.min(chars.length, this.revealShown + size)
      this.streamRenderText = chars.slice(0, this.revealShown).join('')
      this.renderAssistantText()
      if (this.revealShown < chars.length) this.startReveal()
      else this.resolveRevealWaiters()
    },
    // 接收结束：剩余内容按同一节奏追平，追平后再定稿。
    finishReveal() {
      this.revealEnded = true
      if (!this.streamRenderMessageId || this.revealShown >= Array.from(this.revealTarget || '').length) {
        return Promise.resolve()
      }
      this.startReveal()
      return new Promise(resolve => this.revealWaiters.push(resolve))
    },
    resolveRevealWaiters() {
      this.revealWaiters.splice(0).forEach(resolve => resolve())
    },
    // 立即把已显示部分落到消息上（中断、出错时使用）。
    flushAssistantText() {
      if (this.streamRenderTimer) {
        clearTimeout(this.streamRenderTimer)
        this.streamRenderTimer = null
      }
      this.renderAssistantText()
      this.resolveRevealWaiters()
    },
    renderAssistantText() {
      const id = this.streamRenderMessageId
      if (!id) return
      const text = this.streamRenderText
      const index = this.messages.findIndex(item => item.id === id)
      if (index === -1) {
        this.streamRenderMessageId = null
        this.streamRenderText = ''
        return
      }
      // 按空行分块，已完成块只解析一次并缓存 HTML，只重解析最后一块。
      const blocks = splitBlocks(text)
      const doneBlocks = blocks.slice(0, -1)
      const tail = blocks.length > 1 ? blocks[blocks.length - 1] : blocks[0] || ''
      const previous = this.messages[index]
      const cachedBlocks = Array.isArray(previous.blockCache) ? previous.blockCache : []
      const cachedHtml = Array.isArray(previous.blockHtml) ? previous.blockHtml : []
      const rendered = doneBlocks.map((block, blockIndex) => (
        cachedBlocks[blockIndex] === block && cachedHtml[blockIndex]
          ? cachedHtml[blockIndex]
          : markdownToHtml(block)
      ))
      this.messages.splice(index, 1, {
        ...previous,
        text,
        streaming: true,
        renderBlocks: rendered.filter(Boolean).join(''),
        blockCache: doneBlocks,
        blockHtml: rendered,
        liveBlock: tail
      })
    },
    clearStreamRenderTimer() {
      if (this.streamRenderTimer) {
        clearTimeout(this.streamRenderTimer)
        this.streamRenderTimer = null
      }
      this.streamRenderMessageId = null
      this.streamRenderText = ''
      this.resolveRevealWaiters()
    },
    clearTypeTimer() {
      if (this.typeTimer) {
        clearTimeout(this.typeTimer)
        this.typeTimer = null
      }
      const resolve = this.typeResolve
      this.typeResolve = null
      if (resolve) resolve()
    },
    typeAssistantMessage(id, text) {
      return new Promise(resolve => {
        this.clearTypeTimer()
        const chars = Array.from(text || '')
        let index = 0
        const step = () => {
          this.typeTimer = null
          index += 8
          this.replaceAssistantMessage(id, { text: chars.slice(0, index).join('') })
          this.scheduleBottomScroll()
          if (index >= chars.length) {
            this.scrollToBottom({ duration: 120 })
            this.typeResolve = null
            resolve()
            return
          }
          this.typeTimer = setTimeout(step, 36)
        }
        this.typeResolve = resolve
        step()
      })
    },
    abortStream() {
      // 用户离开页面时中断流式请求；fetch 的 AbortController 只在 H5/App 可用。
      if (this.streamAbort) {
        try { this.streamAbort() } catch (error) {}
        this.streamAbort = null
      }
      this.clearStreamRenderTimer()
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
    // 滚动时把高亮跟到视口上方 1/3 处所在的那一轮。
    updateActiveNav() {
      if (Date.now() < this.navLockUntil) return
      const ids = this.chatNavItems.map(item => item.id)
      if (ids.length < 2) return
      const query = uni.createSelectorQuery().in(this)
      ids.forEach(id => query.select(`#message-${id}`).boundingClientRect())
      query.exec(rects => {
        this.pickActiveNav(ids, rects || [])
      })
    },
    pickActiveNav(ids, rects) {
      const line = (uni.getSystemInfoSync().windowHeight || 800) / 3
      let current = ids[0]
      rects.forEach((rect, index) => {
        if (rect && rect.top <= line) current = ids[index]
      })
      if (current !== this.activeNavId) this.activeNavId = current
    },
    scrollToMessage(id) {
      this.activeNavId = id
      this.navLockUntil = Date.now() + 600
      this.$nextTick(() => {
        uni.pageScrollTo({
          selector: `#message-${id}`,
          duration: 220,
          fail: () => uni.pageScrollTo({ scrollTop: 0, duration: 220 })
        })
      })
    },
    // 只渲染带文章 id 和标题的合法引用，坏数据直接跳过。
    citationItems(message) {
      const list = message && Array.isArray(message.citations) ? message.citations : []
      return list.filter(item => item && item.article_id && item.title)
    },
    citationNumber(index) {
      const value = index + 1
      return value < 10 ? `0${value}` : String(value)
    },
    // 从文章页返回后，若上一条回答的引用还没拿到（或上次没保存），补拉一次。
    backfillCitations() {
      if (!this.citationTried) this.citationTried = new Set()
      const assistant = [...this.messages].reverse().find(item => item
        && item.role === 'assistant'
        && item.text
        && item.text !== '正在思考…'
        && !item.streaming
        && (!Array.isArray(item.citations) || !item.citations.length))
      if (!assistant || this.citationTried.has(assistant.id)) return
      const user = [...this.messages].reverse().find(item => item && item.role === 'user' && item.id < assistant.id)
      if (!user || !user.text) return
      this.citationTried.add(assistant.id)
      const articleId = this.linkedArticle && this.linkedArticle.articleId
      requestCitations(user.text, articleId, assistant.text)
        .then(list => { if (Array.isArray(list) && list.length) this.replaceAssistantMessage(assistant.id, { citations: list }) })
        .catch(() => {})
    },
    openCitation(citation) {
      const articleId = citation && citation.article_id
      if (!articleId) return
      uni.navigateTo({ url: `/pages/article/detail?id=${encodeURIComponent(articleId)}&from=ask` })
    },
    openAskRecords() {
      uni.navigateTo({ url: '/pages/profile/ask-records' })
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
  display: flex;
  align-items: center;
  position: relative;
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
  white-space: nowrap;
}

/* Ellipsis moves to the inner text so the chip itself can grow its tap pad. */
.followup-chip-text {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 58rpx pill keeps its look; the transparent pad lifts the tap target to 90rpx. */
.followup-chip::before {
  content: '';
  position: absolute;
  top: -16rpx;
  right: 0;
  bottom: -16rpx;
  left: 0;
}

.followup-chip::after {
  border: 0;
}

/* 消息气泡已拆到 components/AskMessage.vue，输入区拆到 components/AskComposer.vue。 */
.chat-nav-item {
  position: relative;
}

/* 74rpx 的导航项，透明命中区补到 106rpx。 */
.chat-nav-item::before {
  content: '';
  position: absolute;
  top: -16rpx;
  right: -16rpx;
  bottom: -16rpx;
  left: -16rpx;
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
  gap: 0;
  padding: 6rpx 4rpx;
  border-radius: 999rpx;
  background: rgba(255, 255, 255, 0.42);
  transform: translateY(-50%);
  opacity: 0.72;
}

.chat-nav-mark {
  position: relative;
  width: 44rpx;
  height: 44rpx;
  min-height: 44rpx;
  line-height: 44rpx;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

/* 按钮是 44rpx 透明点击区，竖条画在 ::after 上，点不偏也不会残留按压色。 */
.chat-nav-mark::after {
  content: '';
  position: absolute;
  top: 50%;
  right: 6rpx;
  left: auto;
  width: 12rpx;
  height: 5rpx;
  border: 0;
  border-radius: 999rpx;
  background: #BAC7CF;
  transform: translateY(-50%);
}

.chat-nav-mark.active::after {
  width: 20rpx;
  background: #1F5F7A;
}

.ask-page {
  padding-bottom: calc(258rpx + env(safe-area-inset-bottom));
}

.ask-scroll {
  padding: calc(92rpx + env(safe-area-inset-top)) 40rpx 96rpx;
}

/* #ifdef APP-PLUS */
.ask-scroll {
  padding-top: calc(92rpx + var(--status-bar-height));
}

.ask-page::before {
  content: '';
  position: fixed;
  z-index: 100;
  top: 0;
  left: 0;
  right: 0;
  height: var(--status-bar-height);
  background: #F5F7F4;
  pointer-events: none;
}

.dark-mode.ask-page::before {
  background: #101820;
}
/* #endif */

.ask-topbar {
  min-height: 138rpx;
  margin: -16rpx -10rpx 34rpx;
}

.ask-topbar .subtle {
  margin-top: 14rpx;
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
.followup-chip:active {
  transform: scale(0.98);
  opacity: 0.9;
}

.prompt-icon-wrap {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 64rpx;
  height: 64rpx;
  border-radius: 999rpx;
  background: rgba(31,95,122,0.1);
}

/* 提示卡整卡可点；图标区补一层透明命中区，避免小尺寸卡片难点。 */
.prompt-icon-wrap::before {
  content: '';
  position: absolute;
  top: -12rpx;
  right: -12rpx;
  bottom: -12rpx;
  left: -12rpx;
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

.chat-earlier {
  margin: 4rpx 0 24rpx;
  padding: 18rpx 24rpx;
  border-radius: 999rpx;
  background: rgba(31, 95, 122, 0.06);
  color: #5D6B73;
  font-size: 24rpx;
  text-align: center;
}

.dark-mode .chat-earlier {
  background: rgba(255, 255, 255, 0.06);
  color: #A9B6BE;
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

.dark-mode .chat-card-head {
  border-bottom-color: rgba(126,184,209,0.14);
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

.followup-card {
  position: static;
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

.font-large .hero-title {
  font-size: 46rpx;
}

.font-large .prompt-text {
  font-size: 27rpx;
}

.font-small .hero-title {
  font-size: 38rpx;
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
.dark-mode .followup-card {
  border-color: rgba(126,184,209,0.16) !important;
  background: rgba(23,35,49,0.86) !important;
}

/* 消息气泡 / 输入区已抽成组件，暗色统一由组件内的 CSS 变量切换。 */
.dark-mode .metric-chip.primary {
  background: linear-gradient(135deg, rgba(31,95,122,0.9), rgba(16,39,55,0.94)) !important;
}

.dark-mode .page-title,
.dark-mode .hero-title,
.dark-mode .section-title,
.dark-mode .chat-title,
.dark-mode .followup-title,
.dark-mode .metric-value {
  color: #F4F7FA !important;
}

.dark-mode .hero-copy,
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
.dark-mode .chat-state {
  color: #7EB8D1 !important;
}

.dark-mode .prompt-icon-wrap,
.dark-mode .followup-chip {
  background: rgba(126,184,209,0.12) !important;
}

/* 回答下方的“依据”列表：每条都可点击跳到文章详情。 */
.citation-card {
  margin: -8rpx 0 34rpx;
  padding: 24rpx 26rpx;
  border: 1rpx solid rgba(31, 95, 122, 0.12);
  border-radius: 22rpx;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(244, 249, 250, 0.7));
  box-shadow: 0 12rpx 30rpx rgba(20, 33, 43, 0.05);
}

.citation-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 20rpx;
  margin-bottom: 14rpx;
}

.citation-title {
  color: #1F5F7A;
  font-size: 23rpx;
  font-weight: 900;
  letter-spacing: 2rpx;
}

.citation-count {
  color: #7C8790;
  font-size: 21rpx;
  font-variant-numeric: tabular-nums;
}

.citation-row {
  display: flex;
  align-items: flex-start;
  gap: 16rpx;
  width: 100%;
  margin: 0;
  padding: 16rpx 12rpx;
  border: 0;
  border-radius: 16rpx;
  background: transparent;
  text-align: left;
  line-height: 1.5;
}

.citation-row::after {
  border: none;
}

.citation-row-hover {
  background: rgba(31, 95, 122, 0.06);
}

.citation-index {
  flex: 0 0 auto;
  min-width: 40rpx;
  color: #B98A28;
  font-size: 21rpx;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.citation-main {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
  gap: 6rpx;
}

.citation-name {
  color: #143E52;
  font-size: 25rpx;
  font-weight: 900;
  text-wrap: pretty;
}

.citation-quote {
  color: #5D6B73;
  font-size: 22rpx;
  line-height: 1.55;
  text-wrap: pretty;
}

.citation-arrow {
  flex: 0 0 auto;
  color: #1F5F7A;
  font-size: 24rpx;
  line-height: 1;
  transform: translateY(2rpx);
}

.dark-mode .citation-card {
  border-color: rgba(126, 184, 209, 0.16);
  background: linear-gradient(180deg, rgba(26, 40, 52, 0.9), rgba(21, 33, 44, 0.86));
  box-shadow: 0 14rpx 32rpx rgba(0, 0, 0, 0.18);
}

.dark-mode .citation-title,
.dark-mode .citation-arrow {
  color: #7EB8D1;
}

.dark-mode .citation-count,
.dark-mode .citation-quote {
  color: #A9B6BE;
}

.dark-mode .citation-name {
  color: #F4F7FA;
}

.dark-mode .citation-index {
  color: #D4AA4E;
}

/* 暗色字重整体降 40%，避免浅色文字在暗底发胖。 */
.dark-mode .citation-title,
.dark-mode .citation-name,
.dark-mode .citation-index {
  font-weight: 540;
}

.dark-mode .citation-quote {
  font-weight: 240;
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
