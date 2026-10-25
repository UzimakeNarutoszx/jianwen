// Serve dist/build/h5 at 4174; run with playwright-cli run-code --filename.
async (page) => {
  const assert = (condition, message) => { if (!condition) throw new Error(message) }
  const origin = 'http://127.0.0.1:4174'
  page.setDefaultTimeout(12000)
  const errors = []; page.on('pageerror', error => errors.push(error.message))
  const brief = { issue_key: 'housing', title: '住房保障进展', stage: 'implementing', status_line: '申请细则已明确', event_count: 1, published_version: 4 }
  const detail = { ...brief, is_following: true, last_seen_version: 1, events: [{ event_id: 2, event_date: '2026-10-24', position: 1, delta_summary: '已修订的申请材料说明', updated_version: 4, article_id: 'a1', references: [] }], policy_checks: [] }
  const policy = { policy_key: 'pilot', title: '毕业生补贴自查', region: '杭州', version: 'v1', status: 'published', available: true, summary: '逐题核对条件', verified_at: '2026-10-24', review_expires_at: '2099-01-01', questions: [{ id: 'degree', title: '学历是否符合？', help: '按证书选择', options: [{ value: 'yes', label: '符合学历要求' }, { value: 'unknown', label: '尚不确定' }] }], sources: [{ id: 's1', title: '官方通知', org: '杭州市政府', url: 'https://www.hangzhou.gov.cn/' }], materials: ['毕业证明'], application_url: 'https://www.hangzhou.gov.cn/' }
  let seen = null, evaluation = null, failure = 0
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname
    let data = []
    if (path.endsWith('/content/issues/housing')) data = detail
    else if (path.endsWith('/content/issues')) data = [brief]
    else if (path.endsWith('/housing/seen')) { seen = route.request().postDataJSON(); data = { last_seen_version: seen.published_version } }
    else if (path.endsWith('/housing/follow')) data = { is_following: route.request().method() === 'POST' }
    else if (path.endsWith('/policy-checks/pilot/evaluate')) {
      evaluation = route.request().postDataJSON()
      if (failure) return route.fulfill({ status: failure, json: { detail: '规则版本变化' } })
      data = { ...policy, result: 'insufficient_information', title: '请进一步核对', checks: [{ question_id: 'degree', title: '学历', status: 'unknown', reason: '需核对证书', source_id: 's1' }], next_steps: ['核对官方条件'] }
    } else if (path.endsWith('/policy-checks/pilot')) data = policy
    else if (path.endsWith('/policy-checks')) data = [policy]
    else if (path.endsWith('/ask/bootstrap')) data = { prompts: [], followups: [] }
    return route.fulfill({ json: data })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(origin + '/#/pages/issues/index')
  await page.evaluate(() => { localStorage.removeItem('jianwen_ask_session'); localStorage.removeItem('jianwen_pending_ask_context') })
  await page.reload()
  await page.getByText('住房保障进展', { exact: true }).waitFor()
  await page.evaluate(() => { localStorage.setItem('jianwen_auth_token', 'ui-mock-token'); localStorage.setItem('jianwen_login_expires_at', String(Date.now() + 600000)) })
  await page.getByText('查看时间线', { exact: true }).click()
  await page.getByText('标记当前进展已读', { exact: true }).click()
  await page.getByText('当前进展已读；后续发布仍会提醒。', { exact: true }).waitFor()
  assert(seen.published_version === 4, 'Uni seen uses publication version')
  await page.screenshot({ path: 'output/playwright/uni-issue-mobile.png', fullPage: true })
  await page.goto(origin + '/#/pages/policy/detail?key=pilot')
  await page.getByText('尚不确定', { exact: true }).click()
  await page.getByText('查看自查结果', { exact: true }).click()
  await page.getByText('信息不足，暂无法判断', { exact: true }).waitFor()
  assert(evaluation.version === 'v1' && evaluation.answers.degree === 'unknown', 'versioned anonymous evaluation')
  const stored = await page.evaluate(() => JSON.stringify(localStorage))
  assert(!stored.includes('degree') && !stored.includes('answers'), 'Uni answers stay in page memory')
  await page.screenshot({ path: 'output/playwright/uni-policy-mobile.png', fullPage: true })
  await page.getByText('问问这项政策', { exact: true }).click()
  await page.getByText('正在围绕「毕业生补贴自查」问问，仅带入公开内容。', { exact: true }).waitFor()
  assert(!(await page.evaluate(() => JSON.stringify(localStorage))).includes('degree'), 'policy answers do not reach ask context')
  for (const status of [409, 410]) {
    failure = status
    await page.goto(origin + '/#/pages/policy/detail?key=pilot')
    await page.reload()
    await page.getByText('符合学历要求', { exact: true }).click()
    await page.getByText('查看自查结果', { exact: true }).click()
    await page.getByText(status === 409 ? '政策版本已更新，请重新加载后再自查。' : '政策已暂停或到期，请重新加载查看官方依据。', { exact: true }).waitFor()
  }
  assert(!errors.length, errors.join('\n'))
  console.log('Uni issue/policy checks passed: routes, publication seen, anonymous evaluation, safe ask handoff, 409/410 invalidation.')
}
