// Generates the web contract types in src/contracts from packs/schemas/*.v1.json.
// Usage: node scripts/contracts.mjs [--check] [--out <dir>]
//   --check   writes nothing; exits 1 if any generated file is stale, missing or extra
//   --out     output directory (default apps/web/src/contracts)
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { basename, resolve } from 'node:path'
import { compile } from 'json-schema-to-typescript'
import { format, resolveConfig } from 'prettier'

const root = resolve(import.meta.dirname, '../../..')
const schemaDir = resolve(root, 'packs/schemas')

const args = process.argv.slice(2)
const check = args.includes('--check')
const outIndex = args.indexOf('--out')
const outArg = outIndex === -1 ? undefined : args[outIndex + 1]
if (outIndex !== -1 && !outArg) {
  console.error('--out needs a directory')
  process.exit(2)
}
const outDir = outArg ? resolve(outArg) : resolve(import.meta.dirname, '../src/contracts')

// Stable public names for the top-level type of each schema, keyed by file stem.
const publicNames = {
  'scenario.v1': 'ScenarioV1',
  'rulepack.v1': 'RulePackV1',
  'sensor-profile.v1': 'SensorProfileV1',
  'event-record.v1': 'EventRecordV1',
  'action-record.v1': 'ActionRecordV1',
  'session-record.v1': 'SessionRecordV1',
  'live-client.v1': 'LiveClientMessageV1',
  'live-server.v1': 'LiveServerMessageV1',
}
// Shared definitions appear in several schemas; each is exported once, from its owner.
const sharedOwners = {
  'scenario.v1': ['Text', 'Vec3', 'PackRef'],
  'sensor-profile.v1': ['Quantity'],
  'action-record.v1': ['JsonValue'],
}

const prettierConfig = (await resolveConfig(resolve(import.meta.dirname, '../package.json'))) ?? {}
const pretty = (text) => format(text, { ...prettierConfig, parser: 'typescript' })

const files = readdirSync(schemaDir)
  .filter((name) => name.endsWith('.json'))
  .sort()

const outputs = new Map()
const indexLines = []
for (const file of files) {
  const stem = basename(file, '.json')
  const schema = JSON.parse(readFileSync(resolve(schemaDir, file), 'utf-8'))
  const alias = publicNames[stem]
  if (!alias) {
    console.error(`no public type name for ${file}; add it to publicNames in scripts/contracts.mjs`)
    process.exit(2)
  }
  const body = await compile(schema, stem, {
    bannerComment: '',
    format: false,
    additionalProperties: false,
    maxItems: -1,
    cwd: schemaDir,
  })
  const banner = `// Generated from packs/schemas/${file} by \`npm run contracts:gen\`. Do not edit.\n\n`
  outputs.set(`${stem}.ts`, await pretty(banner + body))
  const exported = [`${schema.title} as ${alias}`, ...(sharedOwners[stem] ?? [])]
  indexLines.push(`export type { ${exported.join(', ')} } from './${stem}'`)
}
const indexBanner =
  '// Generated from packs/schemas/*.v1.json by `npm run contracts:gen`. Do not edit.\n\n'
outputs.set('index.ts', await pretty(indexBanner + indexLines.join('\n') + '\n'))

if (check) {
  const stale = []
  let onDisk = []
  try {
    onDisk = readdirSync(outDir).filter((name) => name.endsWith('.ts'))
  } catch {
    /* a missing directory means every file is missing */
  }
  for (const [name, text] of outputs) {
    let current = ''
    try {
      current = readFileSync(resolve(outDir, name), 'utf-8')
    } catch {
      /* missing counts as stale */
    }
    if (current !== text) stale.push(name)
  }
  for (const name of onDisk) if (!outputs.has(name)) stale.push(`${name} (no schema produces it)`)
  if (stale.length > 0) {
    console.error(`contract types are out of date: ${stale.join(', ')}; run \`make schemas\``)
    process.exit(1)
  }
  console.log(`${outputs.size} contract type files up to date`)
} else {
  mkdirSync(outDir, { recursive: true })
  for (const [name, text] of outputs) writeFileSync(resolve(outDir, name), text)
  console.log(`wrote ${outputs.size} contract type files to ${outDir}`)
}
