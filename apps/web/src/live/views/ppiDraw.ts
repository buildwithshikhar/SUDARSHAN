/** Canvas drawing for the radar PPI. Pure functions of a prepared scene; no state of their own. */
import { DEG, ringStepM, type PpiFrame } from '../geometry'
import type { Affiliation, Tokens } from './theme'

export interface PpiPlot {
  x: number
  y: number
  /** 0 to 1: how much of the phosphor is left. */
  alpha: number
}

export interface PpiTrackMark {
  id: string
  label: string
  affiliation: Affiliation
  status: 'tentative' | 'confirmed' | 'coasting'
  x: number
  y: number
  /** Leader end point (velocity carried forward), in pixels. */
  lx: number
  ly: number
  selected: boolean
  trail: { x: number; y: number }[]
}

export interface PpiRing {
  x: number
  y: number
  radiusPx: number
  label: string
}

export interface PpiSensorMark {
  id: string
  modality: string
  x: number
  y: number
  /** Edges of a pointed field, as end points in pixels. */
  wedge: { x1: number; y1: number; x2: number; y2: number } | null
}

export interface PpiScene {
  width: number
  height: number
  frame: PpiFrame
  tokens: Tokens
  sweepDeg: number
  /** Decorative persistence trail behind the sweep; off for reduced motion. */
  sweepTrail: boolean
  plots: PpiPlot[]
  tracks: PpiTrackMark[]
  zones: PpiRing[]
  sensors: PpiSensorMark[]
  rings: { radiusPx: number; label: string }[]
  mono: string
}

const colourOf = (tokens: Tokens, affiliation: Affiliation): string => tokens[affiliation]

export function withAlpha(colour: string, alpha: number): string {
  if (colour.startsWith('#') && colour.length === 7) {
    const a = Math.round(Math.min(1, Math.max(0, alpha)) * 255)
      .toString(16)
      .padStart(2, '0')
    return `${colour}${a}`
  }
  return colour
}

/** Range rings for a given maximum range, labelled in km. */
export function buildRings(frame: PpiFrame): { radiusPx: number; label: string }[] {
  const step = ringStepM(frame.rangeMaxM)
  const out: { radiusPx: number; label: string }[] = []
  for (let m = step; m <= frame.rangeMaxM + 1; m += step) {
    out.push({
      radiusPx: (m / frame.rangeMaxM) * frame.radiusPx,
      label: `${(m / 1000).toFixed(m % 1000 === 0 ? 0 : 1)}`,
    })
  }
  return out
}

/**
 * Own simplified symbol set, one frame shape per affiliation (not APP-6 or MIL-STD-2525):
 * friend a rectangle, neutral a square, hostile a diamond, suspect a dashed diamond,
 * unknown a quatrefoil. A tentative track is drawn dashed, a coasting one with a bar through it.
 */
export function drawSymbol(
  ctx: CanvasRenderingContext2D,
  affiliation: Affiliation,
  x: number,
  y: number,
  r: number,
  colour: string,
  status: 'tentative' | 'confirmed' | 'coasting',
): void {
  ctx.save()
  ctx.strokeStyle = colour
  ctx.lineWidth = 1.5
  ctx.setLineDash(affiliation === 'suspect' || status === 'tentative' ? [3, 2] : [])
  ctx.beginPath()
  switch (affiliation) {
    case 'hostile':
    case 'suspect':
      ctx.moveTo(x, y - r * 1.25)
      ctx.lineTo(x + r * 1.25, y)
      ctx.lineTo(x, y + r * 1.25)
      ctx.lineTo(x - r * 1.25, y)
      ctx.closePath()
      break
    case 'friend':
      ctx.rect(x - r * 1.3, y - r * 0.9, r * 2.6, r * 1.8)
      break
    case 'neutral':
      ctx.rect(x - r, y - r, r * 2, r * 2)
      break
    case 'unknown': {
      // Quatrefoil: four overlapping lobes, drawn as one outline.
      const k = r * 0.6
      const lobe = r * 0.72
      const s = Math.sqrt(lobe * lobe - k * k)
      const a0 = Math.atan2(-s, -k)
      const a1 = Math.atan2(k, s)
      const centres: [number, number][] = [
        [k, -k],
        [k, k],
        [-k, k],
        [-k, -k],
      ]
      centres.forEach(([dx, dy], i) => {
        ctx.arc(x + dx, y + dy, lobe, a0 + (i * Math.PI) / 2, a1 + (i * Math.PI) / 2)
      })
      ctx.closePath()
      break
    }
  }
  ctx.stroke()
  if (status === 'coasting') {
    ctx.setLineDash([])
    ctx.beginPath()
    ctx.moveTo(x - r * 0.7, y + r * 0.1)
    ctx.lineTo(x + r * 0.7, y + r * 0.1)
    ctx.stroke()
  }
  ctx.restore()
}

function drawSelection(ctx: CanvasRenderingContext2D, x: number, y: number, colour: string): void {
  const d = 13
  const c = 5
  ctx.save()
  ctx.strokeStyle = colour
  ctx.lineWidth = 1.5
  ctx.setLineDash([])
  ctx.beginPath()
  for (const [sx, sy] of [
    [-1, -1],
    [1, -1],
    [1, 1],
    [-1, 1],
  ] as const) {
    ctx.moveTo(x + sx * d, y + sy * (d - c))
    ctx.lineTo(x + sx * d, y + sy * d)
    ctx.lineTo(x + sx * (d - c), y + sy * d)
  }
  ctx.stroke()
  ctx.restore()
}

export function drawPpi(ctx: CanvasRenderingContext2D, s: PpiScene): void {
  const { frame, tokens } = s
  const { cx, cy, radiusPx: R } = frame
  ctx.clearRect(0, 0, s.width, s.height)
  ctx.fillStyle = tokens.surface1
  ctx.fillRect(0, 0, s.width, s.height)

  // Scope face.
  ctx.fillStyle = tokens.bg
  ctx.beginPath()
  ctx.arc(cx, cy, R, 0, Math.PI * 2)
  ctx.fill()

  ctx.font = `10px ${s.mono}`
  ctx.textBaseline = 'middle'

  // Range rings with labels in km, set along the 45 degree bearing.
  ctx.lineWidth = 1
  for (const ring of s.rings) {
    ctx.strokeStyle = withAlpha(tokens.line, 1)
    ctx.beginPath()
    ctx.arc(cx, cy, ring.radiusPx, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = tokens.text2
    ctx.textAlign = 'left'
    ctx.fillText(
      `${ring.label} km`,
      cx + ring.radiusPx * Math.sin(Math.PI / 4) + 3,
      cy - ring.radiusPx * Math.cos(Math.PI / 4) - 1,
    )
  }
  // Cross-hair spokes.
  ctx.strokeStyle = tokens.line
  ctx.beginPath()
  ctx.moveTo(cx - R, cy)
  ctx.lineTo(cx + R, cy)
  ctx.moveTo(cx, cy - R)
  ctx.lineTo(cx, cy + R)
  ctx.stroke()

  // Outer scale: a tick every 10 degrees, longer and numbered every 30.
  ctx.strokeStyle = tokens.text2
  ctx.fillStyle = tokens.text2
  ctx.textAlign = 'center'
  for (let b = 0; b < 360; b += 10) {
    const a = b * DEG
    const long = b % 30 === 0
    const r1 = R
    const r2 = R + (long ? 7 : 4)
    ctx.beginPath()
    ctx.moveTo(cx + r1 * Math.sin(a), cy - r1 * Math.cos(a))
    ctx.lineTo(cx + r2 * Math.sin(a), cy - r2 * Math.cos(a))
    ctx.stroke()
    if (long) {
      const rl = R + 17
      ctx.fillText(String(b).padStart(3, '0'), cx + rl * Math.sin(a), cy - rl * Math.cos(a))
    }
  }

  // Zones.
  ctx.save()
  ctx.setLineDash([5, 4])
  ctx.strokeStyle = tokens.text2
  ctx.lineWidth = 1
  for (const zone of s.zones) {
    ctx.beginPath()
    ctx.arc(zone.x, zone.y, zone.radiusPx, 0, Math.PI * 2)
    ctx.stroke()
    ctx.fillStyle = tokens.text2
    ctx.textAlign = 'center'
    ctx.fillText(zone.label, zone.x, zone.y - zone.radiusPx - 7)
  }
  ctx.restore()

  // Sweep with a stepped persistence trail.
  const sweep = s.sweepDeg * DEG
  if (s.sweepTrail) {
    const steps = 22
    const span = 54 * DEG
    for (let i = steps; i >= 1; i--) {
      const a0 = sweep - (i / steps) * span
      const a1 = sweep - ((i - 1) / steps) * span
      ctx.fillStyle = withAlpha(tokens.accent, 0.16 * (1 - i / steps))
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.arc(cx, cy, R, a0 - Math.PI / 2, a1 - Math.PI / 2)
      ctx.closePath()
      ctx.fill()
    }
  }
  ctx.strokeStyle = tokens.accent
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(cx, cy)
  ctx.lineTo(cx + R * Math.sin(sweep), cy - R * Math.cos(sweep))
  ctx.stroke()

  // Pointed sensor fields and sensor sites.
  ctx.lineWidth = 1
  for (const sensor of s.sensors) {
    ctx.strokeStyle = tokens.text2
    ctx.fillStyle = tokens.text2
    if (sensor.wedge) {
      ctx.save()
      ctx.setLineDash([2, 3])
      ctx.beginPath()
      ctx.moveTo(sensor.wedge.x1, sensor.wedge.y1)
      ctx.lineTo(sensor.x, sensor.y)
      ctx.lineTo(sensor.wedge.x2, sensor.wedge.y2)
      ctx.stroke()
      ctx.restore()
    }
    ctx.beginPath()
    if (sensor.modality === 'radar') {
      ctx.arc(sensor.x, sensor.y, 3, 0, Math.PI * 2)
    } else if (sensor.modality === 'rf') {
      ctx.moveTo(sensor.x, sensor.y - 4)
      ctx.lineTo(sensor.x + 4, sensor.y + 3)
      ctx.lineTo(sensor.x - 4, sensor.y + 3)
      ctx.closePath()
    } else {
      ctx.rect(sensor.x - 3, sensor.y - 3, 6, 6)
    }
    ctx.stroke()
    ctx.textAlign = 'left'
    ctx.fillText(sensor.id, sensor.x + 6, sensor.y + 9)
  }

  // Plots.
  for (const plot of s.plots) {
    ctx.fillStyle = withAlpha(tokens.accent, plot.alpha)
    ctx.fillRect(plot.x - 2, plot.y - 2, 4, 4)
  }

  // Tracks.
  ctx.font = `11px ${s.mono}`
  for (const track of s.tracks) {
    const colour = colourOf(tokens, track.affiliation)
    if (track.trail.length > 1) {
      ctx.fillStyle = withAlpha(colour, 0.55)
      track.trail.forEach((p, i) => {
        const k = (i + 1) / track.trail.length
        ctx.fillRect(p.x - k, p.y - k, 1 + k, 1 + k)
      })
    }
    ctx.strokeStyle = colour
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(track.x, track.y)
    ctx.lineTo(track.lx, track.ly)
    ctx.stroke()
    drawSymbol(ctx, track.affiliation, track.x, track.y, 5, colour, track.status)
    if (track.selected) drawSelection(ctx, track.x, track.y, tokens.accent)
    ctx.fillStyle = track.selected ? tokens.text : tokens.text2
    ctx.textAlign = 'left'
    ctx.fillText(track.label, track.x + 10, track.y - 9)
  }
}
