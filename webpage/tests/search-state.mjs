import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

// Exercise the actual page script with controlled response ordering.
const html = await readFile(new URL('../jianwen/search.html', import.meta.url), 'utf8')
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1]
const nodes = new Map()
function node(selector) {
  if (!nodes.has(selector)) nodes.set(selector, {
    value: '', innerHTML: '', textContent: '', hidden: true, handlers: {},
    querySelectorAll: () => [],
    addEventListener(event, handler) { this.handlers[event] = handler }
  })
  return nodes.get(selector)
}
const pending = []
vm.runInNewContext(script, {
  document: { querySelector: node }, location: { search: '' }, URLSearchParams,
  window: { jianwenApi: {
    categories: async () => [],
    articles: () => new Promise((resolve, reject) => pending.push({ resolve, reject }))
  } }
})
const flush = () => new Promise(resolve => setImmediate(resolve))
const submit = query => {
  node('#query').value = query
  node('#search-form').handlers.submit({ preventDefault() {} })
}
const clear = () => node('#clear-search').handlers.click()
const article = title => [{ article_id: title, title }]

submit('first')
pending[0].resolve(article('first'))
await flush()
assert.equal(node('#clear-search').hidden, false)
submit('slow')
clear()
pending[1].resolve(article('stale'))
await flush()
assert.equal(node('#result-count').textContent, '等待搜索', 'clearing must invalidate pending results')
assert.doesNotMatch(node('#results').innerHTML, /stale/)

submit('older')
submit('newer')
pending[3].resolve(article('newest'))
await flush()
pending[2].resolve(article('outdated'))
await flush()
assert.match(node('#results').innerHTML, /newest/)
assert.doesNotMatch(node('#results').innerHTML, /outdated/)

submit('old error')
submit('latest')
pending[5].resolve(article('latest result'))
await flush()
pending[4].reject(new Error('stale failure'))
await flush()
assert.match(node('#results').innerHTML, /latest result/)
assert.doesNotMatch(node('#results').innerHTML, /stale failure/)
console.log('Search state passed: clear, out-of-order responses, and stale failures.')
