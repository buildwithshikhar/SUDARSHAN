/// <reference types="vitest/config" />
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const root = resolve(import.meta.dirname, '../..')
const brand = JSON.parse(readFileSync(resolve(root, 'brand.json'), 'utf-8')) as {
  productName: string
  descriptor: string
}

// The product name lives only in brand.json; the HTML shell reads it at build time.
const brandHtml = (): Plugin => ({
  name: 'brand-html',
  transformIndexHtml: (html) =>
    html
      .replaceAll('%PRODUCT_NAME%', brand.productName)
      .replaceAll('%DESCRIPTOR%', brand.descriptor),
})

const apiTarget = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'
const proxy = Object.fromEntries(
  ['/api', '/healthz', '/readyz'].map((path) => [path, { target: apiTarget, changeOrigin: true }]),
)

export default defineConfig({
  plugins: [react(), brandHtml()],
  server: { port: 5173, proxy, fs: { allow: [root] } },
  preview: { port: 4173, proxy },
  build: { sourcemap: false, target: 'es2022' },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
})
