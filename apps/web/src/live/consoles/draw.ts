/**
 * Canvas drawing for the RF and acoustic consoles: dark instrument displays with a graticule,
 * drawn at device pixel ratio by the caller's transform. Pure functions of a prepared scene; the
 * only state is the offscreen bitmap that mirrors a row ring (`RowImage`).
 *
 * The plot area is a recessed dark display in both themes, as on a real instrument, so the colour
 * map always has a dark floor. Everything around it (tabs, readouts, tables) follows the theme.
 */
import type { RowRing } from './ring'
import {
  AC_MAX_HZ,
  HISTORY_S,
  INFERNO_LUT,
  RF_BANDS,
  RF_BINS,
  RF_CEIL_DBM,
  RF_FLOOR_DBM,
  RF_NOISE_DBM,
  dbmFraction,
  maxOrder,
  type HarmonicLine,
} from './spectra'

export const PLOT = {
  bg: '#080b0d',
  well: '#0c1013',
  grid: '#232c32',
  gridStrong: '#34414a',
  text: '#a9b4bc',
  textStrong: '#e4e7ea',
  trace: '#6fd0dc',
  peak: 'rgba(111, 208, 220, 0.38)',
  fill: 'rgba(111, 208, 220, 0.12)',
  cursor: '#f1f3f4',
  alert: '#e0a526',
} as const

export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export interface RfLayout {
  spectrum: Rect
  waterfall: Rect
  /** Where the band labels sit (below the waterfall). */
  axisY: number
}

const MARGIN = { left: 38, right: 6, top: 6, bottom: 16 }

/** The RF console's plot rectangles for a canvas of `w` by `h` CSS pixels. */
export function rfLayout(w: number, h: number): RfLayout {
  const x = MARGIN.left
  const inner = Math.max(8, w - MARGIN.left - MARGIN.right)
  const total = Math.max(24, h - MARGIN.top - MARGIN.bottom)
  const gap = 6
  const spectrumH = Math.max(20, Math.round((total - gap) * 0.4))
  const waterfallH = Math.max(8, total - gap - spectrumH)
  return {
    spectrum: { x, y: MARGIN.top, w: inner, h: spectrumH },
    waterfall: { x, y: MARGIN.top + spectrumH + gap, w: inner, h: waterfallH },
    axisY: MARGIN.top + spectrumH + gap + waterfallH + 3,
  }
}

/** The acoustic console's plot rectangle. */
export function acousticLayout(w: number, h: number): { plot: Rect; axisY: number } {
  const plot = {
    x: MARGIN.left,
    y: MARGIN.top + 8,
    w: Math.max(8, w - MARGIN.left - MARGIN.right),
    h: Math.max(16, h - MARGIN.top - 8 - MARGIN.bottom),
  }
  return { plot, axisY: plot.y + plot.h + 3 }
}

/** x of frequency `hz` on the acoustic plot. */
export const acousticX = (plot: Rect, hz: number): number => plot.x + (hz / AC_MAX_HZ) * plot.w

/**
 * An offscreen bitmap of a ring through the inferno map. Rows are stored upside down (slot s at
 * image row `rows - 1 - s`) so that the newest block and the older block are each contiguous and
 * a ring that has wrapped is drawn with two copies, newest at the top.
 */
export class RowImage {
  readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D | null
  private readonly image: ImageData | null
  private seen = -1

  constructor(
    private readonly ring: RowRing,
    doc: Document = document,
  ) {
    this.canvas = doc.createElement('canvas')
    this.canvas.width = ring.bins
    this.canvas.height = ring.rows
    this.ctx = this.canvas.getContext('2d')
    this.image = this.ctx ? this.ctx.createImageData(ring.bins, ring.rows) : null
    if (this.image) for (let i = 3; i < this.image.data.length; i += 4) this.image.data[i] = 255
  }

  get ready(): boolean {
    return this.ctx !== null
  }

  /** Bring the bitmap up to date with the ring. Returns true when pixels changed. */
  sync(): boolean {
    const { ring, ctx, image } = this
    if (!ctx || !image || ring.version === this.seen) return false
    const pixels = image.data
    if (ring.count === 0 || this.seen < 0) {
      // First sync, or the ring was cleared: start from an empty (black) bitmap.
      for (let i = 0; i < pixels.length; i += 4) {
        pixels[i] = INFERNO_LUT[0] ?? 0
        pixels[i + 1] = INFERNO_LUT[1] ?? 0
        pixels[i + 2] = INFERNO_LUT[2] ?? 0
      }
    }
    // Slots keep their image row, so only the rows written since the last sync need converting.
    const fresh = this.seen < 0 ? ring.count : Math.min(ring.count, ring.version - this.seen)
    const bins = ring.bins
    for (let age = 0; age < fresh; age++) {
      const slot = ring.slotOfAge(age)
      let from = slot * bins
      let to = (ring.rows - 1 - slot) * bins * 4
      for (let b = 0; b < bins; b++) {
        const c = (ring.data[from++] ?? 0) * 3
        pixels[to++] = INFERNO_LUT[c] ?? 0
        pixels[to++] = INFERNO_LUT[c + 1] ?? 0
        pixels[to++] = INFERNO_LUT[c + 2] ?? 0
        to++
      }
    }
    ctx.putImageData(image, 0, 0)
    this.seen = ring.version
    return true
  }

  /** Draw the ring into `dest`, newest row at the top, oldest at the bottom. */
  paint(ctx: CanvasRenderingContext2D, dest: Rect): void {
    const { ring } = this
    if (ring.count === 0) return
    const rowH = dest.h / ring.rows
    ctx.imageSmoothingEnabled = false
    // Block A, image rows [rows - head, rows): ages 0 .. head - 1, newest first.
    const a = ring.head
    if (a > 0) {
      ctx.drawImage(this.canvas, 0, ring.rows - a, ring.bins, a, dest.x, dest.y, dest.w, a * rowH)
    }
    // Block B, image rows [0, rows - head): ages head .. rows - 1, once the ring has wrapped.
    const b = ring.count - a
    if (b > 0) {
      ctx.drawImage(this.canvas, 0, 0, ring.bins, b, dest.x, dest.y + a * rowH, dest.w, b * rowH)
    }
  }
}

function frame(ctx: CanvasRenderingContext2D, r: Rect, fill: string): void {
  ctx.fillStyle = fill
  ctx.fillRect(r.x, r.y, r.w, r.h)
}

/** Time-axis labels on the left of a waterfall: now, then every 10 s back. */
function drawTimeAxis(ctx: CanvasRenderingContext2D, r: Rect): void {
  ctx.fillStyle = PLOT.text
  ctx.strokeStyle = PLOT.gridStrong
  ctx.textAlign = 'right'
  ctx.textBaseline = 'middle'
  ctx.lineWidth = 1
  for (let s = 0; s <= HISTORY_S; s += 10) {
    const y = Math.round(r.y + (s / HISTORY_S) * r.h) + 0.5
    ctx.beginPath()
    ctx.moveTo(r.x - 3, y)
    ctx.lineTo(r.x, y)
    ctx.stroke()
    if (s < HISTORY_S)
      ctx.fillText(s === 0 ? '0 s' : `-${s}`, r.x - 5, Math.min(y + 4, r.y + r.h - 4))
  }
}

function fitLabel(ctx: CanvasRenderingContext2D, text: string, width: number, mono: string): void {
  for (const size of [10, 9]) {
    ctx.font = `${size}px ${mono}`
    if (ctx.measureText(text).width <= width) return
  }
}

export interface Stale {
  text: string
}

function drawStale(ctx: CanvasRenderingContext2D, r: Rect, stale: Stale, mono: string): void {
  ctx.font = `bold 10px ${mono}`
  const w = ctx.measureText(stale.text).width + 12
  const x = r.x + r.w - w - 4
  const y = r.y + 4
  ctx.fillStyle = PLOT.bg
  ctx.fillRect(x, y, w, 16)
  ctx.strokeStyle = PLOT.alert
  ctx.lineWidth = 1
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, 15)
  ctx.fillStyle = PLOT.alert
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillText(stale.text, x + 6, y + 8.5)
}

export interface RfScene {
  width: number
  height: number
  mono: string
  spectrum: Float32Array
  peak: Float32Array
  image: RowImage
  /** Shown boxed in a corner when the stream has stopped, instead of live data. */
  stale: Stale | null
}

export function drawRf(ctx: CanvasRenderingContext2D, s: RfScene): void {
  const { spectrum: sp, waterfall: wf, axisY } = rfLayout(s.width, s.height)
  ctx.clearRect(0, 0, s.width, s.height)
  frame(ctx, { x: 0, y: 0, w: s.width, h: s.height }, PLOT.bg)
  frame(ctx, sp, PLOT.well)
  frame(ctx, wf, PLOT.well)

  ctx.font = `10px ${s.mono}`
  ctx.lineWidth = 1
  ctx.textBaseline = 'middle'
  ctx.textAlign = 'right'

  // Spectrum graticule: a line every 20 dB, labelled.
  for (let dbm = RF_FLOOR_DBM; dbm <= RF_CEIL_DBM; dbm += 20) {
    const y = Math.round(sp.y + (1 - dbmFraction(dbm)) * sp.h) + 0.5
    ctx.strokeStyle = dbm === RF_FLOOR_DBM || dbm === RF_CEIL_DBM ? PLOT.gridStrong : PLOT.grid
    ctx.beginPath()
    ctx.moveTo(sp.x, y)
    ctx.lineTo(sp.x + sp.w, y)
    ctx.stroke()
    ctx.fillStyle = PLOT.text
    ctx.fillText(String(dbm), sp.x - 5, Math.min(Math.max(y, sp.y + 5), sp.y + sp.h - 5))
  }
  // Noise floor, dashed.
  const nfY = Math.round(sp.y + (1 - dbmFraction(RF_NOISE_DBM)) * sp.h) + 0.5
  ctx.save()
  ctx.setLineDash([3, 3])
  ctx.strokeStyle = PLOT.gridStrong
  ctx.beginPath()
  ctx.moveTo(sp.x, nfY)
  ctx.lineTo(sp.x + sp.w, nfY)
  ctx.stroke()
  ctx.restore()

  // Band windows: boundaries through both plots, a dashed centre line in the spectrum.
  const bandW = sp.w / RF_BANDS.length
  for (let i = 0; i <= RF_BANDS.length; i++) {
    const x = Math.round(sp.x + i * bandW) + 0.5
    ctx.strokeStyle = PLOT.gridStrong
    ctx.beginPath()
    ctx.moveTo(x, sp.y)
    ctx.lineTo(x, sp.y + sp.h)
    ctx.moveTo(x, wf.y)
    ctx.lineTo(x, wf.y + wf.h)
    ctx.stroke()
  }
  ctx.save()
  ctx.setLineDash([2, 4])
  ctx.strokeStyle = PLOT.grid
  for (let i = 0; i < RF_BANDS.length; i++) {
    const x = Math.round(sp.x + (i + 0.5) * bandW) + 0.5
    ctx.beginPath()
    ctx.moveTo(x, sp.y)
    ctx.lineTo(x, sp.y + sp.h)
    ctx.stroke()
  }
  ctx.restore()

  // Spectrum: peak hold behind, the live row in front.
  const xOf = (bin: number): number => sp.x + ((bin + 0.5) / RF_BINS) * sp.w
  const yOf = (dbm: number): number => sp.y + (1 - dbmFraction(dbm)) * sp.h
  ctx.beginPath()
  for (let b = 0; b < RF_BINS; b++) {
    const x = xOf(b)
    if (b === 0) ctx.moveTo(x, yOf(s.peak[b] ?? 0))
    else ctx.lineTo(x, yOf(s.peak[b] ?? 0))
  }
  ctx.strokeStyle = PLOT.peak
  ctx.lineWidth = 1
  ctx.stroke()
  ctx.beginPath()
  ctx.moveTo(xOf(0), sp.y + sp.h)
  for (let b = 0; b < RF_BINS; b++) ctx.lineTo(xOf(b), yOf(s.spectrum[b] ?? 0))
  ctx.lineTo(xOf(RF_BINS - 1), sp.y + sp.h)
  ctx.closePath()
  ctx.fillStyle = PLOT.fill
  ctx.fill()
  ctx.beginPath()
  for (let b = 0; b < RF_BINS; b++) {
    const x = xOf(b)
    if (b === 0) ctx.moveTo(x, yOf(s.spectrum[b] ?? 0))
    else ctx.lineTo(x, yOf(s.spectrum[b] ?? 0))
  }
  ctx.strokeStyle = PLOT.trace
  ctx.lineWidth = 1.25
  ctx.stroke()

  // Waterfall.
  s.image.paint(ctx, wf)
  drawTimeAxis(ctx, wf)

  // Band markers: label and display half-span under each window.
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  ctx.fillStyle = PLOT.textStrong
  RF_BANDS.forEach((band, i) => {
    fitLabel(ctx, band.label, bandW - 4, s.mono)
    ctx.fillText(band.label, sp.x + (i + 0.5) * bandW, axisY)
  })

  if (s.stale) drawStale(ctx, sp, s.stale, s.mono)
}

export interface AcousticScene {
  width: number
  height: number
  mono: string
  image: RowImage
  cursorHz: number
  /** Whether the cursor is the keyboard's current focus (drawn heavier). */
  focused: boolean
  /** The harmonic lines of the reports in the last second, marked along the top edge. */
  lines: readonly HarmonicLine[]
  stale: Stale | null
}

export function drawAcoustic(ctx: CanvasRenderingContext2D, s: AcousticScene): void {
  const { plot, axisY } = acousticLayout(s.width, s.height)
  ctx.clearRect(0, 0, s.width, s.height)
  frame(ctx, { x: 0, y: 0, w: s.width, h: s.height }, PLOT.bg)
  frame(ctx, plot, PLOT.well)
  s.image.paint(ctx, plot)
  drawTimeAxis(ctx, plot)

  ctx.font = `10px ${s.mono}`
  ctx.lineWidth = 1
  // Frequency graticule every 250 Hz, labelled every 500.
  ctx.textAlign = 'center'
  ctx.textBaseline = 'top'
  for (let hz = 0; hz <= AC_MAX_HZ; hz += 250) {
    const x = Math.round(acousticX(plot, hz)) + 0.5
    ctx.strokeStyle = hz % 500 === 0 ? PLOT.gridStrong : PLOT.grid
    ctx.globalAlpha = 0.7
    ctx.beginPath()
    ctx.moveTo(x, plot.y)
    ctx.lineTo(x, plot.y + plot.h)
    ctx.stroke()
    ctx.globalAlpha = 1
    if (hz % 500 === 0) {
      ctx.fillStyle = PLOT.textStrong
      ctx.textAlign = hz === 0 ? 'left' : hz === AC_MAX_HZ ? 'right' : 'center'
      ctx.fillText(hz === 0 ? '0 Hz' : hz === AC_MAX_HZ ? '2000' : String(hz), x, axisY)
    }
  }

  // Harmonic marks along the top edge: a small triangle at every line a report names.
  ctx.fillStyle = PLOT.trace
  for (const line of s.lines) {
    const n = maxOrder(line)
    for (let k = 1; k <= n; k++) {
      const hz = k * line.fundamentalHz
      if (hz >= AC_MAX_HZ) break
      const x = acousticX(plot, hz)
      ctx.beginPath()
      ctx.moveTo(x - 3, plot.y - 7)
      ctx.lineTo(x + 3, plot.y - 7)
      ctx.lineTo(x, plot.y - 1)
      ctx.closePath()
      ctx.fill()
    }
  }

  // Cursor: a dashed line with a flag at each end, so it reads without colour.
  const cx = Math.round(acousticX(plot, s.cursorHz)) + 0.5
  ctx.save()
  ctx.strokeStyle = PLOT.cursor
  ctx.fillStyle = PLOT.cursor
  ctx.lineWidth = s.focused ? 2 : 1
  ctx.setLineDash([5, 3])
  ctx.beginPath()
  ctx.moveTo(cx, plot.y)
  ctx.lineTo(cx, plot.y + plot.h)
  ctx.stroke()
  ctx.setLineDash([])
  ctx.beginPath()
  ctx.moveTo(cx - 4, plot.y + plot.h + 1)
  ctx.lineTo(cx + 4, plot.y + plot.h + 1)
  ctx.lineTo(cx, plot.y + plot.h - 5)
  ctx.closePath()
  ctx.fill()
  ctx.restore()

  if (s.stale) drawStale(ctx, plot, s.stale, s.mono)
}
