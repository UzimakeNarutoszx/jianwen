import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const source = (await readFile(new URL('../utils/app-updater.js', import.meta.url), 'utf8'))
  .replace('import.meta.env.VITE_UPDATE_MANIFEST_URL', "'https://updates.example.com/latest.json'")
  .replace('import.meta.env.VITE_UPDATE_APK_PREFIX', "'https://updates.example.com/apk/'")
  .replace('export function checkForAppUpdate', 'function checkForAppUpdate')

async function check(manifest, confirm = false, enabled = true) {
  const calls = { requests: [], modals: [], downloads: [], loading: [] }
  const uni = {
    getStorageSync: () => 0,
    setStorageSync: () => {},
    request: options => { calls.requests.push(options.url); options.success({ statusCode: 200, data: manifest }) },
    showModal: options => { calls.modals.push(options); options.success({ confirm }) },
    showLoading: options => { calls.loading.push(options && options.title) },
    downloadFile: options => {
      calls.downloads.push(options.url)
      // 模拟 uni 的下载任务对象：进度回调必须是可调用的。
      return {
        onProgressUpdate: handler => {
          calls.onProgress = handler
          handler({ progress: 42 })
        }
      }
    }
  }
  const context = vm.createContext({ uni, Date, Number, Promise })
  const configured = enabled ? source : source.replace("'https://updates.example.com/latest.json'", "''")
  vm.runInContext(`${configured}\ncheckForAppUpdate()`, context)
  await new Promise(resolve => setImmediate(resolve))
  return calls
}

test('only newer releases from the approved HTTPS source are offered', async () => {
  const url = 'https://updates.example.com/apk/jianwen-1.1.1.apk'
  assert.equal((await check({ versionCode: 111, apkUrl: url })).modals.length, 0)
  assert.equal((await check({ versionCode: 111, apkUrl: 'http://example.com/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 111, apkUrl: 'https://updates.example.com.evil.invalid/apk/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 112, apkUrl: url })).modals.length, 1)
  assert.equal((await check({ versionCode: 112, apkUrl: url })).downloads.length, 0)
  assert.deepEqual((await check({ versionCode: 112, apkUrl: url }, true)).downloads, [url])
  assert.equal((await check({ versionCode: 112, apkUrl: url }, true, false)).requests.length, 0)
})

test('download shows progress instead of a frozen loading toast', async () => {
  const url = 'https://updates.example.com/apk/jianwen-1.1.1.apk'
  const calls = await check({ versionCode: 112, apkUrl: url, versionName: '1.1.2' }, true)
  assert.deepEqual(calls.downloads, [url])
  assert.ok(calls.loading.some(title => /正在下载 42%/.test(String(title))), `loading: ${calls.loading}`)
})
