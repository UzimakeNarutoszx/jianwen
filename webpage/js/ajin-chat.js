(function () {
  const note = document.querySelector('.feature-note')
  if (!note) return
  const section = document.createElement('section')
  section.className = 'ajin-chat'
  section.id = 'ajin-chat'
  section.setAttribute('aria-labelledby', 'ajin-chat-title')
  section.innerHTML = '<div class="ajin-chat-heading"><div><p class="eyebrow">AJIN / CHAT</p><h2 id="ajin-chat-title">和阿烬聊聊</h2><p>像“问问”一样直接输入问题，阿烬会用自己的兴趣和思考方式接住话题。</p></div><div class="ajin-chat-status"><span class="status-dot" aria-hidden="true"></span><span>阿烬已就绪</span></div></div><div id="ajin-chat-log" class="ajin-chat-log" aria-live="polite"></div><form id="ajin-chat-form" class="ajin-chat-form" novalidate><input id="ajin-chat-input" required maxlength="4000" autocomplete="off" placeholder="例如：给我一个适合架子鼓练习的游戏 BGM…"><button class="button button-primary" type="submit">发送 <span aria-hidden="true">→</span></button></form><p id="ajin-chat-hint" class="ajin-chat-hint">需要登录后使用，对话会遵循阿烬的角色提示词。</p>'
  note.parentNode.insertBefore(section, note)

  const form = section.querySelector('#ajin-chat-form')
  const input = section.querySelector('#ajin-chat-input')
  const log = section.querySelector('#ajin-chat-log')
  const hint = section.querySelector('#ajin-chat-hint')
  let history = []
  try {
    const saved = JSON.parse(localStorage.getItem('jianwen_web_ajin_history') || '[]')
    history = Array.isArray(saved) ? saved.slice(-20) : []
  } catch { localStorage.removeItem('jianwen_web_ajin_history') }
  const addMessage = (text, role) => {
    const node = document.createElement('div')
    node.className = `ajin-chat-message${role === 'user' ? ' user' : ''}`
    node.textContent = text
    log.appendChild(node)
    log.scrollTop = log.scrollHeight
  }
  if (history.length) history.forEach(item => addMessage(item.content, item.role))
  else addMessage('嘿，想聊点什么？架子鼓、代码、数学，还是最近看到的故事？', 'assistant')
  form.addEventListener('submit', async event => {
    event.preventDefault()
    const question = input.value.trim()
    if (!question) return
    if (!window.getToken()) {
      hint.textContent = '请先登录见闻账号，再和阿烬对话。'
      return
    }
    const submit = form.querySelector('button')
    submit.disabled = true
    addMessage(question, 'user')
    history.push({ role: 'user', content: question })
    input.value = ''
    hint.textContent = '阿烬正在想…'
    try {
      const result = await window.jianwenApi.ajinChat(question, history.slice(0, -1))
      addMessage(result.answer || '我刚刚卡了一下，再问一次试试。', 'assistant')
      history.push({ role: 'assistant', content: result.answer || '' })
      hint.textContent = '阿烬已回应'
    } catch (error) {
      addMessage(error.message || '暂时无法连接阿烬。', 'assistant')
      history.pop()
      hint.textContent = '请求失败，请稍后再试。'
    } finally { submit.disabled = false; input.focus() }
    localStorage.setItem('jianwen_web_ajin_history', JSON.stringify(history.slice(-20)))
  })
})()
