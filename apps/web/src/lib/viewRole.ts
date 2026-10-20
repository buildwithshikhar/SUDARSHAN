import { useSyncExternalStore } from 'react'
import { useAuth, type Role } from './auth'
import { readSetting, writeSetting } from './storage'

/** What a signed-in person works as: the account role, or the detachment commander seat for a trainee account. */
export type ViewRole = Role | 'commander'

export const TEAM_ROLE_KEY = 'ui.teamRole'
export type TeamRole = 'operator' | 'commander'

const listeners = new Set<() => void>()

export function getTeamRole(): TeamRole {
  return readSetting(TEAM_ROLE_KEY) === 'commander' ? 'commander' : 'operator'
}

export function setTeamRole(next: TeamRole): void {
  writeSetting(TEAM_ROLE_KEY, next)
  listeners.forEach((listener) => listener())
}

function useTeamRole(): TeamRole {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    getTeamRole,
    getTeamRole,
  )
}

/** The role whose sidebar and screens the signed-in person sees; null while signed out. */
export function useViewRole(): ViewRole | null {
  const { state } = useAuth()
  const team = useTeamRole()
  if (state.status !== 'authenticated') return null
  return state.user.role === 'trainee' && team === 'commander' ? 'commander' : state.user.role
}
