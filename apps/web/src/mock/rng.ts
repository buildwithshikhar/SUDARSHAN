/** Seeded generator for the typed screen data: the same seed always gives the same numbers. */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const clamp = (value: number, low: number, high: number): number =>
  Math.min(high, Math.max(low, value))

/** Round to a fixed number of decimals; keeps the seeded tables free of long floats. */
export const round = (value: number, digits = 1): number => {
  const k = 10 ** digits
  return Math.round(value * k) / k
}

/** A 16-digit hexadecimal chain value derived from text (display only, not a cryptographic hash). */
export function chainValue(text: string, previous: string): string {
  let h1 = 0x811c9dc5
  let h2 = 0x01000193
  const input = `${previous}|${text}`
  for (let i = 0; i < input.length; i += 1) {
    const c = input.charCodeAt(i)
    h1 = Math.imul(h1 ^ c, 0x01000193) >>> 0
    h2 = Math.imul(h2 + c, 0x85ebca6b) >>> 0
    h2 ^= h2 >>> 13
  }
  return `${h1.toString(16).padStart(8, '0')}${h2.toString(16).padStart(8, '0')}`
}

/** Index into an array that is known to be non-empty. */
export function at<T>(items: readonly T[], index: number): T {
  const item = items[((index % items.length) + items.length) % items.length]
  if (item === undefined) throw new Error('empty list')
  return item
}
