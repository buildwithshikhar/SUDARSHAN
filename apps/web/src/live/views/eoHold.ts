/**
 * What the EO view is allowed to draw: EO and IR reports, each held for 0.4 s, placed at the
 * bearing and elevation the sensor measured and at the angular size its pixel count implies.
 * There is no range in an EO report and none is invented here.
 */
import { angularSizeDeg, wrap180 } from '../geometry'
import type { Report } from '../protocol'

export const HOLD_MS = 400

export type EoShape = 'rotary-small' | 'fixed-wing-small' | 'bird' | 'point'

export interface HeldReport {
  key: number
  sensorId: string
  azimuthDeg: number
  elevationDeg: number
  /** Angular extent of the object in the image, in degrees. */
  sizeDeg: number
  apparentPx: number
  shape: EoShape
  /** Wall-clock ms of the last report that refreshed it. */
  seenAt: number
}

const SHAPES: ReadonlySet<string> = new Set(['rotary-small', 'fixed-wing-small', 'bird'])

/** The mesh to draw: the reported class if the sensor recognised one, otherwise a generic point. */
export function shapeFor(reportedClass: string | null): EoShape {
  return reportedClass !== null && SHAPES.has(reportedClass) ? (reportedClass as EoShape) : 'point'
}

export class ReportHold {
  private held: HeldReport[] = []
  private next = 1

  constructor(private readonly holdMs = HOLD_MS) {}

  /** Take the EO/IR reports of one frame, at the field of view the sensor had. */
  ingest(
    reports: readonly Report[],
    fovBySensor: Record<string, number | null>,
    nowMs: number,
  ): void {
    for (const r of reports) {
      if (r.modality !== 'eo' && r.modality !== 'ir') continue
      const px = r.features.apparent_px
      const fov = fovBySensor[r.sensor_id]
      if (typeof px !== 'number' || fov === null || fov === undefined) continue
      const sizeDeg = angularSizeDeg(px, fov)
      const radius = Math.max(0.35, fov * 0.08)
      const near = this.held.find(
        (h) =>
          h.sensorId === r.sensor_id &&
          Math.hypot(wrap180(h.azimuthDeg - r.azimuth_deg), h.elevationDeg - r.elevation_deg) <=
            radius,
      )
      const shape = shapeFor(r.reported_class)
      if (near) {
        near.azimuthDeg = r.azimuth_deg
        near.elevationDeg = r.elevation_deg
        near.sizeDeg = sizeDeg
        near.apparentPx = px
        near.shape = shape
        near.seenAt = nowMs
      } else {
        this.held.push({
          key: this.next++,
          sensorId: r.sensor_id,
          azimuthDeg: r.azimuth_deg,
          elevationDeg: r.elevation_deg,
          sizeDeg,
          apparentPx: px,
          shape,
          seenAt: nowMs,
        })
      }
    }
  }

  /** Reports still inside their hold at `nowMs`; expired ones are forgotten. */
  active(nowMs: number): readonly HeldReport[] {
    this.held = this.held.filter((h) => nowMs - h.seenAt <= this.holdMs)
    return this.held
  }
}
