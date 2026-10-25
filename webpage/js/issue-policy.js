(function () {
  'use strict'
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]))
  const safeUrl = value => /^https?:\/\//i.test(value || '') ? value : ''
  const unavailable = policy => !policy.available || (policy.review_expires_at && Date.parse(`${policy.review_expires_at}T23:59:59+08:00`) < Date.now())
  const labels = { potentially_eligible: '可能符合条件', not_eligible: '暂不符合条件', insufficient_information: '信息不足，暂无法判断' }
  const checkLabels = { met: '已满足', not_met: '未满足', unknown: '待确认' }
  const sources = items => (items || []).map(s => safeUrl(s.url) ? `<a class="ip-source text-link" href="${esc(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.title || '官方依据')} · ${esc(s.org)} ${esc(s.published_at)}</a>` : '').join('')
  const stageLabel = value => ({ consulting: '征求意见', published: '已发布', implementing: '实施中', ended: '已结束', ongoing: '持续跟进' }[value] || value)
  const issueLink = item => `issue.html?key=${encodeURIComponent(item.issue_key)}`
  const policyLink = item => `policy-check.html?key=${encodeURIComponent(item.policy_key)}`
  const issueCard = item => `<article class="ip-card"><p class="ip-meta">${esc(stageLabel(item.stage))}</p><h2>${esc(item.title)}</h2><p>${esc(item.status_line)}</p><p class="ip-meta ip-count">${esc(item.event_count)} 条进展</p><a class="text-link" href="${issueLink(item)}">查看时间线</a></article>`
  if (typeof module !== 'undefined' && module.exports) { module.exports = { esc, safeUrl, unavailable, issueCard }; return }
  const api = window.jianwenApi, page = document.querySelector('[data-issue-page], [data-policy-page]')
  const params = new URLSearchParams(location.search); let key = params.get('key') || ''
  const login = () => location.assign(`login.html?return=${encodeURIComponent(location.pathname + location.search)}`)
  window.jianwenIssueLinks = article => !article.issue && !(article.policy_checks || []).length ? '' : `<section class="ip-entry">${article.issue ? `<p>所属议题：<a class="text-link" href="${issueLink(article.issue)}">${esc(article.issue.title)} · 查看进展</a></p><p>本文是第 <span class="ip-count">${esc(article.issue.position)}</span> / ${esc(article.issue.event_count)} 条进展 · ${esc(stageLabel(article.issue.stage))}</p><p>${esc(article.issue.status_line)}</p><button class="button button-secondary" data-follow-issue="${esc(article.issue.issue_key)}">关注议题</button>${article.issue.prev_delta ? `<p>上次进展：${esc(article.issue.prev_delta)}</p>` : ''}` : ''}${(article.policy_checks || []).map(p => `<a class="text-link" href="${policyLink(p)}">${esc(p.title)} · 匿名政策自查</a>`).join('')}</section>`
  if (!page) {
    document.addEventListener('click', async event => {
      const button = event.target.closest('[data-follow-issue]'); if (!button || button.disabled) return;
      if (!window.getToken()) { login(); return }
      button.disabled = true;
      try { await api.followIssue(button.dataset.followIssue, true); button.textContent = '已关注' }
      catch (error) { button.textContent = error.message; button.disabled = false }
    })
    const main = document.querySelector('main'), name = location.pathname.split('/').pop()
    if (!main) return
    const entry = document.createElement('section'); entry.className = 'ip-entry'; entry.setAttribute('aria-label', '议题与政策入口')
    if (name === 'discover.html') { entry.className = 'ip-discover-entry'; entry.innerHTML = '<div class="ip-portals"><a class="ip-portal ip-portal-track" href="issues.html"><span class="ip-portal-symbol" aria-hidden="true"><img class="ip-portal-icon" src="../assets/icons/issue-track.svg" alt=""></span><span class="ip-portal-copy"><strong>追踪</strong><span>沿着时间线，看懂每一步变化</span></span><span class="ip-portal-open" aria-hidden="true">↗</span></a><a class="ip-portal ip-portal-check" href="policy-checks.html"><span class="ip-portal-symbol" aria-hidden="true"><img class="ip-portal-icon" src="../assets/icons/policy-check.svg" alt=""></span><span class="ip-portal-copy"><strong>自查</strong><span>对照官方条件，理清申请资格</span></span><span class="ip-portal-open" aria-hidden="true">↗</span></a></div><div class="ip-discover-grid"></div>'; main.querySelector('.discover-hero').after(entry); api.issues().then(items => { const active = items.map(i => i.issue || i).filter(i => !['ended','closed'].includes(i.stage)).slice(0, 6); entry.querySelector('.ip-discover-grid').innerHTML = active.map(issueCard).join('') || '暂无活跃议题。' }).catch(() => { entry.querySelector('.ip-discover-grid').textContent = '议题暂时无法加载。' }) }
    if (name === 'profile.html') { entry.innerHTML = '<a class="text-link" href="issues.html?mine=1">我关注的议题</a>'; main.prepend(entry) }
    if (name === 'index.html') {
      let request = 0
      async function refresh() { const revision = ++request, token = window.getToken(); entry.replaceChildren(); entry.remove(); if (!token) return; try { const updates = await api.issueUpdates(); if (revision !== request || token !== window.getToken()) return; entry.innerHTML = updates.length ? `<h2>关注议题有 ${updates.length} 项新进展</h2>${updates.map(i => `<a class="text-link" href="${issueLink(i.issue)}">${esc(i.issue.title)} · <span class="ip-count">${esc(i.new_events)}</span> 条更新</a>`).join('')}` : '' ; if (updates.length) main.prepend(entry) } catch { if (revision === request) { entry.textContent = '议题更新暂时无法加载，请稍后重试。'; main.prepend(entry) } } }
      refresh(); window.addEventListener('pageshow', refresh); window.addEventListener('jianwen-session-change', refresh); window.addEventListener('storage', refresh)
    }
    return
  }
  const status = document.getElementById('ip-status'), content = document.getElementById('ip-content')
  let issue = null, policy = null, answers = {}, result = null, step = 0, busy = false, generation = 0, entrySeenVersion = 0
  function reset() { answers = {}; result = null; step = 0 }
  function fail(error) { status.className = 'ip-error'; status.textContent = error.message; const retry = document.createElement('button'); retry.className = 'button button-secondary'; retry.textContent = '重新加载'; retry.addEventListener('click', load); content.replaceChildren(retry) }
  function renderIssue() {
    content.innerHTML = `<p class="ip-meta">${esc(stageLabel(issue.stage))}</p><h1>${esc(issue.title)}</h1><p>${esc(issue.status_line)}</p><div class="ip-actions"><button class="button button-primary" data-action="follow" ${busy ? 'disabled' : ''}>${issue.is_following ? '取消关注' : '关注议题'}</button><a class="button button-secondary" href="ask.html?issue=${encodeURIComponent(issue.issue_key || key)}">围绕议题问问</a>${issue.is_following ? `<button class="button button-secondary" data-action="seen" ${busy ? 'disabled' : ''}>标记当前进展已读</button>` : ''}</div>${(issue.policy_checks || []).map(p => `<section class="ip-card"><h2>${esc(p.title)}</h2><a class="text-link" href="${policyLink(p)}">自查</a></section>`).join('')}<h2>进展时间线</h2>${issue.is_following && entrySeenVersion ? `<p class="ip-meta">上次看到这里：发布版本 ${esc(entrySeenVersion)}；标有「有新进展」的是此后新增或修订的内容。</p>` : ''}<div class="ip-timeline">${(issue.events || []).map((e, i) => `<article class="ip-card ip-event ${i < 2 ? '' : 'is-collapsed'}"><p class="ip-meta">${esc(e.event_date)}${e.updated_version > entrySeenVersion ? ' · 有新进展' : ''}${e.historical ? ' · 历史进展' : ''}</p><h3>第 ${esc(e.position)} 条进展</h3><div class="ip-event-body"><div><p>${esc(e.delta_summary)}</p>${e.article_id ? `<a class="text-link" href="article.html?id=${encodeURIComponent(e.article_id)}">阅读关联文章</a>` : ''}${sources(e.references)}</div></div>${i >= 2 ? '<button class="button button-secondary" data-action="toggle-event">展开</button>' : ''}</article>`).join('') || '<p>暂无已发布进展。</p>'}</div>`
  }
  function renderPolicy() {
    const blocked = unavailable(policy), q = policy.questions?.[step], allSources = result?.sources || policy.sources || []
    const answered = q && Object.prototype.hasOwnProperty.call(answers, q.id)
    content.innerHTML = `<p class="ip-meta">${esc(policy.region)}</p><h1>${esc(policy.title)}</h1><p>${esc(policy.summary)}</p><p class="ip-meta">核验时间：${esc(policy.verified_at || '未核验')} · 复核期限：${esc(policy.review_expires_at || '未设置')}</p><p>匿名自查；答案仅在本页内存中，离开后清除。结果供准备申请参考，以官方审核为准。</p>${blocked ? `<section class="ip-card"><h2>暂不可自查</h2><p>${esc(policy.unavailable_reason || '政策已暂停或超过复核期限，请查看官方依据。')}</p></section>` : result ? `<section class="ip-card" aria-live="polite"><h2>${esc(labels[result.result])}</h2><p>${esc(result.title)}</p>${(result.checks || []).map(c => { const source = allSources.find(s => s.id === c.source_id); return `<article class="ip-card"><h3>${esc(c.title)} · ${esc(checkLabels[c.status])}</h3><p>${esc(c.reason)}</p>${source ? sources([source]) : ''}</article>` }).join('')}${(result.next_steps || []).map(s => `<p>${esc(s)}</p>`).join('')}</section>` : q ? `<section class="ip-card"><p class="ip-meta ip-count">第 ${step + 1} / ${policy.questions.length} 题</p><h2 id="question-title" tabindex="-1">${esc(q.title)}</h2><p>${esc(q.help)}</p><div role="group" aria-labelledby="question-title">${q.options.map((o, i) => `<button type="button" class="ip-option" data-option="${i}" aria-pressed="${answers[q.id] === o.value}">${answers[q.id] === o.value ? '✓ ' : ''}${esc(o.label)}</button>`).join('')}</div><div class="ip-actions"><button class="button button-secondary" data-action="previous" ${step === 0 || busy ? 'disabled' : ''}>上一题</button><button class="button button-primary" data-action="${step < policy.questions.length - 1 ? 'next' : 'evaluate'}" ${!answered || busy ? 'disabled' : ''}>${busy ? '正在核对…' : step < policy.questions.length - 1 ? '下一题' : '查看自查结果'}</button></div></section>` : '<p>政策问题正在整理。</p>'}<div class="ip-actions">${!blocked ? `<button class="button button-secondary" data-action="reset" ${busy ? 'disabled' : ''}>${result ? '重新自查' : '清空答案'}</button>` : ''}<a class="button button-secondary" href="ask.html?policy=${encodeURIComponent(key)}">问问这项政策</a></div><section class="ip-card"><h2>官方依据</h2>${sources(allSources)}</section>${(result?.materials || policy.materials || []).length ? `<section class="ip-card"><h2>申请材料</h2>${(result?.materials || policy.materials).map(m => `<p>${esc(m)}</p>`).join('')}</section>` : ''}${safeUrl(result?.application_url || policy.application_url) ? `<a class="button button-primary" target="_blank" rel="noopener noreferrer" href="${esc(result?.application_url || policy.application_url)}">前往官方办理入口</a>` : ''}`
  }
  async function load() {
    const current = ++generation; busy = false; status.className = ''; status.textContent = '正在加载…'; content.replaceChildren(); reset(); issue = null; policy = null
    try {
      if (page.dataset.issuePage === 'list') { if (params.get('mine') === '1' && !window.getToken()) { login(); return } const items = await (params.get('mine') === '1' ? api.followedIssues() : api.issues()); if (current !== generation) return; content.innerHTML = items.map(i => issueCard(i.issue || i)).join('') || '<p>暂无议题，稍后再来看看。</p>' }
      else if (page.dataset.issuePage === 'detail') { const data = await api.issue(key); if (current !== generation) return; issue = data; entrySeenVersion = Number(data.last_seen_version || 0); key = data.issue_key || key; renderIssue(); if (data.is_following && data.published_version) api.markIssueSeen(key, data.published_version).catch(() => {}) }
      else if (page.dataset.policyPage === 'list') { const items = await api.policyChecks(); if (current !== generation) return; content.innerHTML = items.map(p => `<article class="ip-card"><p class="ip-meta">${esc(p.region)}</p><h2>${esc(p.title)}</h2><p>${esc(p.summary)}</p><p class="ip-meta">${esc(p.available ? '可进行自查' : p.unavailable_reason || '暂不可自查')}</p><a class="text-link" href="${policyLink(p)}">查看条件与依据</a></article>`).join('') || '<p>暂无已核验的政策。</p>' }
      else { const data = await api.policyCheck(key); if (current !== generation) return; policy = data; renderPolicy() }
      status.textContent = ''
    } catch (error) { if (current === generation) fail(error) }
  }
  content.addEventListener('click', async event => {
    const option = event.target.closest('[data-option]'), button = event.target.closest('[data-action]'); if (busy) return
    if (option && policy) { const q = policy.questions[step]; answers[q.id] = q.options[Number(option.dataset.option)].value; renderPolicy(); content.querySelector(`[data-option="${option.dataset.option}"]`)?.focus(); return }
    if (!button) return; const action = button.dataset.action
    if (action === 'toggle-event') { const card = button.closest('.ip-event'); card.classList.toggle('is-collapsed'); button.textContent = card.classList.contains('is-collapsed') ? '展开' : '收起'; return }
    if (['previous','next','reset'].includes(action)) { if (action === 'reset') reset(); else step += action === 'next' ? 1 : -1; renderPolicy(); document.getElementById('question-title')?.focus(); return }
    if (action === 'follow' || action === 'seen') {
      if (!window.getToken()) { login(); return } const current = issue, token = window.getToken(); busy = true; renderIssue()
      try { const data = action === 'follow' ? await api.followIssue(key, !current.is_following) : await api.markIssueSeen(key, current.published_version); if (current !== issue || token !== window.getToken()) return; if (action === 'follow') current.is_following = data.is_following; else current.last_seen_version = data.last_seen_version; status.textContent = action === 'seen' ? '当前进展已读；后续发布仍会提醒。' : current.is_following ? '已关注，今日会提醒新进展。' : '已取消关注。' }
      catch (error) { status.textContent = error.message }
      finally { busy = false; if (issue === current) renderIssue() }
    }
    if (action === 'evaluate' && policy && !unavailable(policy)) {
      busy = true; renderPolicy(); const current = generation
      try { const data = await api.evaluatePolicyCheck(key, policy.version, answers); if (current !== generation) return; result = data; status.textContent = '自查完成。' }
      catch (error) { if (current !== generation) return; if ([409,410].includes(error.status)) { reset(); policy = null; fail(new Error(error.status === 409 ? '政策版本已更新，请重新加载后再自查。' : '政策已暂停或到期，请重新加载查看官方依据。')) } else status.textContent = error.message }
      finally { busy = false; if (policy && current === generation) renderPolicy() }
    }
  })
  window.addEventListener('pagehide', () => { generation++; reset(); content.replaceChildren() })
  window.addEventListener('pageshow', event => { if (event.persisted) load() })
  window.addEventListener('jianwen-session-change', () => { if (page.dataset.issuePage) load() })
  window.addEventListener('storage', () => { if (page.dataset.issuePage) load() })
  load()
})()
