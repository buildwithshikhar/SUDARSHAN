import { useCallback, useEffect, useState } from 'react'

export interface VersionInfo {
  productName: string
  descriptor: string
  version: string
  gitSha: string
  buildTime: string
  env: string
}

export type VersionState =
  { status: 'loading' } | { status: 'ready'; info: VersionInfo } | { status: 'error' }

const base = (import.meta.env.VITE_API_URL as string | undefined) ?? ''

export async function fetchVersion(signal?: AbortSignal): Promise<VersionInfo> {
  const response = await fetch(`${base}/api/v1/version`, { signal })
  if (!response.ok) throw new Error(`version request failed: ${response.status}`)
  return (await response.json()) as VersionInfo
}

export function useVersion(): { state: VersionState; retry: () => void } {
  const [state, setState] = useState<VersionState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    fetchVersion(controller.signal)
      .then((info) => setState({ status: 'ready', info }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ status: 'error' })
      })
    return () => controller.abort()
  }, [attempt])

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])
  return { state, retry }
}
