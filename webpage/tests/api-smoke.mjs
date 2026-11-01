import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const apiBase = (process.env.JIANWEN_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')
const webBase = (process.env.JIANWEN_WEB_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '')
const testToken = process.env.JIANWEN_TEST_TOKEN || ''
const webpageRoot = fileURLToPath(new URL('../', import.meta.url))

async function requestJson(url, options = {}) {
  const response = await fetch(url, options)
  assert.equal(response.ok, true, `${url} returned ${response.status}`)
  return response.json()
}

const today = await requestJson(`${apiBase}/api/v1/content/today`)
assert.equal(Array.isArray(today), true)
assert.equal(today.length, 5, 'today must return five articles')
assert.ok(today.every(article => article.article_id && article.title))

const quote = await requestJson(`${apiBase}/api/v1/content/daily-quote`)
assert.ok(quote.text, 'daily quote must contain text')

const article = await requestJson(`${apiBase}/api/v1/content/articles/${encodeURIComponent(today[0].article_id)}`)
assert.equal(article.article_id, today[0].article_id)
assert.equal(Array.isArray(article.sections), true)

const discover = await requestJson(`${apiBase}/api/v1/content/discover`)
assert.equal(Array.isArray(discover.topics), true)
assert.equal(Array.isArray(discover.updates), true)

const categories = await requestJson(`${apiBase}/api/v1/content/categories`)
assert.equal(Array.isArray(categories), true)

const classics = await requestJson(`${apiBase}/api/v1/content/classic-books`)
assert.equal(Array.isArray(classics), true)

for (const page of ['index.html', 'article.html', 'discover.html', 'ask.html', 'login.html', 'profile.html']) {
  const response = await fetch(`${webBase}/jianwen/${page}`)
  assert.equal(response.ok, true, `${page} returned ${response.status}`)
  const html = await response.text()
  for (const script of ['site.js', 'api-browser.js']) {
    const sources = [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"/g)].map(match => match[1])
    const source = sources.find(value => new URL(value, response.url).pathname.endsWith(`/js/${script}`))
    assert.ok(source, `${page} must load ${script}`)
    const resource = await fetch(new URL(source, response.url))
    assert.equal(resource.ok, true, `${page}: ${source} returned ${resource.status}`)
    assert.match(resource.headers.get('content-type') || '', /javascript/, `${source} must be JavaScript`)
  }
}

const loginHtml = await readFile(`${webpageRoot}/jianwen/login.html`, 'utf8')
const loginScript = await readFile(`${webpageRoot}/js/login.js`, 'utf8')
assert.doesNotMatch(loginHtml + loginScript, /jianwen_local_account|localSession|access_token:\s*`local-/)

const pageFiles = ['discover.html', 'profile.html']
for (const file of pageFiles) {
  const html = await readFile(`${webpageRoot}/jianwen/${file}`, 'utf8')
  assert.match(html, /api-browser\.js/)
  assert.doesNotMatch(html, /\.\.\/js\/api\.js/)
}

if (testToken) {
  const headers = { Authorization: `Bearer ${testToken}` }
  await requestJson(`${apiBase}/api/v1/profile/me`, { headers })
  await requestJson(`${apiBase}/api/v1/profile/favorites`, { headers })
  await requestJson(`${apiBase}/api/v1/profile/history`, { headers })
  await requestJson(`${apiBase}/api/v1/profile/ai-records`, { headers })
  await requestJson(`${apiBase}/api/v1/profile/topics`, { headers })
}

console.log(`Smoke test passed: 5 articles, quote, article, discover, categories, classics, and ${testToken ? 'protected' : 'public'} pages.`)
