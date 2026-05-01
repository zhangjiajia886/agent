import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const backendPort = process.env.BACKEND_PORT || '8000'
const frontendPort = parseInt(process.env.FRONTEND_PORT || '3000')

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    port: frontendPort,
    strictPort: false,
    proxy: {
      '/api': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true,
        ws: true
      },
      '/uploads': {
        target: `http://localhost:${backendPort}`,
        changeOrigin: true
      }
    }
  }
})
