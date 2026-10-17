import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
const source = await readFile(new URL('../utils/reading-activity-core.js', import.meta.url), 'utf8')
const { createReadingCollector } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
function fixture(transport) {
  let time = Date.parse('2026-10-17T10:00:00Z'), user = { owner: 1, token: 'one' }, serial = 0
  const storage = new Map(), sent = []
  const collector = createReadingCollector({ now: () => time, identity: () => user,
    read: key => structuredClone(storage.get(key)), write: (key, value) => storage.set(key, structuredClone(value)),
    uuid: () => `batch-${++serial}`, send: async (item, token) => { sent.push({ item: structuredClone(item), token }); if (transport) await transport(item, token) } })
  const advance = seconds => { for (let i = 0; i < seconds; i++) { time += 1000; collector.sample() } }
  const start = () => { collector.resume(); collector.setTarget({ kind: 'article', content_id: 'a', scroll_progress: 0 }) }
  return { collector, storage, sent, advance, start, setUser: next => { user = next }, jump: ms => { time += ms }, time: () => time }
}
const total = f => f.sent.reduce((sum, { item }) => sum + Date.parse(item.ended_at) - Date.parse(item.started_at), 0) / 1000

test('switching account, refreshing token and logout preserve sealed time under its owner', async () => {
  for (const next of [{ owner: 2, token: 'two' }, { owner: 1, token: 'refreshed' }, {}]) {
    const f = fixture(); f.start(); f.advance(10); f.setUser(next); f.collector.sample()
    const saved = f.storage.get('jianwen_reading_queue_1')
    assert.equal(saved.length, 1)
    assert.equal(Date.parse(saved[0].ended_at) - Date.parse(saved[0].started_at), 10000)
    assert.equal(saved[0].batch_id, 'batch-1')
  }
})

test('foreground samples split into valid <=15 second batches; idle pauses at 60s', async () => {
  const f = fixture(); f.start(); f.advance(80); await f.collector.flush()
  assert.equal(total(f), 60)
  assert.equal(new Set(f.sent.map(x => x.item.batch_id)).size, f.sent.length)
  for (const { item } of f.sent) assert.ok(Date.parse(item.ended_at) - Date.parse(item.started_at) <= 15000)
  f.collector.interact(); f.advance(3); await f.collector.flush(); assert.equal(total(f), 63)
})
test('page/background pause and stalled timers never create background duration', async () => {
  const f = fixture(); f.start(); f.advance(3); f.collector.pause(); f.advance(30)
  await f.collector.flush(); assert.equal(total(f), 3)
  f.collector.resume(); f.jump(45000); f.collector.sample(); f.advance(2)
  await f.collector.flush(); assert.equal(total(f), 5)
})
test('switching chapter closes preceding target and keeps chapter/book/progress', async () => {
  const f = fixture(); f.start(); f.advance(3)
  f.collector.setTarget({ kind: 'classic', content_id: '4', book_id: 'b', scroll_progress: 20 })
  f.advance(4); f.collector.progress(60); f.advance(1); await f.collector.flush()
  assert.equal(total(f), 8)
  assert.equal(f.sent[0].item.kind, 'article'); assert.equal(f.sent[1].item.book_id, 'b')
  assert.equal(f.sent[1].item.scroll_progress, 60)
})
test('network retries preserve batch IDs and uploaded tokens', async () => {
  let failed = true
  const f = fixture(() => { if (failed) throw new Error('offline') }); f.start(); f.advance(4)
  await f.collector.flush(); const id = f.sent[0].item.batch_id
  assert.equal(f.storage.get('jianwen_reading_queue_1').length, 1)
  failed = false; await f.collector.upload()
  assert.equal(f.sent[1].item.batch_id, id); assert.equal(f.storage.get('jianwen_reading_queue_1').length, 0)
})
test('account switch during upload never shifts another account queue', async () => {
  let release
  const f = fixture(() => new Promise(resolve => { release = resolve })); f.start(); f.advance(4)
  const uploading = f.collector.flush(); f.setUser({ owner: 2, token: 'two' }); f.collector.sample()
  release(); await uploading
  assert.equal(f.sent[0].token, 'one')
  assert.equal(f.storage.get('jianwen_reading_queue_1').length, 1)
  assert.equal(f.storage.has('jianwen_reading_queue_2'), false)
})
test('guests do not collect; bad payloads discarded; auth failure stops collection', async () => {
  const f = fixture(() => { const e = new Error('expired'); e.status = 401; throw e })
  f.setUser({}); f.start(); f.advance(8); await f.collector.flush(); assert.equal(f.sent.length, 0)
  f.setUser({ owner: 1, token: 'one' }); f.collector.resume(); f.advance(3); await f.collector.flush()
  const count = f.sent.length; f.advance(10); await f.collector.flush(); assert.equal(f.sent.length, count)
  const g = fixture(() => { const e = new Error('deleted'); e.status = 404; throw e })
  g.start(); g.advance(3); await g.collector.flush(); assert.equal(g.storage.get('jianwen_reading_queue_1').length, 0)
})
