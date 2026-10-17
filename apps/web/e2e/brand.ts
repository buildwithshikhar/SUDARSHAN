import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

export const brand = JSON.parse(
  readFileSync(resolve(import.meta.dirname, '../../../brand.json'), 'utf-8'),
) as { productName: string; descriptor: string }
