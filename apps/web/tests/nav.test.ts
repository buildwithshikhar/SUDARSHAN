import en from '../src/i18n/en.json'
import hi from '../src/i18n/hi.json'
import { findModule, modulePath, NAV, sidebarGroups } from '../src/nav/modules'

const count = (role: keyof typeof NAV) => ({
  groups: NAV[role].length,
  modules: NAV[role].reduce((n, g) => n + g.modules.length, 0),
})

describe('navigation source list (docs/07-ui-map.md)', () => {
  it('matches the UI map counts for each role', () => {
    expect(count('trainee')).toEqual({ groups: 3, modules: 6 })
    expect(count('instructor')).toEqual({ groups: 4, modules: 10 })
    expect(count('admin')).toEqual({ groups: 3, modules: 8 })
  })

  it('shows the shared Account group to every role exactly once', () => {
    for (const role of ['trainee', 'instructor', 'admin'] as const) {
      const groups = sidebarGroups(role)
      expect(groups.filter((g) => g.id === 'account')).toHaveLength(1)
      expect(groups.at(-1)?.id).toBe('account')
    }
  })

  it('has unique slugs per role and a wave on every module', () => {
    for (const role of ['trainee', 'instructor', 'admin'] as const) {
      const slugs = sidebarGroups(role).flatMap((g) => g.modules.map((m) => m.slug))
      expect(new Set(slugs).size).toBe(slugs.length)
      for (const group of sidebarGroups(role))
        for (const module of group.modules) expect(module.wave).toMatch(/^\d+[abc]?$/)
    }
  })

  it('has an English and a Hindi label for every group and module', () => {
    for (const role of ['trainee', 'instructor', 'admin'] as const)
      for (const group of sidebarGroups(role)) {
        expect(en.nav.group).toHaveProperty(group.id)
        expect(hi.nav.group).toHaveProperty(group.id)
        for (const module of group.modules) {
          expect(en.nav.module).toHaveProperty(module.slug)
          expect(hi.nav.module).toHaveProperty(module.slug)
        }
      }
  })

  it('finds modules only inside the role', () => {
    expect(findModule('trainee', 'drills')?.group.id).toBe('train')
    expect(findModule('trainee', 'cohorts')).toBeNull()
    expect(findModule('admin', 'profile')?.group.id).toBe('account')
    expect(modulePath('instructor', 'class', 'cohorts')).toBe('/instructor/cohorts')
    expect(modulePath('admin', 'account', 'profile')).toBe('/account/profile')
  })
})
