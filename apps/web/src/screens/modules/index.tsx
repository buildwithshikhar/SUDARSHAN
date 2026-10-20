import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

type Screen = LazyExoticComponent<ComponentType>

const admin = <K extends string>(name: K) =>
  lazy(() =>
    import('./admin').then((m) => ({ default: (m as unknown as Record<K, ComponentType>)[name] })),
  )
const instructor = <K extends string>(name: K) =>
  lazy(() =>
    import('./instructor').then((m) => ({
      default: (m as unknown as Record<K, ComponentType>)[name],
    })),
  )
const trainee = <K extends string>(name: K) =>
  lazy(() =>
    import('./trainee').then((m) => ({
      default: (m as unknown as Record<K, ComponentType>)[name],
    })),
  )
const command = lazy(() => import('./command').then((m) => ({ default: m.Command })))

/** The screen behind each sidebar module that has no routes of its own; loaded when first opened. */
export const MODULE_SCREENS: Record<string, Screen> = {
  today: trainee('Today'),
  drills: trainee('Drills'),
  'recognition-library': trainee('RecognitionLibrary'),
  'my-performance': trainee('MyPerformance'),
  help: trainee('Help'),
  command,
  cohorts: instructor('Cohorts'),
  trainees: instructor('Trainees'),
  'live-sessions': instructor('LiveSessions'),
  'team-exercise': instructor('TeamExercise'),
  'rule-packs': instructor('RulePacks'),
  curricula: instructor('Curricula'),
  'unit-aar': instructor('UnitAar'),
  reports: instructor('Reports'),
  'users-and-roles': admin('UsersAndRoles'),
  organisation: admin('Organisation'),
  packs: admin('Packs'),
  'data-register': admin('DataRegister'),
  records: admin('Records'),
  health: admin('Health'),
  settings: admin('Settings'),
  backup: admin('Backup'),
}
