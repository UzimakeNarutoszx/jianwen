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
  const params = new URLSearchParams(location.search), articleId = params.get('article') || '', initialQuestion = params.get('q') || '', issueKey = params.get('issue') || '', policyKey = params.get('policy') || ''
  let requestActive = false, answerChanged = Boolean(initialQuestion), controller = null, answer = '', displayedAnswer = '', displayedLength = 0, lastQuestion = '', stopped = false, revealTimer, revealWaiters = [], copyResetTimer
  if (!window.getToken()) {
    let previous = new URL('../index.html', location.href).href
    try {
      const referrer = new URL(document.referrer)
      if (referrer.origin === location.origin && !referrer.pathname.endsWith('/login.html')) previous = referrer.href
    } catch {}
    const login = new URL('login.html', location.href)
    login.searchParams.set('return', location.pathname + location.search)
    login.searchParams.set('cancel', previous)
    window.location.replace(login.href)
    return
  }
  if (articleId) { input.placeholder = '围绕这篇文章提出一个问题'; state.textContent = '已带入文章上下文' }
  if (issueKey || policyKey) state.textContent = issueKey ? '已带入议题公开内容' : '已带入政策公开内容，不包含自查答案'
  if (initialQuestion) input.value = initialQuestion
  function renderAnswer() {
    const visibleAnswer = requestActive ? displayedAnswer : answer
    if (!output.querySelector) {
      output.innerHTML = `<article class="answer-message"><p class="answer-label">AI 问问</p><div class="answer-copy">${markdown(visibleAnswer)}</div></article>`
      return
    }
    let copy = output.querySelector('.answer-copy')
    if (!copy) {
      output.innerHTML = '<article class="answer-message"><p class="answer-label">AI 问问</p><div class="answer-copy"></div></article>'
      copy = output.querySelector('.answer-copy')
    }
    const parsed = document.createElement('div')
    parsed.innerHTML = markdown(visibleAnswer)
    const previous = [...copy.children]
    const next = [...parsed.children]
    next.forEach((element, index) => {
      const old = previous[index]
      const unchanged = old && old.outerHTML === element.outerHTML
      if (!unchanged) {
        const replacement = element.cloneNode(true)
        if (old && old.tagName === replacement.tagName) old.replaceChildren(...replacement.childNodes)
        else if (old) old.replaceWith(replacement)
        else copy.appendChild(replacement)
      }
    })
    previous.slice(next.length).forEach(element => element.remove())
  }
  function resolveRevealWaiters() {
    revealWaiters.splice(0).forEach(resolve => resolve())
  }
  function revealNextCharacter() {
    if (displayedLength >= answer.length) {
      revealTimer = null
      resolveRevealWaiters()
      return
    }
    const character = Array.from(answer.slice(displayedLength))[0]
    displayedAnswer += character
    displayedLength += character.length
    renderAnswer()
    revealTimer = setTimeout(revealNextCharacter, 12)
  }
  function finishReveal() {
    if (displayedLength >= answer.length) return Promise.resolve()
    if (!revealTimer) revealTimer = setTimeout(revealNextCharacter, 0)
    return new Promise(resolve => revealWaiters.push(resolve))
  }
  function restoreAnswer() {
    if (initialQuestion) return
    if (typeof localStorage === 'undefined') return
    try {
      const saved = JSON.parse(localStorage.getItem('jianwen_web_ask_last') || 'null')
      if (!saved || !saved.question || !saved.answer) return
      lastQuestion = saved.question; answer = saved.answer; answerChanged = true; input.value = saved.question
      renderAnswer(); status.textContent = '已恢复上一次问问记录'
    } catch { localStorage.removeItem('jianwen_web_ask_last') }
  }
  function saveAnswer() {
    if (typeof localStorage === 'undefined') return
    if (lastQuestion && answer) localStorage.setItem('jianwen_web_ask_last', JSON.stringify({ question: lastQuestion, answer, savedAt: Date.now() }))
  }
  function updateAnswer(text) {
    answer = text
    status.textContent = '正在生成回答…'
    if (!revealTimer) revealTimer = setTimeout(revealNextCharacter, 0)
  }
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
    requestActive = true; answerChanged = true; lastQuestion = question; answer = ''; displayedAnswer = ''; displayedLength = 0; stopped = false; controller = new AbortController()
    submit.disabled = true; input.readOnly = true; stop.hidden = false; actions.hidden = true; retry.hidden = true; copy.disabled = true; resetCopyButton()
    status.textContent = '正在连接 AI 服务…'; output.setAttribute('aria-busy','true')
    output.innerHTML = '<div class="answer-placeholder answer-loading"><span class="loading-spinner" aria-hidden="true"></span><strong>正在思考…</strong><p>回答会逐步显示，你可以随时停止。</p></div>'
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() },120000)
    try {
      const token = window.getToken(); if (!token) throw new Error('登录已失效，请重新登录。')
      const response = await fetch(`${window.jianwenApi.baseUrl()}/api/v1/content/ask/stream`, { method:'POST', headers:{ 'Content-Type':'application/json', Authorization:`Bearer ${token}` }, body:JSON.stringify({ question, article_id:articleId, issue_key:issueKey, policy_key:policyKey }), signal:controller.signal })
      if (!response.ok) { if (response.status === 401) window.clearSession(); const data = await response.json().catch(() => ({})); throw new Error(typeof data.detail === 'string' ? data.detail : `请求失败（${response.status}），请稍后重试。`) }
      await consumeStream(response,updateAnswer,controller.signal)
      status.textContent = '回答接收完毕 · 请结合原始资料核对'; saveAnswer()
    } catch (error) {
      const message = stopped ? '已停止生成，已收到的内容已保留。' : timedOut ? '等待回答超时，请稍后重试。' : error.message || '网络连接中断，请稍后重试。'
      status.textContent = message; retry.hidden = false
      if (!answer) output.innerHTML = `<div class="answer-placeholder"><strong>${stopped ? '已停止生成' : '暂时无法回答'}</strong><p>${escapeHtml(message)}</p>${window.getToken() ? '' : `<a class="button button-primary" href="login.html?return=${encodeURIComponent(location.pathname + location.search)}">重新登录</a>`}</div>`
    } finally {
      clearTimeout(timer); await finishReveal(); requestActive = false; if (answer) renderAnswer(); saveAnswer()
      output.removeAttribute('aria-busy'); submit.disabled = false; input.readOnly = false; stop.hidden = true; actions.hidden = false; copy.disabled = !answer
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); ask(input.value.trim()) })
  stop.addEventListener('click', () => { if (requestActive) { stopped = true; controller.abort() } })
  retry.addEventListener('click', () => { input.value = lastQuestion; ask(lastQuestion) })
  function resetCopyButton() {
    clearTimeout(copyResetTimer)
    copy.setAttribute('data-state', 'idle')
    copy.textContent = '复制回答'
  }
  copy.addEventListener('click', async () => {
    if (!answer) return
    try {
      await navigator.clipboard.writeText(answer)
      clearTimeout(copyResetTimer)
      copy.setAttribute('data-state', 'copied')
      copy.textContent = '✓ 已复制'
      copyResetTimer = setTimeout(resetCopyButton, 2500)
    } catch { status.textContent = '浏览器未允许访问剪贴板，请选中回答后复制。' }
  })
  window.addEventListener('pagehide', () => { controller?.abort(); clearTimeout(copyResetTimer) })
  restoreAnswer(); loadPrompts()
})()
