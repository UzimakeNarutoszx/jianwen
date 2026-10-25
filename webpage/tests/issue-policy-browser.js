// Run with playwright-cli run-code --filename webpage/tests/issue-policy-browser.js.
async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message) }
  page.setDefaultTimeout(12000)
  const origin = 'http://127.0.0.1:8765'
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  const brief = { issue_key: 'housing', title: '住房保障进展', stage: 'implementing', status_line: '申请条件已明确', event_count: 1, published_version: 3 }
  const detail = { ...brief, is_following: true, last_seen_version: 1, position: null, prev_delta: null, events: [{ event_id: 'same-event', event_date: '2026-10-24', position: 1, delta_summary: '原事件修订也应提醒', updated_version: 3, article_id: 'article-1', references: [] }], policy_checks: [{ policy_key: 'pilot', title: '政策试点' }] }
  const policy = { policy_key: 'pilot', title: '毕业生补贴自查', region: '杭州', version: 'v1', status: 'published', available: true, summary: '逐题核对申请条件', verified_at: '2026-10-24', review_expires_at: '2099-01-01', sources: [{ id: 's1', title: '官方通知', url: 'https://www.hangzhou.gov.cn/', org: '杭州市政府' }], questions: [{ id: 'degree', title: '学历是否符合？', help: '按证书选择', options: [{ value: 'yes', label: '符合学历要求' }, { value: 'no', label: '不符合学历要求' }, { value: 'unknown', label: '尚不确定' }] }], materials: ['毕业证明'], application_url: 'https://www.hangzhou.gov.cn/' }
  let seenBody = null, evaluateBody = null, failure = 0
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data = null
    if (path.endsWith('/content/issues/housing')) data = detail
    else if (path.endsWith('/content/issues')) data = [brief]
    else if (path.endsWith('/housing/seen')) { seenBody = route.request().postDataJSON(); data = { last_seen_version: seenBody.published_version } }
    else if (path.endsWith('/housing/follow')) data = { is_following: route.request().method() === 'POST' }
    else if (path.endsWith('/policy-checks/pilot/evaluate')) {
      evaluateBody = route.request().postDataJSON()
      if (failure) return route.fulfill({ status: failure, json: { detail: '政策已变更' } })
      const answer = evaluateBody.answers.degree
      data = { ...policy, result: answer === 'yes' ? 'potentially_eligible' : answer === 'no' ? 'not_eligible' : 'insufficient_information', title: '自查结果', checks: [{ question_id: 'degree', title: '学历', status: answer === 'yes' ? 'met' : answer === 'no' ? 'not_met' : 'unknown', reason: '请核对官方通知', source_id: 's1' }], next_steps: ['准备材料'] }
    } else if (path.endsWith('/policy-checks/pilot')) data = policy
    else if (path.endsWith('/policy-checks')) data = [policy]
    else if (path.endsWith('/ask/bootstrap')) data = { prompts: [], followups: [] }
    else if (path.endsWith('/content/issues/empty')) data = { ...detail, events: [] }
    else if (path.endsWith('/profile/issues/updates')) data = [{ issue: brief, new_events: 1, events: detail.events }]
    else data = []
    return route.fulfill({ json: data })
  })
  await page.goto(origin + '/jianwen/issue.html?key=housing&v=20261025-3')
  await page.evaluate(() => { localStorage.removeItem('jianwen_auth_token'); localStorage.removeItem('jianwen_login_expires_at') })
  await page.reload()
  await page.getByRole('heading', { name: '住房保障进展', exact: true }).waitFor()
  await page.getByRole('button', { name: '关注议题', exact: true }).count() // authenticated flags are supplied by the mock
  await page.getByRole('button', { name: '取消关注', exact: true }).click()
  await page.waitForURL('**/login.html?return=*')
  assert(new URL(page.url()).searchParams.get('return').includes('key=housing'), 'login preserves issue key')
  await page.evaluate(() => { localStorage.setItem('jianwen_auth_token', 'ui-mock-token'); localStorage.setItem('jianwen_login_expires_at', String(Date.now() + 600000)) })
  await page.goto(origin + '/jianwen/issue.html?key=housing&v=20261025-3')
  await page.getByRole('button', { name: '标记当前进展已读' }).click()
  await page.getByText('当前进展已读；后续发布仍会提醒。', { exact: true }).waitFor()
  assert(seenBody.published_version === 3 && !('event_id' in seenBody), 'seen uses loaded publication version')
  assert(await page.getByText('2026-10-24 · 有新进展', { exact: true }).count() === 1, 'entry-time unread boundary remains visible after acknowledgement')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: 'output/playwright/issue-mobile.png', fullPage: true })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'issue mobile has no horizontal overflow')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.screenshot({ path: 'output/playwright/issue-desktop-dark.png', fullPage: true })
  await page.emulateMedia({ colorScheme: 'light' })
  await page.setViewportSize({ width: 390, height: 844 })
  for (const [option, label] of [['符合学历要求','可能符合条件'], ['不符合学历要求','暂不符合条件'], ['尚不确定','信息不足，暂无法判断']]) {
    await page.goto(origin + '/jianwen/policy-check.html?key=pilot&v=20261025-3')
    await page.getByRole('button', { name: option, exact: true }).click()
    await page.getByRole('button', { name: '查看自查结果' }).click()
    await page.getByRole('heading', { name: label, exact: true }).waitFor()
    assert(evaluateBody.version === 'v1', 'evaluation binds rule version')
    assert(await page.getByRole('link', { name: /官方通知/ }).count() >= 1, 'result links official basis')
    const stored = await page.evaluate(() => JSON.stringify(localStorage))
    assert(!stored.includes('degree') && !stored.includes('answers'), 'answers never enter storage')
  }
  await page.screenshot({ path: 'output/playwright/policy-mobile.png', fullPage: true })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'policy mobile has no horizontal overflow')
  policy.questions.push({ id: 'residency', title: '居住条件是否符合？', options: [{ value: 'yes', label: '符合居住条件' }, { value: 'unknown', label: '居住情况待确认' }] })
  await page.goto(origin + '/jianwen/policy-check.html?key=pilot&v=20261025-3')
  await page.getByRole('button', { name: '符合学历要求', exact: true }).click()
  await page.getByRole('button', { name: '下一题', exact: true }).click()
  await page.getByRole('button', { name: '居住情况待确认', exact: true }).click()
  await page.getByRole('button', { name: '上一题', exact: true }).click()
  assert(await page.getByRole('button', { name: '✓ 符合学历要求', exact: true }).getAttribute('aria-pressed') === 'true', 'previous answer retained in page memory')
  await page.getByRole('button', { name: '下一题', exact: true }).click()
  await page.getByRole('button', { name: '查看自查结果', exact: true }).click()
  await page.getByRole('heading', { name: '可能符合条件', exact: true }).waitFor()
  assert(evaluateBody.answers.residency === 'unknown', 'multi-question answers reach the versioned evaluator')
  policy.questions.pop()
  for (const status of [409, 410]) {
    failure = status
    await page.goto(origin + '/jianwen/policy-check.html?key=pilot&v=20261025-3')
    await page.getByRole('button', { name: '符合学历要求', exact: true }).click()
    await page.getByRole('button', { name: '查看自查结果' }).click()
    await page.getByText(status === 409 ? '政策版本已更新，请重新加载后再自查。' : '政策已暂停或到期，请重新加载查看官方依据。', { exact: true }).waitFor()
    assert(await page.getByRole('button', { name: '查看自查结果' }).count() === 0, 'stale form removed')
  }
  failure = 0; policy.available = false; policy.unavailable_reason = '规则已暂停'
  await page.goto(origin + '/jianwen/policy-check.html?key=pilot&v=20261025-3')
  await page.getByRole('heading', { name: '暂不可自查' }).waitFor()
  assert(await page.getByRole('button', { name: '查看自查结果' }).count() === 0, 'paused policy has no evaluation')
  assert(errors.length === 0, errors.join('\n'))
  console.log('Issue/policy browser checks passed: login return, publication seen, anonymous three outcomes, official basis, version conflict and paused policy.')
}
