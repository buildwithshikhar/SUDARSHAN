/**
 * The single source list for the sidebar, matching docs/07-ui-map.md.
 * Each module records the wave that delivers it; until then its route shows an honest empty state.
 * Counts per role are pinned by tests/nav.test.ts so they cannot drift from the UI map.
 */
import type { Role } from '../lib/auth'

export interface NavModule {
  slug: string
  wave: string
}

export interface NavGroup {
  id: string
  modules: NavModule[]
}

export const NAV: Record<Role, NavGroup[]> = {
  trainee: [
    {
      id: 'train',
      modules: [
        { slug: 'today', wave: '11a' },
        { slug: 'drills', wave: '5' },
        { slug: 'recognition-library', wave: '11b' },
      ],
    },
    { id: 'review', modules: [{ slug: 'my-performance', wave: '12a' }] },
    {
      id: 'account',
      modules: [
        { slug: 'profile', wave: '2' },
        { slug: 'help', wave: '15a' },
      ],
    },
  ],
  instructor: [
    {
      id: 'class',
      modules: [
        { slug: 'cohorts', wave: '10a' },
        { slug: 'trainees', wave: '10a' },
      ],
    },
    {
      id: 'run',
      modules: [
        { slug: 'live-sessions', wave: '10b' },
        { slug: 'team-exercise', wave: '13a' },
      ],
    },
    {
      id: 'content',
      modules: [
        { slug: 'scenarios', wave: '9a' },
        { slug: 'generator', wave: '9a' },
        { slug: 'rule-packs', wave: '10a' },
        { slug: 'curricula', wave: '10a' },
      ],
    },
    {
      id: 'review',
      modules: [
        { slug: 'unit-aar', wave: '12a' },
        { slug: 'reports', wave: '12a' },
      ],
    },
  ],
  admin: [
    {
      id: 'administration',
      modules: [
        { slug: 'users-and-roles', wave: '13c' },
        { slug: 'organisation', wave: '13c' },
        { slug: 'packs', wave: '13c' },
      ],
    },
    {
      id: 'trust',
      modules: [
        { slug: 'data-register', wave: '13c' },
        { slug: 'records', wave: '13b' },
      ],
    },
    {
      id: 'system',
      modules: [
        { slug: 'health', wave: '13c' },
        { slug: 'settings', wave: '13c' },
        { slug: 'backup', wave: '13c' },
      ],
    },
  ],
}

/** Profile and Help are shown to every role in a shared Account group; profile is built now. */
export const ACCOUNT_BUILT = new Set(['profile'])

/** The counted sidebar groups: trainee Account (Profile, Help) is shared, so it is listed apart. */
export function sidebarGroups(role: Role): NavGroup[] {
  const own = NAV[role].filter((g) => g.id !== 'account')
  const account = NAV.trainee.find((g) => g.id === 'account')
  return account ? [...own, account] : own
}

export function findModule(
  role: Role,
  slug: string,
): { group: NavGroup; module: NavModule } | null {
  for (const group of sidebarGroups(role)) {
    const module = group.modules.find((m) => m.slug === slug)
    if (module) return { group, module }
  }
  return null
}

export function modulePath(role: Role, groupId: string, slug: string): string {
  return groupId === 'account' ? `/account/${slug}` : `/${role}/${slug}`
}
