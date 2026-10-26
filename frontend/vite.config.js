import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发代理：/api → 后端 8000（CORS 已在后端放开，双保险）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    host: '127.0.0.1',
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/local-files': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
