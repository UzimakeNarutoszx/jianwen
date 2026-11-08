import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const source = (await readFile(new URL('../utils/app-updater.js', import.meta.url), 'utf8'))
  .replace('export function checkForAppUpdate', 'function checkForAppUpdate')

async function check(manifest, confirm = false) {
  const calls = { requests: [], modals: [], downloads: [], loading: [] }
  const uni = {
    getStorageSync: () => 0,
    setStorageSync: () => {},
    request: options => { calls.requests.push(options.url); options.success({ statusCode: 200, data: manifest }) },
    showModal: options => { calls.modals.push(options); options.success({ confirm }) },
    showLoading: options => { calls.loading.push(options && options.title) },
    hideLoading: () => {},
    showToast: () => {},
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
  vm.runInContext(`${source}\ncheckForAppUpdate()`, context)
  await new Promise(resolve => setImmediate(resolve))
  return calls
}

test('only newer releases from the approved HTTPS source are offered', async () => {
  const url = 'http://8.147.110.194/downloads/jianwen-1.1.1.apk'
  // 当前安装的是 111：同版本不提示，来源不对不提示，更高版本才提示。
  assert.equal((await check({ versionCode: 111, apkUrl: url })).modals.length, 0)
  assert.equal((await check({ versionCode: 112, apkUrl: 'https://example.com/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: 112, apkUrl: url })).modals.length, 1)
  assert.equal((await check({ versionCode: 112, apkUrl: url })).downloads.length, 0)
  assert.deepEqual((await check({ versionCode: 112, apkUrl: url }, true)).downloads, [url])
})

test('download shows progress instead of a frozen loading toast', async () => {
  const url = 'http://8.147.110.194/downloads/jianwen-1.1.1.apk'
  const calls = await check({ versionCode: 112, apkUrl: url, versionName: '1.1.2' }, true)
  assert.deepEqual(calls.downloads, [url])
  assert.ok(calls.loading.some(title => /正在下载 42%/.test(String(title))), `loading: ${calls.loading}`)
})
