import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    proxy: Object.fromEntries(['/api/', '/public/', '/uploads/', '/static/images/'].map(path => [path, {
      target: 'http://8.147.110.194',
      changeOrigin: true
    }]))
  }
})
