import path from 'path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/vitest.setup.ts'],
    css: true,
    // Expose VITE_ env vars in the test environment so modules that read
    // import.meta.env.VITE_API_BASE_URL at module-load time get the expected
    // value instead of an empty string (Vitest does not load .env.development).
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1',
    },
  },
})
