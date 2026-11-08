import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const source = (await readFile(new URL('../utils/app-updater.js', import.meta.url), 'utf8'))
  .replace('import.meta.env.VITE_UPDATE_MANIFEST_URL', "'https://updates.example.com/latest.json'")
  .replace('import.meta.env.VITE_UPDATE_APK_PREFIX', "'https://updates.example.com/apk/'")
  .replace('export function checkForAppUpdate', 'function checkForAppUpdate')

async function check(manifest, confirm = false, enabled = true) {
  const calls = { requests: [], modals: [], downloads: [] }
  const uni = {
    getStorageSync: () => 0,
    setStorageSync: () => {},
    request: options => { calls.requests.push(options.url); options.success({ statusCode: 200, data: manifest }) },
    showModal: options => { calls.modals.push(options); options.success({ confirm }) },
    showLoading: () => {},
    downloadFile: options => { calls.downloads.push(options.url) }
  }
  const context = vm.createContext({ uni, Date, Number, Promise })
  const configured = enabled ? source : source.replace("'https://updates.example.com/latest.json'", "''")
  vm.runInContext(`${configured}\ncheckForAppUpdate()`, context)
  await new Promise(resolve => setImmediate(resolve))
  return calls
}

test('only newer releases from the approved HTTPS source are offered', async () => {
  const url = 'https://updates.example.com/apk/jianwen-1.1.0.apk'
  assert.equal((await check({ versionCode: 110, apkUrl: url })).modals.length, 0)
  assert.equal((await check({ versionCode: 111, apkUrl: 'http://example.com/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 111, apkUrl: 'https://updates.example.com.evil.invalid/apk/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 111, apkUrl: url })).modals.length, 1)
  assert.equal((await check({ versionCode: 111, apkUrl: url })).downloads.length, 0)
  assert.deepEqual((await check({ versionCode: 111, apkUrl: url }, true)).downloads, [url])
  assert.equal((await check({ versionCode: 111, apkUrl: url }, true, false)).requests.length, 0)
})
