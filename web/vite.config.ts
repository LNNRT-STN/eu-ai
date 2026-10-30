import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // maplibre-gl v6 loads its worker relative to its own module: pre-bundling would break that path
  optimizeDeps: { exclude: ['maplibre-gl'] },
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  // the FastAPI server (api/main.py) keeps the data, the shared scenario and the Claude key
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
