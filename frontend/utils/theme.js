export function isDarkMode() {
  return !!uni.getStorageSync('jianwen_dark_mode')
}

export function applyTabBarTheme(darkMode = isDarkMode()) {
  if (typeof uni.setTabBarStyle !== 'function') {
    return
  }

  // 非 tabBar 页面（分类、搜索、收藏等）调用会失败，静默忽略即可
  uni.setTabBarStyle({
    color: darkMode ? '#8FA2B2' : '#8A949E',
    selectedColor: darkMode ? '#7EB8D1' : '#1F5F7A',
    backgroundColor: darkMode ? '#101820' : '#FFFFFF',
    borderStyle: darkMode ? 'black' : 'white',
    fail() {}
  })
}
