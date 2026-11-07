const UPDATE_MANIFEST_URL = 'https://raw.githubusercontent.com/UzimakeNarutoszx/jianwen/main/webpage/downloads/latest.json'
const UPDATE_CHECK_KEY = 'jianwen_update_checked_at'
const CHECK_INTERVAL = 6 * 60 * 60 * 1000

function versionCode(value) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
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

function downloadAndOpen(url, versionName) {
  uni.showLoading({ title: '正在下载更新', mask: true })
  uni.downloadFile({
    url,
    success: result => {
      if (result.statusCode !== 200 || !result.tempFilePath) {
        uni.showToast({ title: '下载失败，请稍后重试', icon: 'none' })
        return
      }
      // Android still asks the user to confirm installation. The download itself is automatic.
      plus.runtime.openFile(result.tempFilePath, {}, () => {
        uni.showToast({ title: `已下载 ${versionName || '新版本'}`, icon: 'none' })
      })
    },
    fail: () => uni.showToast({ title: '下载失败，请稍后重试', icon: 'none' }),
    complete: () => uni.hideLoading()
  })
}

export function checkForAppUpdate({ force = false } = {}) {
  // #ifdef APP-PLUS
  if (!force && !shouldCheck()) return
  markChecked()
  requestManifest().then(manifest => {
    const currentCode = versionCode('102')
    const latestCode = versionCode(manifest.versionCode)
    if (typeof manifest.apkUrl !== 'string' || !manifest.apkUrl.startsWith('https://raw.githubusercontent.com/UzimakeNarutoszx/jianwen/main/apk/') || latestCode <= currentCode) return
    uni.showModal({
      title: `见闻 ${manifest.versionName || '有新版本'}`,
      content: manifest.notes || '发现新版本，是否立即下载？',
      confirmText: '下载更新',
      cancelText: '稍后再说',
      success: result => { if (result.confirm) downloadAndOpen(manifest.apkUrl, manifest.versionName) }
    })
  }).catch(() => {})
  // #endif
}
