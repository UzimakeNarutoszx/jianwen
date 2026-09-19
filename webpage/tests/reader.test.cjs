// Run: node webpage/tests/reader.test.cjs
const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')
const source = fs.readFileSync(path.join(__dirname, '../js/reader.js'), 'utf8')
const flush = () => new Promise(resolve => setImmediate(resolve))
class Element {
  constructor() { this.children = []; this.attributes = {}; this.listeners = {}; this.value = ''; this.style = { setProperty() {} }; this.offsetHeight = 1500; this.textContent = '' }
  setAttribute(k, v) { this.attributes[k] = v }
  addEventListener(k, callback) { this.listeners[k] = callback }
  append(...children) { for (const child of children) this.children.push(...(child.fragment ? child.children : [child])) }
  replaceChildren(...children) { this.children = []; this.append(...children) }
  get childNodes() { return this.children }
  getBoundingClientRect() { return { top: 200 } }
  focus() {}
  click() { this.listeners.click?.() }
}
function setup({ search = '?book=one', chapter = async (_, id) => ({ id, content: '第一段\n第二段' }), saved = null, accountApi = null } = {}) {
  const elements = new Map()
  const storage = new Map(saved ? [['jianwen_web_reader_one', JSON.stringify(saved)]] : [])
  const classes = new Set()
  const document = { getElementById(id) { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id) }, createElement() { return new Element() }, createDocumentFragment() { const e = new Element(); e.fragment = true; return e }, documentElement: new Element(), addEventListener() {}, body: { classList: { contains: c => classes.has(c), remove: c => classes.delete(c), toggle(c) { if (classes.has(c)) { classes.delete(c); return false } classes.add(c); return true } } } }
  const window = { jianwenApi: { classicBook: async () => ({ title: '测试经典', chapters: [{ id: 1, title: '第一章' }, { id: 2, title: '第二章' }] }), classicChapter: chapter }, innerHeight: 800, scrollY: 0, scrollTo({ top }) { this.scrollY = top }, addEventListener() {} }
  if (accountApi) { Object.assign(window.jianwenApi, accountApi); window.getToken = () => 'test-session' }
  const localStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) }
  vm.runInNewContext(source, { window, document, localStorage, location: { search, href: `http://localhost/reader.html${search}` }, history: { replaceState() {} }, URL, URLSearchParams, setTimeout, clearTimeout, requestAnimationFrame: callback => callback() })
  return { el: id => document.getElementById(id), storage, classes }
}
async function run() {
  let r = setup({ chapter: async () => ({ content: '<script>alert(1)</script>\n正文' }) })
  await flush()
  assert.equal(r.el('reader-content').children[0].textContent, '<script>alert(1)</script>', 'Content is rendered as text')
  assert.equal(r.el('previous-chapter').disabled, true)
  assert.equal(r.el('next-chapter').disabled, false)
  assert.equal(JSON.parse(r.storage.get('jianwen_web_reader_one')).chapterId, 1)
  for (let i = 0; i < 10; i++) r.el('font-larger').click()
  assert.equal(r.el('font-value').textContent, '28 px')
  r.el('focus-toggle').click()
  assert.equal(r.classes.has('is-focused'), true)
  r.el('toc-toggle').click()
  assert.equal(r.classes.has('is-focused'), false)
  r = setup({ saved: { chapterId: 2, fraction: .5 } })
  await flush()
  assert.equal(r.el('chapter-title').textContent, '第二章', 'Per-book resume restores chapter')
  assert.equal(r.el('next-chapter').disabled, true)
  let firstResolve
  r = setup({ chapter: (_, id) => id === 1 ? new Promise(resolve => { firstResolve = resolve }) : Promise.resolve({ content: '新的第二章' }) })
  await flush()
  r.el('next-chapter').click()
  await flush()
  firstResolve({ content: '旧的第一章' })
  await flush()
  assert.equal(r.el('reader-content').children[0].textContent, '新的第二章', 'Stale requests cannot replace current chapter')
  r = setup({ chapter: async () => { throw new Error('测试断网') } })
  await flush()
  assert.match(r.el('reader-content').children[0].textContent, /测试断网/)
  assert.equal(r.el('reader-content').children[1].textContent, '重新加载')
  assert.equal(r.storage.has('jianwen_web_reader_one'), false, 'Failed chapters do not overwrite progress')
  r = setup({ chapter: async () => ({ content: null, external_url: 'javascript:alert(1)' }) })
  await flush()
  assert.match(r.el('reader-content').children[0].textContent, /暂无完整正文/)
  assert.equal(r.el('reader-content').children.length, 1, 'Unsafe source links are omitted')
  r = setup({ search: '' })
  await flush()
  assert.equal(r.el('chapter-title').textContent, '还没有选择书籍')
  const writes = []
  r = setup({ saved: { chapterId: 1, updatedAt: 1 }, accountApi: { readingProgress: async () => ({ chapter_id: 2, scroll_progress: .25, updated_at: '2050-01-01T00:00:00' }), saveReadingProgress: async (id, payload) => writes.push({ id, payload }) } })
  await flush()
  assert.equal(r.el('chapter-title').textContent, '第二章', 'Newer account progress wins over local progress')
  await new Promise(resolve => setTimeout(resolve, 1300))
  assert.equal(writes[0].id, 'one')
  assert.equal(writes[0].payload.chapter_id, 2)
  assert.equal(r.el('save-state').textContent, '阅读位置已同步至账号')
  console.log('Reader: safe text, navigation boundaries, per-book resume, font limits, focus, stale responses, retry, no text, unsafe URL and missing book checks passed.')
}
run().catch(error => { console.error(error); process.exitCode = 1 })
