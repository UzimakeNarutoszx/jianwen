import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import vm from 'node:vm'

const source = (await readFile(new URL('../utils/app-updater.js', import.meta.url), 'utf8'))
  .replace('export function checkForAppUpdate', 'function checkForAppUpdate')

// 与 utils/app-updater.js 的 NATIVE_VERSION_CODE 保持一致；这是 1.1.11 整包的原生版本。
const NATIVE = 121
const APK = 'http://8.147.110.194/downloads/jianwen-1.1.4.apk'
const WGT = 'http://8.147.110.194/downloads/jianwen-1.1.4.wgt'

async function check(manifest, confirm = false, options = {}) {
  const calls = { requests: [], modals: [], downloads: [], loading: [], waitingTitles: [], installed: [], restarted: 0, toasts: [] }
  const uni = {
    getStorageSync: key => (key === 'jianwen_wgt_version_code' ? (options.wgtInstalled || 0) : 0),
    setStorageSync: (key, value) => { if (key === 'jianwen_wgt_version_code') calls.installed.push(value) },
    request: options2 => { calls.requests.push(options2.url); options2.success({ statusCode: 200, data: manifest }) },
    showModal: options2 => { calls.modals.push(options2); options2.success({ confirm }) },
    showLoading: options2 => { calls.loading.push(options2 && options2.title) },
    hideLoading: () => {},
    showToast: options2 => { calls.toasts.push(options2 && options2.title) },
    downloadFile: options2 => {
      calls.downloads.push(options2.url)
      options2.success({ statusCode: 200, tempFilePath: '/tmp/pkg' })
      // 模拟 uni 的下载任务对象：进度回调必须是可调用的。
      return {
        onProgressUpdate: handler => {
          calls.onProgress = handler
          handler({ progress: 42 })
        }
      }
    }
  }
  const context = vm.createContext({
    uni,
    Date,
    Number,
    Promise,
    plus: {
      nativeUI: { showWaiting: title => { calls.loading.push(title); return { setTitle: title => calls.waitingTitles.push(title), close: () => {} } } },
      runtime: {
        openFile: () => {},
        // 安装器是异步的：成功回调必须真的被调用，否则测不到「装完自重启」。
        install: (path, options2, success) => { success() },
        restart: () => { calls.restarted += 1 }
      }
    }
  })
  vm.runInContext(`${source}\ncheckForAppUpdate()`, context)
  await new Promise(resolve => setImmediate(resolve))
  return calls
}

test('only newer native releases from the approved source are offered', async () => {
  // 同版本不提示，来源不对不提示，更高版本才提示。
  assert.equal((await check({ versionCode: NATIVE, apkUrl: APK })).modals.length, 0)
  assert.equal((await check({ versionCode: NATIVE + 1, apkUrl: 'https://example.com/app.apk' })).modals.length, 0)
  assert.equal((await check({ versionCode: NATIVE + 1, apkUrl: APK })).modals.length, 1)
  assert.equal((await check({ versionCode: NATIVE + 1, apkUrl: APK })).downloads.length, 0)
  assert.deepEqual((await check({ versionCode: NATIVE + 1, apkUrl: APK }, true)).downloads, [APK])
})

test('download shows progress instead of a frozen loading toast', async () => {
  const calls = await check({ versionCode: NATIVE + 1, apkUrl: APK, versionName: '1.1.3' }, true)
  assert.deepEqual(calls.downloads, [APK])
  assert.equal(calls.loading.length, 1, 'download should create only one loading indicator')
  assert.ok(calls.waitingTitles.some(title => /正在下载 42%/.test(String(title))), `titles: ${calls.waitingTitles}`)
})

test('a resource package is installed and rebooted without a native upgrade', async () => {
  const manifest = { versionCode: NATIVE, apkUrl: APK, wgtUrl: WGT, wgtVersionCode: 5, wgtBaseVersionCode: NATIVE }
  const calls = await check(manifest, true)
  // 原生版本没变：不走整包，只下资源包，装完自重启。
  assert.deepEqual(calls.downloads, [WGT])
  assert.deepEqual(calls.installed, [5])
  assert.equal(calls.restarted, 1)
})

test('resource package is skipped when already installed, for another build, or from elsewhere', async () => {
  const base = { versionCode: NATIVE, apkUrl: APK, wgtUrl: WGT, wgtVersionCode: 5, wgtBaseVersionCode: NATIVE }
  assert.equal((await check(base, true, { wgtInstalled: 5 })).downloads.length, 0)
  assert.equal((await check({ ...base, wgtBaseVersionCode: NATIVE - 1 }, true)).downloads.length, 0)
  assert.equal((await check({ ...base, wgtUrl: 'https://example.com/app.wgt' }, true)).downloads.length, 0)
})

test('a native upgrade wins over a pending resource package', async () => {
  const manifest = { versionCode: NATIVE + 1, apkUrl: APK, wgtUrl: WGT, wgtVersionCode: 9, wgtBaseVersionCode: NATIVE + 1 }
  const calls = await check(manifest, true)
  assert.deepEqual(calls.downloads, [APK])
  assert.equal(calls.restarted, 0)
})
