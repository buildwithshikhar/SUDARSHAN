import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from './api'

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

interface VersionContextValue {
  state: VersionState
  retry: () => void
}

const VersionContext = createContext<VersionContextValue | null>(null)

export function VersionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<VersionState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    api<VersionInfo>('/api/v1/version', { signal: controller.signal })
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

  const value = useMemo(() => ({ state, retry }), [state, retry])
  return <VersionContext.Provider value={value}>{children}</VersionContext.Provider>
}

export function useVersion(): VersionContextValue {
  const value = useContext(VersionContext)
  if (!value) throw new Error('useVersion must be used inside VersionProvider')
  return value
}
