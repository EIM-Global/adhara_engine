import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const apiBackend = process.env.API_BACKEND || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: process.env.HOST || 'localhost',
    port: parseInt(process.env.PORT || '5173'),
    proxy: {
      '/api': apiBackend,
      '/health': apiBackend,
    },
  },
})
