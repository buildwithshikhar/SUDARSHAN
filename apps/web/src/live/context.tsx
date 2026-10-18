import { createContext, useContext, useSyncExternalStore, type ReactNode } from 'react'
import type { LiveSession } from './session'
import type { LiveState } from './store'

const SessionContext = createContext<LiveSession | null>(null)

export function LiveProvider({ session, children }: { session: LiveSession; children: ReactNode }) {
  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>
}

export function useLiveSession(): LiveSession {
  const session = useContext(SessionContext)
  if (!session) throw new Error('useLiveSession must be used inside LiveProvider')
  return session
}

/** Subscribe to a slice of the session state; the selector must return stable references. */
export function useLive<T>(selector: (state: LiveState) => T): T {
  const { store } = useLiveSession()
  return useSyncExternalStore(
    store.subscribe,
    () => selector(store.getState()),
    () => selector(store.getState()),
  )
}
