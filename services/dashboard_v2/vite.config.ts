import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0', // Listen on all interfaces for WSL2 access
    port: 3000,
    strictPort: true,
    proxy: {
      // Proxy all backend API paths
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/semantic': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/control': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/goals': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/arbitration': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/llm': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/analytics': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/skills': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/artifacts': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/alerts': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
