import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// バックエンド (FastAPI) へのプロキシ先。ランチャーから起動するときは VITE_PROXY_TARGET で渡される
const target = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8050'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5189,
    strictPort: true,
    proxy: { '/api': target },
  },
  test: { include: ['src/**/*.test.ts'] },
})
