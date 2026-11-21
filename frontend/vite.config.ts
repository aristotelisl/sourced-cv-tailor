import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  server: {
    // The FastAPI backend (uvicorn backend.main:app) runs on :8000 (browser tests use another port).
    proxy: { '/api': `http://127.0.0.1:${process.env.CV_TAILOR_API_PORT ?? 8000}` },
  },
})
