import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const source = (await readFile(new URL('../utils/app-updater.js', import.meta.url), 'utf8'))
  .replace('export function checkForAppUpdate', 'function checkForAppUpdate')

async function check(manifest, confirm = false) {
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
  vm.runInContext(`${source}\ncheckForAppUpdate()`, context)
  await new Promise(resolve => setImmediate(resolve))
  return calls
}

test('only newer releases from the approved HTTPS source are offered', async () => {
  const url = 'https://raw.githubusercontent.com/UzimakeNarutoszx/jianwen/main/apk/jianwen-1.0.3.apk'
  assert.equal((await check({ versionCode: 102, apkUrl: url })).modals.length, 0)
  assert.equal((await check({ versionCode: 103, apkUrl: 'http://example.com/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 103, apkUrl: url })).modals.length, 1)
  assert.equal((await check({ versionCode: 103, apkUrl: url })).downloads.length, 0)
  assert.deepEqual((await check({ versionCode: 103, apkUrl: url }, true)).downloads, [url])
})
