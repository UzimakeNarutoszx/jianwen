import { getAuthToken, postReadingActivity } from './api.js'
import { createReadingCollector } from './reading-activity-core.js'

export const readingActivity = createReadingCollector({
  identity: () => ({ token: getAuthToken(), owner: uni.getStorageSync('jianwen_auth_user')?.id }),
  read: key => uni.getStorageSync(key),
  write: (key, value) => { try { uni.setStorageSync(key, value) } catch {} },
  send: postReadingActivity
})

let installed = false
export function installReadingActivity() {
  if (installed) return
  installed = true
  setInterval(() => readingActivity.sample(), 1000)
  setInterval(() => readingActivity.flush(), 15000)
  // #ifdef H5
  const active = () => !document.hidden && document.hasFocus()
  const visibility = () => active() ? readingActivity.resume() : readingActivity.pause()
  for (const event of ['pointerdown', 'pointermove', 'scroll', 'touchstart', 'keydown']) {
    window.addEventListener(event, () => readingActivity.interact(), { passive: true })
  }
  window.addEventListener('blur', visibility)
  window.addEventListener('focus', visibility)
  window.addEventListener('pagehide', () => readingActivity.pause())
  window.addEventListener('pageshow', visibility)
  document.addEventListener('visibilitychange', visibility)
  // #endif
}

export function resumeReadingActivity() {
  // #ifdef H5
  if (document.hidden || !document.hasFocus()) return
  // #endif
  readingActivity.resume()
}
