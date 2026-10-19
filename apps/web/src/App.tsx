import { lazy, Suspense, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useParams,
} from 'react-router-dom'
import { PublicFrame } from './layout/PublicFrame'
import { Shell } from './layout/Shell'
import { AuthProvider, useAuth, type Role } from './lib/auth'
import { VersionProvider, useVersion } from './lib/version'
import { findModule } from './nav/modules'
import { About } from './screens/About'
import { Bench } from './screens/Bench'
import { Debrief } from './screens/Debrief'
import { DevComponents } from './screens/DevComponents'
import { ModulePlaceholder, NoAccess, NotFound, Offline } from './screens/Messages'
import { LiveSessionPage } from './screens/LiveSession'
import { Profile } from './screens/Profile'
import { SessionLobby } from './screens/SessionLobby'
import { SignIn } from './screens/SignIn'
import { Status } from './screens/Status'
import { LoadingState } from './ui/States'

// The authoring screens are loaded when first opened, so they stay out of the initial bundle.
const ScenarioLibrary = lazy(() =>
  import('./screens/ScenarioLibrary').then((m) => ({ default: m.ScenarioLibrary })),
)
const ScenarioEditor = lazy(() =>
  import('./screens/ScenarioEditor').then((m) => ({ default: m.ScenarioEditor })),
)
const GeneratorStudio = lazy(() =>
  import('./screens/GeneratorStudio').then((m) => ({ default: m.GeneratorStudio })),
)

const AUTHORS: Role[] = ['instructor', 'admin']

/** An authoring screen: instructor and admin only, loaded on demand. */
function Authoring({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <RoleGate roles={AUTHORS}>
      <Suspense fallback={<LoadingState label={t('app.loading')} />}>{children}</Suspense>
    </RoleGate>
  )
}

/** Pages that are reachable with or without a session pick the matching frame. */
function Frame({ children }: { children: ReactNode }) {
  const { state } = useAuth()
  return state.status === 'authenticated' ? (
    <Shell>{children}</Shell>
  ) : (
    <PublicFrame>{children}</PublicFrame>
  )
}

function RequireAuth() {
  const { t } = useTranslation()
  const { state } = useAuth()
  const location = useLocation()
  if (state.status === 'loading') {
    return (
      <PublicFrame>
        <LoadingState label={t('app.loading')} />
      </PublicFrame>
    )
  }
  if (state.status === 'anonymous') {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  return (
    <Shell>
      <Outlet />
    </Shell>
  )
}

/** Signed-in routes that bring their own full-screen frame (the live workspace). */
function RequireAuthBare() {
  const { t } = useTranslation()
  const { state } = useAuth()
  const location = useLocation()
  if (state.status === 'loading') {
    return (
      <PublicFrame>
        <LoadingState label={t('app.loading')} />
      </PublicFrame>
    )
  }
  if (state.status === 'anonymous') {
    return <Navigate to="/sign-in" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Screens only some roles may open; admins, for one, cannot play a session. */
function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { state } = useAuth()
  if (state.status !== 'authenticated') return null
  return roles.includes(state.user.role) ? <>{children}</> : <Navigate to="/no-access" replace />
}

/** /:role/:module: each role may open only its own modules; others get No access. */
function RoleModule() {
  const { role, module } = useParams()
  const { state } = useAuth()
  if (state.status !== 'authenticated') return null
  const own = state.user.role
  if (role !== own) {
    const known = role === 'trainee' || role === 'instructor' || role === 'admin'
    return known ? <Navigate to="/no-access" replace /> : <NotFound />
  }
  const found = module ? findModule(own, module) : null
  if (!found) return <NotFound />
  if (found.module.home) return <Navigate to={found.module.home} replace />
  return (
    <ModulePlaceholder slug={found.module.slug} groupId={found.group.id} wave={found.module.wave} />
  )
}

function AccountModule() {
  const { module } = useParams()
  const { state } = useAuth()
  if (state.status !== 'authenticated') return null
  if (module === 'profile') return <Profile />
  const found = module ? findModule(state.user.role, module) : null
  if (!found || found.group.id !== 'account') return <NotFound />
  return (
    <ModulePlaceholder slug={found.module.slug} groupId={found.group.id} wave={found.module.wave} />
  )
}

function Home() {
  const { state } = useAuth()
  if (state.status === 'loading') return null
  return <Navigate to={state.status === 'authenticated' ? '/status' : '/sign-in'} replace />
}

export function AppRoutes() {
  const { state, retry } = useAuth()
  const version = useVersion()
  if (state.status === 'offline') {
    return (
      <PublicFrame>
        <Offline onRetry={retry} />
      </PublicFrame>
    )
  }
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/sign-in"
        element={
          <PublicFrame>
            <SignIn />
          </PublicFrame>
        }
      />
      <Route
        path="/about"
        element={
          <Frame>
            <About />
          </Frame>
        }
      />
      <Route
        path="/offline"
        element={
          <Frame>
            <Offline />
          </Frame>
        }
      />
      <Route
        path="/no-access"
        element={
          <Frame>
            <NoAccess />
          </Frame>
        }
      />
      <Route element={<RequireAuthBare />}>
        <Route
          path="/train/session/:id"
          element={
            <RoleGate roles={['trainee', 'instructor']}>
              <LiveSessionPage />
            </RoleGate>
          }
        />
      </Route>
      <Route element={<RequireAuth />}>
        <Route
          path="/train/session/:id/debrief"
          element={
            <RoleGate roles={['trainee', 'instructor']}>
              <Debrief />
            </RoleGate>
          }
        />
        <Route
          path="/train/lobby"
          element={
            <RoleGate roles={['trainee', 'instructor']}>
              <SessionLobby />
            </RoleGate>
          }
        />
        <Route
          path="/content/scenarios"
          element={
            <Authoring>
              <ScenarioLibrary />
            </Authoring>
          }
        />
        <Route
          path="/content/scenarios/editor"
          element={
            <Authoring>
              <ScenarioEditor />
            </Authoring>
          }
        />
        <Route
          path="/content/scenarios/editor/:id"
          element={
            <Authoring>
              <ScenarioEditor />
            </Authoring>
          }
        />
        <Route
          path="/content/generator"
          element={
            <Authoring>
              <GeneratorStudio />
            </Authoring>
          }
        />
        <Route path="/status" element={<Status />} />
        <Route path="/account/:module" element={<AccountModule />} />
        <Route path="/:role/:module" element={<RoleModule />} />
        {version.state.status === 'ready' && version.state.info.env === 'demo' && (
          <Route path="/dev/components" element={<DevComponents />} />
        )}
        {version.state.status === 'ready' && version.state.info.env === 'demo' && (
          <Route path="/bench" element={<Bench />} />
        )}
      </Route>
      <Route
        path="*"
        element={
          <Frame>
            <NotFound />
          </Frame>
        }
      />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <VersionProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </VersionProvider>
    </BrowserRouter>
  )
}
