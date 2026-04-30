import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
// BACKEND_HOST can be overridden to point at a remote backend, e.g.:
//   BACKEND_HOST=192.168.1.42 pnpm dev

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  const backendHost = env.BACKEND_HOST ?? 'localhost'
  return {
    plugins: [react()],
    server: {
      // Dev-mode proxy: forwards /api and /ws to the local FastAPI backend.
      // Has no effect in production (Caddy handles routing there).
      proxy: {
        '/api': {
          target: `http://${backendHost}:8000`,
          changeOrigin: true,
        },
        '/ws': {
          target: `ws://${backendHost}:8000`,
          ws: true,
        },
      },
    },
  }
})
