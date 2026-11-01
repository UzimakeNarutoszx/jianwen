(async function () {
  if (!window.getToken()) return
  const host = document.createElement('section')
  host.className = 'profile-section'
  host.innerHTML = `<h2>让见闻更懂你</h2><p>更新个人资料，选择你希望持续关注的议题。</p><form id="settings-form"><div class="settings-fields"><label>昵称<input name="nickname" maxlength="16" required autocomplete="nickname"></label><label>个人简介<input name="bio" maxlength="160" placeholder="记录你的好奇与关注"></label></div><fieldset class="settings-topics"><legend>关注主题</legend><div id="settings-topics">正在加载主题…</div></fieldset><button type="submit" class="button button-primary">保存偏好</button><p role="status" id="settings-state"></p></form>`
  document.querySelector('.profile-hero').after(host)
  const form = host.querySelector('form')
  const state = host.querySelector('#settings-state')
  const submit = form.querySelector('button')
  submit.disabled = true
  try {
    const [profile, categories, selected] = await Promise.all([jianwenApi.profile(), jianwenApi.categories(), jianwenApi.topics()])
    form.elements.nickname.value = profile.nickname || ''
    form.elements.bio.value = profile.bio || ''
    const topics = host.querySelector('#settings-topics')
    topics.textContent = ''
    const names = [...new Set([...categories.map(item => typeof item === 'string' ? item : item.name), ...selected].filter(Boolean))]
    for (const name of names) {
      const label = document.createElement('label')
      const input = document.createElement('input')
      input.type = 'checkbox'
      input.name = 'topic'
      input.value = name
      input.checked = selected.includes(name)
      label.append(input, document.createTextNode(name))
      topics.append(label)
    }
    submit.disabled = false
  } catch (error) { state.textContent = `偏好加载失败：${error.message}。请刷新重试。`; return }
  form.addEventListener('submit', async event => {
    event.preventDefault()
    const nickname = form.elements.nickname.value.trim()
    if (!nickname) { state.textContent = '昵称不能为空。'; form.elements.nickname.focus(); return }
    const topics = [...form.querySelectorAll('[name="topic"]:checked')].map(input => input.value)
    if (topics.length > 30) { state.textContent = '最多关注 30 个主题。'; return }
    submit.disabled = true
    state.textContent = '正在保存…'
    try {
      const profile = await jianwenApi.updateProfile({ nickname, bio: form.elements.bio.value.trim() })
      document.querySelector('#name').textContent = profile.nickname
      document.querySelector('#bio').textContent = profile.bio || '同步你的收藏、历史和 AI 问问记录。'
      await jianwenApi.saveTopics(topics)
      const user = window.getSessionUser() || {}
      localStorage.setItem('jianwen_auth_user', JSON.stringify({ ...user, nickname: profile.nickname }))
      state.textContent = '已保存。今日阅读将结合你的关注主题推荐。'
      const topicPanel = [...document.querySelectorAll('#profile .profile-section')].find(section => section.querySelector('h2')?.textContent === '关注主题')
      if (topicPanel) {
        const list = topicPanel.querySelector('.tag-list')
        list.replaceChildren(...topics.map(topic => { const span = document.createElement('span'); span.textContent = topic; return span }))
        if (!topics.length) list.textContent = '暂无关注主题。'
      }
    } catch (error) { state.textContent = `保存未全部完成：${error.message}。你可以重试。` }
    finally { submit.disabled = false }
  })
})()
