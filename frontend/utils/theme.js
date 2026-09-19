export function isDarkMode() {
  return !!uni.getStorageSync('jianwen_dark_mode')
}

export function applyTabBarTheme(darkMode = isDarkMode()) {
  if (typeof uni.setTabBarStyle !== 'function') {
    return
  }

  uni.setTabBarStyle({
    color: darkMode ? '#8FA2B2' : '#8A949E',
    selectedColor: darkMode ? '#7EB8D1' : '#1F5F7A',
    backgroundColor: darkMode ? '#101820' : '#FFFFFF',
    borderStyle: darkMode ? 'black' : 'white'
  })
}
