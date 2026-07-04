import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Prerrequisito duro (phase-plan §6.1): sin este proxy, Vite:5173 y
    // Django:8000 son orígenes distintos y SameSite=Strict nunca entrega la
    // cookie sv_refresh en dev. Para que axios realmente pase por este proxy,
    // VITE_API_BASE_URL en .env.development debe ser el path relativo
    // /api/v1 (same-origin), no una URL absoluta a :8000.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
