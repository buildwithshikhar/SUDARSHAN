/** Design tokens read from CSS custom properties, for canvas and WebGL code that cannot use Tailwind. */
export interface Tokens {
  bg: string
  surface1: string
  surface2: string
  line: string
  text: string
  text2: string
  accent: string
  signal: string
  hostile: string
  suspect: string
  unknown: string
  neutral: string
  friend: string
}

const NAMES: Record<keyof Tokens, string> = {
  bg: '--bg',
  surface1: '--surface-1',
  surface2: '--surface-2',
  line: '--border',
  text: '--text',
  text2: '--text-2',
  accent: '--accent',
  signal: '--signal',
  hostile: '--track-hostile',
  suspect: '--track-suspect',
  unknown: '--track-unknown',
  neutral: '--track-neutral',
  friend: '--track-friend',
}

const FALLBACK: Tokens = {
  bg: '#0b0e11',
  surface1: '#12161a',
  surface2: '#1a1f24',
  line: '#272d34',
  text: '#e4e7ea',
  text2: '#9ba4ae',
  accent: '#4fb6c2',
  signal: '#e0a526',
  hostile: '#e5484d',
  suspect: '#ee8a45',
  unknown: '#e6c84f',
  neutral: '#5db46e',
  friend: '#5b9bd5',
}

export function readTokens(root: HTMLElement = document.documentElement): Tokens {
  const style = getComputedStyle(root)
  const out = { ...FALLBACK }
  for (const key of Object.keys(NAMES) as (keyof Tokens)[]) {
    const value = style.getPropertyValue(NAMES[key]).trim()
    if (value) out[key] = value
  }
  return out
}

/** A cached token set that refreshes when the theme attribute changes. */
export function watchTokens(): { get: () => Tokens; dispose: () => void } {
  let tokens = readTokens()
  const observer = new MutationObserver(() => {
    tokens = readTokens()
  })
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  return { get: () => tokens, dispose: () => observer.disconnect() }
}

export type Affiliation = 'hostile' | 'suspect' | 'unknown' | 'neutral' | 'friend'

export function affiliationOf(identity: string | undefined): Affiliation {
  switch (identity) {
    case 'hostile':
    case 'suspect':
    case 'neutral':
    case 'friend':
      return identity
    default:
      return 'unknown'
  }
}

export const prefersReducedMotion = (): boolean =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches
