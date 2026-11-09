const UPDATE_MANIFEST_URL = 'http://8.147.110.194/downloads/latest.json'
const DOWNLOAD_PREFIX = 'http://8.147.110.194/downloads/'
const UPDATE_CHECK_KEY = 'jianwen_update_checked_at'
const WGT_INSTALLED_KEY = 'jianwen_wgt_version_code'
const CHECK_INTERVAL = 6 * 60 * 60 * 1000

// 原生版本号：早期 plus.runtime 还没就绪时用它兜底，必须随每次整包发布同步提升。
const NATIVE_VERSION_CODE = 112

function versionCode(value) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
}

function nativeVersionCode() {
  try {
    const reported = versionCode(plus.runtime.versionCode)
    if (reported > 0) return reported
  } catch {}
  return NATIVE_VERSION_CODE
}

function installedWgtCode() {
  try { return versionCode(uni.getStorageSync(WGT_INSTALLED_KEY)) } catch { return 0 }
}

function shouldCheck() {
  try { return Date.now() - Number(uni.getStorageSync(UPDATE_CHECK_KEY) || 0) > CHECK_INTERVAL } catch { return true }
}

function markChecked() {
  try { uni.setStorageSync(UPDATE_CHECK_KEY, Date.now()) } catch {}
}

function requestManifest() {
  return new Promise((resolve, reject) => {
    uni.request({
      url: `${UPDATE_MANIFEST_URL}?t=${Date.now()}`,
      timeout: 8000,
      success: response => response.statusCode === 200 && response.data ? resolve(response.data) : reject(new Error('版本清单不可用')),
      fail: reject
    })
  })
}

function downloadWithProgress(url, onDownloaded) {
  // 带宽有限，整包要一分钟：必须让用户看到进度，而不是一个静止的「正在下载」。
  let lastPercent = -1
  let waiting = null
  try { waiting = plus.nativeUI.showWaiting('正在下载 0%', { modal: true }) } catch { uni.showLoading({ title: '正在下载', mask: true }) }
  const showPercent = percent => {
    if (percent === lastPercent) return
    lastPercent = percent
    if (waiting) waiting.setTitle(`正在下载 ${percent}%`)
  }
  showPercent(0)
  const task = uni.downloadFile({
    url,
    success: result => {
      if (result.statusCode !== 200 || !result.tempFilePath) {
        uni.showToast({ title: '下载失败，请稍后重试', icon: 'none' })
        return
      }
      onDownloaded(result.tempFilePath)
    },
    fail: () => uni.showToast({ title: '下载失败，请稍后重试', icon: 'none' }),
    complete: () => { if (waiting) waiting.close(); else uni.hideLoading() }
  })
  try {
    if (task && typeof task.onProgressUpdate === 'function') {
      task.onProgressUpdate(res => {
        const percent = res && res.progress > 0 ? Math.min(99, Math.round(res.progress)) : 0
        showPercent(percent)
      })
    }
  } catch {}
}

function installApk(url, versionName) {
  downloadWithProgress(url, tempFilePath => {
    // Android still asks the user to confirm installation. The download itself is automatic.
    plus.runtime.openFile(tempFilePath, {}, () => {
      uni.showToast({ title: `已下载 ${versionName || '新版本'}`, icon: 'none' })
    })
  })
}

function installWgt(url, versionCodeValue) {
  downloadWithProgress(url, tempFilePath => {
    // 资源包只有约 1 MB，装完自动重启生效，不需要用户再点一次安装。
    plus.runtime.install(tempFilePath, { force: false }, () => {
      try { uni.setStorageSync(WGT_INSTALLED_KEY, versionCodeValue) } catch {}
      plus.runtime.restart()
    }, () => {
      uni.showToast({ title: '资源包安装失败，请重试', icon: 'none' })
    })
  })
}

function isApprovedUrl(value) {
  return typeof value === 'string' && value.startsWith(DOWNLOAD_PREFIX)
}

export function checkForAppUpdate({ force = false, manual = false } = {}) {
  // #ifdef APP-PLUS
  if (!force && !shouldCheck()) return Promise.resolve({ status: 'skipped' })
  markChecked()
  return requestManifest().then(manifest => {
    const currentCode = nativeVersionCode()
    const latestCode = versionCode(manifest.versionCode)
    const wgtCode = versionCode(manifest.wgtVersionCode)
    const wgtBase = versionCode(manifest.wgtBaseVersionCode)
    const hasWgt = isApprovedUrl(manifest.wgtUrl) && wgtCode > 0

    if (latestCode > currentCode) {
      // 原生版本变了就必须走整包，资源包盖不住原生新能力。
      if (!isApprovedUrl(manifest.apkUrl)) {
        if (manual) uni.showToast({ title: '更新清单不可用', icon: 'none' })
        return { status: 'invalid' }
      }
      uni.showModal({
        title: `见闻 ${manifest.versionName || '有新版本'}`,
        content: manifest.notes || '发现新版本，是否立即下载？',
        confirmText: '下载更新',
        cancelText: '稍后再说',
        success: result => { if (result.confirm) installApk(manifest.apkUrl, manifest.versionName) }
      })
      return { status: 'update-available', versionCode: latestCode }
    }

    // 原生版本没变时只换网页资源，1 MB 量级，几秒装完。
    if (hasWgt && wgtBase === currentCode && wgtCode > installedWgtCode()) {
      uni.showModal({
        title: '见闻内容更新',
        content: manifest.wgtNotes || '有新的内容更新，安装后自动重启，约几秒。',
        confirmText: '立即更新',
        cancelText: '稍后再说',
        success: result => { if (result.confirm) installWgt(manifest.wgtUrl, wgtCode) }
      })
      return { status: 'wgt-available', versionCode: wgtCode }
    }

    if (manual) uni.showToast({ title: '当前已是最新版本', icon: 'none' })
    return { status: 'latest', versionCode: currentCode }
  }).catch(error => {
    if (manual) uni.showToast({ title: '检查更新失败，请稍后重试', icon: 'none' })
    return { status: 'error', error }
  })
  // #endif
}
