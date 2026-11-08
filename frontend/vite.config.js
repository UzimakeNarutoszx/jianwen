import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    proxy: Object.fromEntries(['/api/', '/public/', '/uploads/', '/static/images/'].map(path => [path, {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true
    }]))
  }
})
