import { useEffect, useRef, type MutableRefObject } from 'react'

/** A ref that always holds the latest value, updated after each render (safe to read in handlers). */
export function useLatest<T>(value: T): MutableRefObject<T> {
  const ref = useRef(value)
  useEffect(() => {
    ref.current = value
  })
  return ref
}
