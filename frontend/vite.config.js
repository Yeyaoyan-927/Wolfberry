import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发代理：/api、/files → 后端 8009（CORS 已在后端放开，双保险）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5176,
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8009', changeOrigin: true },
      '/files': { target: 'http://127.0.0.1:8009', changeOrigin: true },
    },
  },
})
