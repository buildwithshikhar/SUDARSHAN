import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api, ApiError, NetworkError, setCsrfToken } from './api'
import { applyUserPreferences, getTheme } from './prefs'
import i18n, { isLanguage } from '../i18n'

export type Role = 'trainee' | 'instructor' | 'admin'

export interface User {
  id: string
  email: string
  role: Role
  language: string
  theme: string
}

interface SessionResponse {
  user: User
  csrf: string
  expiresAt: string
}

export type AuthState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'offline' }
  | { status: 'authenticated'; user: User; expiresAt: string }

interface AuthContextValue {
  state: AuthState
  login: (email: string, password: string) => Promise<void>
  evaluationLogin: (seat: string) => Promise<void>
  logout: () => Promise<void>
  savePreferences: (prefs: { language?: string; theme?: string }) => Promise<void>
  retry: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  const accept = useCallback((session: SessionResponse) => {
    setCsrfToken(session.csrf)
    applyUserPreferences(session.user)
    setState({ status: 'authenticated', user: session.user, expiresAt: session.expiresAt })
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    api<SessionResponse>('/api/v1/auth/me', { signal: controller.signal })
      .then(accept)
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        if (error instanceof ApiError && error.status === 401) {
          setCsrfToken(null)
          setState({ status: 'anonymous' })
        } else {
          setState({ status: 'offline' })
        }
      })
    return () => controller.abort()
  }, [attempt, accept])

  const login = useCallback(
    async (email: string, password: string) => {
      accept(
        await api<SessionResponse>('/api/v1/auth/login', {
          method: 'POST',
          body: { email, password },
        }),
      )
    },
    [accept],
  )

  const evaluationLogin = useCallback(
    async (seat: string) => {
      accept(
        await api<SessionResponse>('/api/v1/auth/evaluation-login', {
          method: 'POST',
          body: { seat },
        }),
      )
    },
    [accept],
  )

  const logout = useCallback(async () => {
    try {
      await api<undefined>('/api/v1/auth/logout', { method: 'POST' })
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
    }
    setCsrfToken(null)
    setState({ status: 'anonymous' })
  }, [])

  const savePreferences = useCallback(async (prefs: { language?: string; theme?: string }) => {
    const user = await api<User>('/api/v1/auth/me/preferences', { method: 'PATCH', body: prefs })
    setState((current) => (current.status === 'authenticated' ? { ...current, user } : current))
  }, [])

  const retry = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((n) => n + 1)
  }, [])

  const value = useMemo(
    () => ({ state, login, evaluationLogin, logout, savePreferences, retry }),
    [state, login, evaluationLogin, logout, savePreferences, retry],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}

/** Preference changes: applied immediately, and saved to the account when signed in. */
export async function persistPreference(
  auth: AuthContextValue,
  prefs: { language?: string; theme?: string },
): Promise<void> {
  if (auth.state.status !== 'authenticated') return
  try {
    await auth.savePreferences(prefs)
  } catch (error) {
    if (!(error instanceof NetworkError || error instanceof ApiError)) throw error
  }
}

export function currentPreferences(): { language: string; theme: string } {
  return { language: isLanguage(i18n.language) ? i18n.language : 'en', theme: getTheme() }
}
