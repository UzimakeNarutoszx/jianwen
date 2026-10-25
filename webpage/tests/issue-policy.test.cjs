const test = require('node:test')
const assert = require('node:assert/strict')
const { esc, safeUrl, unavailable, issueCard } = require('../js/issue-policy.js')
test('published issue cards escape titles, summaries and query keys', () => {
  const html = issueCard({ issue_key: 'a&evil=x', title: '<img onerror=alert(1)>', stage: '发布', status_line: '<script>x</script>', event_count: 2 })
  assert(!html.includes('<script>'))
  assert(!html.includes('<img'))
  assert(html.includes('key=a%26evil%3Dx'))
  assert.equal(esc('"&'), '&quot;&amp;')
})
test('official links reject executable URLs', () => {
  for (const value of ['javascript:alert(1)', 'data:text/html,a', '/redirect', '//evil.example']) assert.equal(safeUrl(value), '')
  assert.equal(safeUrl('https://www.gov.cn/a'), 'https://www.gov.cn/a')
})
test('paused policies and expired review windows cannot be evaluated', () => {
  assert(unavailable({ available: false }))
  assert(unavailable({ available: true, review_expires_at: '2000-01-01' }))
  assert(!unavailable({ available: true, review_expires_at: '2099-01-01' }))
})
