import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  // Other HTML entries are built with their dedicated configs.
  optimizeDeps: { entries: ['index.html'] },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
      '/auth': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
      '/media': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
      '^/store': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
      '/static': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
      '/support-donation': {
        target: 'http://127.0.0.1:4789',
        changeOrigin: false,
      },
    },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
  },
  build: {
    sourcemap: true,
  },
})
