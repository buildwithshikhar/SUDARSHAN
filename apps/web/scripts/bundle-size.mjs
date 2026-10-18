// Bundle budget (docs/04-engine.md): JavaScript <= 1.5 MB gzipped, excluding assets
// (fonts, images, terrain packs). Run after `npm run build`.
//
//   node scripts/bundle-size.mjs [--max-bytes 1500000] [--json out.json]
//
// Sizes are gzip level 9 of each file in dist/assets/*.js. "initial" is what index.html loads
// before any route; the budget applies to the total of every chunk, so lazy chunks cannot hide.
import { readFileSync, readdirSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const dist = join(root, 'dist')
const args = process.argv.slice(2)
const option = (name, fallback) => {
  const at = args.indexOf(name)
  return at >= 0 ? args[at + 1] : fallback
}
const maxBytes = Number(option('--max-bytes', '1500000'))
const jsonOut = option('--json', null)

let html
try {
  html = readFileSync(join(dist, 'index.html'), 'utf8')
} catch {
  console.error('dist/index.html not found: run `npm run build` first')
  process.exit(2)
}
const initial = new Set(
  [...html.matchAll(/(?:src|href)="\/?(assets\/[^"]+\.js)"/g)].map((m) => m[1]),
)

const files = readdirSync(join(dist, 'assets'))
  .filter((f) => f.endsWith('.js'))
  .map((f) => {
    const raw = readFileSync(join(dist, 'assets', f))
    return { file: `assets/${f}`, raw: raw.length, gzip: gzipSync(raw, { level: 9 }).length }
  })
  .sort((a, b) => b.gzip - a.gzip)

const total = files.reduce((n, f) => n + f.gzip, 0)
const first = files.filter((f) => initial.has(f.file)).reduce((n, f) => n + f.gzip, 0)
const kb = (n) => `${(n / 1024).toFixed(1)} KB`

for (const f of files) {
  console.log(
    `${kb(f.gzip).padStart(10)} gz  ${kb(f.raw).padStart(10)} raw  ${f.file}${initial.has(f.file) ? '  (initial)' : ''}`,
  )
}
console.log(`\ninitial ${kb(first)} gzipped · total ${kb(total)} gzipped · budget ${kb(maxBytes)}`)
if (jsonOut)
  writeFileSync(
    jsonOut,
    JSON.stringify({ initial_gzip: first, total_gzip: total, budget: maxBytes, files }, null, 2),
  )
if (total > maxBytes) {
  console.error(
    `FAIL: total JavaScript is ${total} bytes gzipped, over the ${maxBytes} byte budget`,
  )
  process.exit(1)
}
console.log('PASS')
