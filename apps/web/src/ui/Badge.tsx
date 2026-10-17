import type { ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'warning' | 'hostile' | 'neutralTrack'

const tones: Record<Tone, string> = {
  neutral: 'border-line text-ink-2',
  accent: 'border-accent text-accent',
  warning: 'border-signal text-signal',
  hostile: 'border-track-hostile text-track-hostile',
  neutralTrack: 'border-track-neutral text-track-neutral',
}

/** Status is always carried by the text; colour only reinforces it. */
export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex h-5 items-center border px-2 text-xs ${tones[tone]}`}>
      {children}
    </span>
  )
}
