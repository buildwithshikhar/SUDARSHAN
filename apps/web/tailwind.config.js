/** Colours resolve to the CSS variables in src/styles/tokens.css; Tailwind's default palette is removed. */
const v = (name) => `var(--${name})`

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    colors: {
      transparent: 'transparent',
      current: 'currentColor',
      bg: v('bg'),
      surface: { 1: v('surface-1'), 2: v('surface-2') },
      line: v('border'),
      ink: { DEFAULT: v('text'), 2: v('text-2') },
      accent: { DEFAULT: v('accent'), on: v('on-accent') },
      signal: v('signal'),
      track: {
        hostile: v('track-hostile'),
        suspect: v('track-suspect'),
        unknown: v('track-unknown'),
        neutral: v('track-neutral'),
        friend: v('track-friend'),
      },
    },
    fontFamily: {
      sans: ['var(--font-sans)'],
      mono: ['var(--font-mono)'],
    },
    fontSize: {
      '2xs': ['11px', { lineHeight: '16px' }],
      xs: ['12px', { lineHeight: '16px' }],
      sm: ['13px', { lineHeight: '20px' }],
      base: ['14px', { lineHeight: '20px' }],
      md: ['16px', { lineHeight: '24px' }],
      lg: ['20px', { lineHeight: '28px' }],
    },
    borderRadius: { none: '0', sm: '2px', DEFAULT: '2px', md: '4px' },
    spacing: {
      0: '0',
      px: '1px',
      0.5: '2px',
      1: '4px',
      2: '8px',
      3: '12px',
      4: '16px',
      6: '24px',
      8: '32px',
      12: '48px',
      7: '28px',
      10: '40px',
    },
    boxShadow: { none: 'none' },
    extend: {},
  },
  plugins: [],
}
