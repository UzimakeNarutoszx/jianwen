// 播放前台服务：Android 上让朗读进程在锁屏/后台保持存活。
// H5/其他平台是空实现，避免引入原生模块。

// #ifdef APP-PLUS
import { startKeepAlive, updateKeepAlive, stopKeepAlive } from '@/uni_modules/jianwen-keepalive'
// #endif

export function startPlaybackService(title, text) {
  // #ifdef APP-PLUS
  try {
    startKeepAlive(title || '今日朗读', text || '见闻 · 正在播放')
  } catch (error) {}
  // #endif
}

export function updatePlaybackService(title, text) {
  // #ifdef APP-PLUS
  try {
    updateKeepAlive(title || '今日朗读', text || '见闻 · 正在播放')
  } catch (error) {}
  // #endif
}

export function stopPlaybackService() {
  // #ifdef APP-PLUS
  try {
    stopKeepAlive()
  } catch (error) {}
  // #endif
}
