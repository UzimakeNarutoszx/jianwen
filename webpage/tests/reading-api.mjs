import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const calls = []
const context = {
  window: {}, localStorage: { getItem: key => key === 'jianwen_auth_token' ? 'test-token' : null },
  AbortController, FormData, setTimeout, clearTimeout, URLSearchParams,
  fetch: async (url, options) => {
    calls.push({ url, options })
    return { ok: true, status: 200, headers: { get: () => 'application/json' }, json: async () => ({ chapter_id: 199, scroll_progress: 37 }) }
  }
}
vm.runInNewContext(await readFile(new URL('../js/api-browser.js', import.meta.url), 'utf8'), context)
const api = context.window.jianwenApi
const value = await api.readingProgress('communist-manifesto')
assert.equal(value.scroll_progress, 0.37)
assert.ok(calls[0].url.endsWith('/reading-positions/communist-manifesto'))
await api.saveReadingProgress('communist-manifesto', { chapter_id: 199, scroll_progress: 0.374 })
assert.deepEqual(JSON.parse(calls[1].options.body), { chapter_id: 199, scroll_progress: 37 })
assert.equal(calls[1].options.headers.Authorization, 'Bearer test-token')
console.log('Reading API: route, authentication, and fractional/percentage conversion passed.')
