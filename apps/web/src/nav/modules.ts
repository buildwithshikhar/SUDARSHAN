/**
 * The single source list for the sidebar, matching docs/07-ui-map.md.
 * Counts per role are pinned by tests/nav.test.ts so they cannot drift from the UI map.
 * The detachment commander seat is a trainee account working in the team role; it has its own
 * sidebar, listed apart from the counted roles.
 */
import type { Role } from '../lib/auth'
import type { ViewRole } from '../lib/viewRole'

/** A screen inside a module, for modules that have more than one (docs/07-ui-map.md). */
export interface NavScreen {
  slug: string
  /** Route pattern. */
  path: string
  /** Roles that may open it. */
  roles: Role[]
}

export interface NavModule {
  slug: string
  /** Build-plan reference; kept for the planning documents, never shown. */
  wave: string
  /** Where the sidebar link goes, when the module has its own routes. */
  home?: string
  screens?: NavScreen[]
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
        {
          slug: 'drills',
          wave: '5',
          screens: [
            { slug: 'session-lobby', path: '/train/lobby', roles: ['trainee', 'instructor'] },
            { slug: 'live-session', path: '/train/session/:id', roles: ['trainee', 'instructor'] },
          ],
        },
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
        { slug: 'scenarios', wave: '9a', home: '/content/scenarios' },
        { slug: 'generator', wave: '9a', home: '/content/generator' },
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

/** A trainee account in the detachment commander seat: the command module, then the trainee screens. */
const COMMANDER: NavGroup[] = [
  { id: 'command', modules: [{ slug: 'command', wave: '13a' }] },
  ...NAV.trainee,
]

const ALL: Record<ViewRole, NavGroup[]> = { ...NAV, commander: COMMANDER }

/** The counted sidebar groups: trainee Account (Profile, Help) is shared, so it is listed apart. */
export function sidebarGroups(role: ViewRole): NavGroup[] {
  const own = ALL[role].filter((g) => g.id !== 'account')
  const account = NAV.trainee.find((g) => g.id === 'account')
  return account ? [...own, account] : own
}

export function findModule(
  role: ViewRole,
  slug: string,
): { group: NavGroup; module: NavModule } | null {
  for (const group of sidebarGroups(role)) {
    const module = group.modules.find((m) => m.slug === slug)
    if (module) return { group, module }
  }
  return null
}

export function modulePath(role: ViewRole, groupId: string, slug: string): string {
  const home = findModule(role, slug)?.module.home
  if (home) return home
  return groupId === 'account' ? `/account/${slug}` : `/${role}/${slug}`
}
