const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')
const root = path.resolve(__dirname, '..')
const data = JSON.parse(fs.readFileSync(path.join(root, 'data/changelog.json'), 'utf8'))
const script = fs.readFileSync(path.join(root, 'js/changelog.js'), 'utf8')

class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.hidden = false; this.attrs = {} }
  append(...children) { this.children.push(...children) }
  replaceChildren(...children) { this.children = children }
  setAttribute(key, value) { this.attrs[key] = value }
  removeAttribute(key) { delete this.attrs[key] }
  addEventListener(name, callback) { this[name] = callback }
}
async function render(type, fail = false) {
  const nodes = Object.fromEntries(['entries', 'months', 'count', 'retry'].map(key => [key, new Node(key)]))
  const filters = ['all', 'web', 'app', 'ai'].map(id => Object.assign(new Node('a'), { dataset: { filter: id } }))
  let shouldFail = fail
  const context = {
    URLSearchParams, Map, location: { search: type ? `?type=${type}` : '', hash: '' },
    document: {
      querySelector: selector => nodes[selector.replace('[data-changelog-', '').replace(']', '')],
      querySelectorAll: () => filters,
      createElement: tag => new Node(tag), getElementById: () => null
    },
    fetch: async (url, options) => {
      assert.equal(url, 'data/changelog.json')
      assert.equal(options.cache, 'no-store')
      return { ok: !shouldFail, json: async () => data }
    }
  }
  vm.runInNewContext(script, context)
  await new Promise(resolve => setImmediate(resolve))
  return { nodes, filters, recover: () => { shouldFail = false } }
}

test('shared catalog preserves historical releases and validates current entries', () => {
  const historicalEntries = data.entries.filter(entry => entry.date < '2026-10-17')
  assert.equal(new Set(data.entries.map(entry => entry.date)).size, data.entries.length)
  assert.deepEqual(data.entries.map(entry => entry.date), [...data.entries.map(entry => entry.date)].sort().reverse())
  assert.deepEqual(historicalEntries.map(entry => entry.date), ['2026-10-11', '2026-10-02', '2026-09-26', '2026-09-19'])
  assert.equal(historicalEntries.flatMap(entry => entry.groups.flatMap(group => group.items)).length, 27)
  for (const entry of data.entries) {
    assert.ok(entry.title)
    assert.deepEqual(entry.groups.map(group => group.title), ['新功能', '改进与修复'])
    for (const item of entry.groups.flatMap(group => group.items)) {
      assert.ok(item.text)
      assert.ok(item.types.length)
      assert.ok(item.types.every(type => ['web', 'app', 'ai'].includes(type)))
    }
  }
})
test('website renders shared data with all filters, counts and month anchors', async () => {
  for (const type of ['all', 'web', 'app', 'ai', 'invalid']) {
    const { nodes, filters } = await render(type)
    const active = ['web', 'app', 'ai'].includes(type) ? type : 'all'
    const expectedItems = data.entries.flatMap(entry => entry.groups.flatMap(group => group.items)).filter(item => active === 'all' || item.types.includes(active))
    assert.ok(nodes.count.textContent.includes(`${expectedItems.length} 条更新`))
    assert.equal(filters.find(filter => filter.attrs['aria-current']).dataset.filter, active)
    assert.deepEqual(nodes.months.children.map(link => link.href), ['#month-2026-11', '#month-2026-10', '#month-2026-09'])
    const articles = nodes.entries.children.flatMap(section => section.children[1].children)
    const items = articles.flatMap(article => article.children[1].children.filter(node => node.tag === 'ul').flatMap(node => node.children))
    assert.equal(items.length, expectedItems.length)
    assert.deepEqual(items.map(item => item.textContent), expectedItems.map(item => item.text))
  }
})
test('website exposes retry after failed fetch and recovers', async () => {
  const { nodes, recover } = await render('', true)
  assert.equal(nodes.retry.hidden, false)
  assert.match(nodes.count.textContent, /失败/)
  assert.equal(typeof nodes.retry.click, 'function')
  recover()
  await nodes.retry.click()
  assert.equal(nodes.retry.hidden, true)
  assert.equal(nodes.count.textContent, `共 ${data.entries.flatMap(entry => entry.groups.flatMap(group => group.items)).length} 条更新`)
})

test('catalog renderer uses a fresh asset URL after the static-to-dynamic migration', () => {
  const html = fs.readFileSync(path.join(root, 'changelog.html'), 'utf8')
  assert.match(html, /js\/changelog\.js\?v=20261017-5/)
})
