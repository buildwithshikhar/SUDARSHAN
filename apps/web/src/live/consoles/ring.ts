/**
 * A fixed-size ring of display rows in one typed array. Rows are written at the moment scenario
 * time crosses a row boundary (4 per second); nothing is allocated after construction.
 */
export class RowRing {
  readonly data: Uint8Array
  /** Slot the next row goes to. */
  head = 0
  /** Rows written so far, up to `rows`. */
  count = 0
  /** Rows written in total: a change counter for the drawing code. */
  version = 0

  constructor(
    readonly bins: number,
    readonly rows: number,
  ) {
    this.data = new Uint8Array(bins * rows)
  }

  /** Claim the next slot, clear it and return its byte offset. */
  next(): number {
    const offset = this.head * this.bins
    this.data.fill(0, offset, offset + this.bins)
    this.head = (this.head + 1) % this.rows
    this.count = Math.min(this.rows, this.count + 1)
    this.version += 1
    return offset
  }

  /** Slot of the row `age` rows back (0 is the newest), or -1 when it has not been written. */
  slotOfAge(age: number): number {
    if (age < 0 || age >= this.count) return -1
    return (this.head - 1 - age + this.rows * 2) % this.rows
  }

  /** Read one value: bin `bin` of the row `age` rows back (0 when there is no such row). */
  at(age: number, bin: number): number {
    const slot = this.slotOfAge(age)
    return slot < 0 ? 0 : (this.data[slot * this.bins + bin] ?? 0)
  }

  clear(): void {
    this.data.fill(0)
    this.head = 0
    this.count = 0
    this.version += 1
  }
}
