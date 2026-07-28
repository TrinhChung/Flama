import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const flaskOrigin = env.VITE_FLASK_ORIGIN || 'http://127.0.0.1:4789'

  return {
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
          target: flaskOrigin,
          changeOrigin: false,
        },
        '/media': {
          target: flaskOrigin,
          changeOrigin: false,
        },
        '/static': {
          target: flaskOrigin,
          changeOrigin: false,
        },
        '/support-donation': {
          target: flaskOrigin,
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
  }
})
