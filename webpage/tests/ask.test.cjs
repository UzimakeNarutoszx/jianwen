const assert = require('node:assert/strict')
const { markdown, consumeStream } = require('../js/ask.js')
const fs = require('node:fs')
const vm = require('node:vm')
const path = require('node:path')
const flush = () => new Promise(resolve => setImmediate(resolve))
function page(fetchImpl) {
  const elements = new Map()
  const el = id => { if (!elements.has(id)) elements.set(id, { value:'', textContent:'', innerHTML:'', handlers:{}, addEventListener(k,v) { this.handlers[k]=v }, setAttribute(){}, removeAttribute(){}, focus(){} }); return elements.get(id) }
  const context = { document:{ getElementById:el, querySelector:el }, window:{ getToken:()=> 'test-session', clearSession(){}, addEventListener(){}, jianwenApi:{ baseUrl:()=> 'http://localhost', askBootstrap:async()=> ({}) } }, location:{ search:'', pathname:'/ask.html' }, URLSearchParams, AbortController, DOMException, TextDecoder, setTimeout, clearTimeout, navigator:{ clipboard:{ writeText:async()=>{} } }, fetch:fetchImpl }
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../js/ask.js'),'utf8'), context)
  return { el, submit:() => el('ask-form').handlers.submit({ preventDefault(){} }) }
}
async function main() {
  const html = markdown('# 标题\n\n**重要** 和 `x < 1`\n- 第一\n- 第二\n1. 顺序\n> 引用\n```html\n<script>alert(1)</script>\n```\n<img src=x onerror=alert(1)>\n[危险](javascript:alert(1))')
  assert.match(html, /<h3>标题<\/h3>/)
  assert.match(html, /<strong>重要<\/strong>/)
  assert.match(html, /<ul><li>第一<\/li><li>第二<\/li><\/ul>/)
  assert.match(html, /<ol><li>顺序<\/li><\/ol>/)
  assert.match(html, /&lt;script&gt;/)
  assert.doesNotMatch(html, /<script|<img|<a /)
  const bytes = new TextEncoder().encode('中文流式回答。')
  const updates = []
  const response = new Response(new ReadableStream({ start(c) { for (const byte of bytes) c.enqueue(Uint8Array.of(byte)); c.close() } }))
  assert.equal(await consumeStream(response, text => updates.push(text)), '中文流式回答。')
  assert.ok(updates.length > 2)
  await assert.rejects(consumeStream(new Response(''), () => {}), /未返回有效回答/)
  const abort = new AbortController(); abort.abort()
  await assert.rejects(consumeStream(new Response('不会读取'), () => {}, abort.signal), { name: 'AbortError' })
  await assert.rejects(consumeStream(new Response(new ReadableStream({ start(c) { c.error(new Error('网络断开')) } })), () => {}), /网络断开/)
  let requests = 0, resolveRequest
  let ui = page(() => { requests++; return new Promise(resolve => { resolveRequest=resolve }) })
  ui.el('ask-input').value = '测试问题'
  ui.submit(); ui.submit()
  assert.equal(requests,1,'Duplicate submits are ignored')
  resolveRequest(new Response('**真实回答**'))
  await flush(); await flush()
  assert.match(ui.el('ask-output').innerHTML, /<strong>真实回答<\/strong>/)
  assert.equal(ui.el('ask-input').value,'测试问题')
  assert.equal(ui.el('ask-submit').disabled,false)
  ui = page(async()=> new Response(JSON.stringify({ detail:'额度不足' }),{status:429}))
  ui.el('ask-input').value='保留问题'; ui.submit()
  await flush(); await flush()
  assert.equal(ui.el('ask-input').value,'保留问题')
  assert.equal(ui.el('ask-retry').hidden,false)
  assert.match(ui.el('ask-status').textContent,/额度不足/)
  ui = page((_,options)=> new Promise((resolve,reject)=> options.signal.addEventListener('abort',()=> reject(new DOMException('Aborted','AbortError')))))
  ui.el('ask-input').value='等待问题'; ui.submit(); ui.el('ask-stop').handlers.click()
  await flush()
  assert.match(ui.el('ask-status').textContent,/已停止生成/)
  assert.equal(ui.el('ask-submit').disabled,false)
  console.log('Ask: safe Markdown, lists/code, split UTF-8 streaming, empty response, abort, network failure passed.')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
