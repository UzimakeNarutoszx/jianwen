(function () {
  'use strict'
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]))
  const inline = text => text.split(/(`[^`\n]+`)/g).map(p => p.startsWith('`') && p.endsWith('`') ? `<code>${escapeHtml(p.slice(1,-1))}</code>` : escapeHtml(p).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/\*([^*\n]+)\*/g,'<em>$1</em>')).join('')
  function markdown(text) {
    const result = []; let code = null; let list = ''
    const endList = () => { if (list) result.push(`</${list}>`); list = '' }
    for (const line of String(text).replace(/\r\n?/g,'\n').split('\n')) {
      if (/^\s*```/.test(line)) { endList(); if (code === null) code = []; else { result.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`); code = null } continue }
      if (code !== null) { code.push(line); continue }
      const item = line.match(/^\s*(?:([-*+])|\d+[.)、])\s+(.+)$/)
      if (item) { const type = item[1] ? 'ul' : 'ol'; if (list !== type) { endList(); list = type; result.push(`<${type}>`) } result.push(`<li>${inline(item[2])}</li>`); continue }
      endList(); if (!line.trim()) continue
      const heading = line.match(/^#{1,6}\s+(.+)$/)
      if (heading) result.push(`<h3>${inline(heading[1])}</h3>`)
      else if (/^>\s?/.test(line)) result.push(`<blockquote>${inline(line.replace(/^>\s?/,''))}</blockquote>`)
      else result.push(`<p>${inline(line)}</p>`)
    }
    endList(); if (code !== null) result.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`)
    return result.join('')
  }
  async function consumeStream(response, onText, signal) {
    if (!response.body) throw new Error('浏览器未提供可读取的回答，请换用现代浏览器。')
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let answer = ''
    try {
      while (true) {
        if (signal?.aborted) throw new DOMException('Aborted','AbortError')
        const { done, value } = await reader.read(); if (done) break
        answer += decoder.decode(value,{ stream:true })
        if (answer.length > 250000) { await reader.cancel(); throw new Error('回答过长，已停止接收。请缩小问题范围。') }
        onText(answer)
      }
      answer += decoder.decode()
      if (!answer.trim()) throw new Error('AI 未返回有效回答，请稍后重试。')
      onText(answer); return answer
    } finally { reader.releaseLock() }
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports = { markdown, consumeStream }; return }
  const $ = id => document.getElementById(id)
  const form = $('ask-form'), input = $('ask-input'), output = $('ask-output'), state = $('context-state'), submit = $('ask-submit'), stop = $('ask-stop'), status = $('ask-status'), actions = $('answer-actions'), copy = $('answer-copy-button'), retry = $('ask-retry')
  const params = new URLSearchParams(location.search), articleId = params.get('article') || '', initialQuestion = params.get('q') || ''
  let requestActive = false, answerChanged = Boolean(initialQuestion), controller = null, answer = '', lastQuestion = '', stopped = false, renderTimer
  if (!window.getToken()) { window.location.replace(`login.html?return=${encodeURIComponent(location.pathname + location.search)}`); return }
  if (articleId) { input.placeholder = '围绕这篇文章提出一个问题'; state.textContent = '已带入文章上下文' }
  if (initialQuestion) input.value = initialQuestion
  function renderAnswer() { renderTimer = null; output.innerHTML = `<article class="answer-message"><p class="answer-label">AI 问问</p><div class="answer-copy">${markdown(answer)}</div></article>` }
  function updateAnswer(text) { answer = text; status.textContent = '正在生成回答…'; if (!renderTimer) renderTimer = setTimeout(renderAnswer,80) }
  document.querySelector('.prompt-grid').addEventListener('click', event => { const b = event.target.closest('.prompt-chip'); if (!b || requestActive) return; input.value = b.dataset.question || b.textContent.trim(); input.focus() })
  async function loadPrompts() {
    try {
      const data = await window.jianwenApi.askBootstrap(); const prompts = Array.isArray(data.prompts) ? data.prompts.slice(0,3) : []
      if (prompts.length) document.querySelector('.prompt-grid').innerHTML = prompts.map(p => `<button type="button" class="prompt-chip" data-question="${escapeHtml(p)}">${escapeHtml(p)}</button>`).join('')
      if (data.welcome_message && !initialQuestion && !requestActive && !answerChanged) output.innerHTML = `<div class="answer-placeholder"><span aria-hidden="true">✦</span><strong>${escapeHtml(data.welcome_message)}</strong><p>选择一个推荐问题，或在下方输入自己的问题。</p></div>`
    } catch { state.textContent = articleId ? '已带入文章上下文 · 推荐问题暂不可用' : '推荐问题暂时不可用，可直接提问' }
  }
  async function ask(question) {
    if (requestActive) return
    if (!question) { status.textContent = '请先输入一个问题。'; input.focus(); return }
    if (question.length > 4000) { status.textContent = '请将问题控制在 4000 字以内。'; input.focus(); return }
    requestActive = true; answerChanged = true; lastQuestion = question; answer = ''; stopped = false; controller = new AbortController()
    submit.disabled = true; input.readOnly = true; stop.hidden = false; actions.hidden = true; retry.hidden = true; copy.disabled = true; copy.textContent = '复制回答'
    status.textContent = '正在连接 AI 服务…'; output.setAttribute('aria-busy','true')
    output.innerHTML = '<div class="answer-placeholder answer-loading"><span class="loading-spinner" aria-hidden="true"></span><strong>正在思考…</strong><p>回答会逐步显示，你可以随时停止。</p></div>'
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() },120000)
    try {
      const token = window.getToken(); if (!token) throw new Error('登录已失效，请重新登录。')
      const response = await fetch(`${window.jianwenApi.baseUrl()}/api/v1/content/ask/stream`, { method:'POST', headers:{ 'Content-Type':'application/json', Authorization:`Bearer ${token}` }, body:JSON.stringify({ question, article_id:articleId }), signal:controller.signal })
      if (!response.ok) { if (response.status === 401) window.clearSession(); const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败（${response.status}），请稍后重试。`) }
      await consumeStream(response,updateAnswer,controller.signal)
      status.textContent = '回答接收完毕 · 请结合原始资料核对'
    } catch (error) {
      const message = stopped ? '已停止生成，已收到的内容已保留。' : timedOut ? '等待回答超时，请稍后重试。' : error.message || '网络连接中断，请稍后重试。'
      status.textContent = message; retry.hidden = false
      if (!answer) output.innerHTML = `<div class="answer-placeholder"><strong>${stopped ? '已停止生成' : '暂时无法回答'}</strong><p>${escapeHtml(message)}</p>${window.getToken() ? '' : `<a class="button button-primary" href="login.html?return=${encodeURIComponent(location.pathname + location.search)}">重新登录</a>`}</div>`
    } finally {
      clearTimeout(timer); clearTimeout(renderTimer); renderTimer = null; if (answer) renderAnswer()
      requestActive = false; output.removeAttribute('aria-busy'); submit.disabled = false; input.readOnly = false; stop.hidden = true; actions.hidden = false; copy.disabled = !answer
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); ask(input.value.trim()) })
  stop.addEventListener('click', () => { if (requestActive) { stopped = true; controller.abort() } })
  retry.addEventListener('click', () => { input.value = lastQuestion; ask(lastQuestion) })
  copy.addEventListener('click', async () => { if (!answer) return; try { await navigator.clipboard.writeText(answer); copy.textContent = '已复制' } catch { status.textContent = '浏览器未允许访问剪贴板，请选中回答后复制。' } })
  window.addEventListener('pagehide', () => controller?.abort())
  loadPrompts()
})()
