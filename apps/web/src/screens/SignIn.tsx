import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import brand from '../../../../brand.json'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useVersion } from '../lib/version'
import { setTeamRole, type TeamRole } from '../lib/viewRole'
import { BrandMark } from '../ui/BrandMark'
import { Button } from '../ui/Button'
import { Input } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'

/** The seeded demo accounts (the seed command creates one per account role); the commander seat is a trainee account. */
const DEMO_SEATS: { id: string; email: string; team: TeamRole }[] = [
  { id: 'operator', email: 'trainee@demo.invalid', team: 'operator' },
  { id: 'commander', email: 'trainee@demo.invalid', team: 'commander' },
  { id: 'instructor', email: 'instructor@demo.invalid', team: 'operator' },
  { id: 'admin', email: 'admin@demo.invalid', team: 'operator' },
]

export function SignIn() {
  const { t } = useTranslation()
  const auth = useAuth()
  const version = useVersion()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [failure, setFailure] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  if (auth.state.status === 'authenticated') return <Navigate to="/status" replace />

  const from = (location.state as { from?: string } | null)?.from ?? '/status'
  const demo = version.state.status === 'ready' && version.state.info.env === 'demo'

  const signIn = async (address: string, secret: string) => {
    setPending(true)
    try {
      await auth.login(address, secret)
      navigate(from, { replace: true })
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        setFailure(t('signIn.tooMany', { seconds: error.retryAfter ?? 60 }))
      } else if (error instanceof ApiError && error.status === 401) {
        setFailure(t('signIn.invalid'))
      } else {
        setFailure(t('signIn.unreachable'))
      }
    } finally {
      setPending(false)
    }
  }

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const next = {
      email: email.trim() ? undefined : t('signIn.emailRequired'),
      password: password ? undefined : t('signIn.passwordRequired'),
    }
    setErrors(next)
    setFailure(null)
    if (next.email || next.password) return
    await signIn(email.trim(), password)
  }

  /** Demo builds only: pick a seat to fill in its demo account (and sign in when the build carries the demo password). */
  const pickRole = async (seat: (typeof DEMO_SEATS)[number]) => {
    setTeamRole(seat.team)
    setEmail(seat.email)
    setErrors({})
    setFailure(null)
    const secret = import.meta.env.VITE_DEMO_PASSWORD as string | undefined
    if (secret) {
      setPassword(secret)
      await signIn(seat.email, secret)
    } else {
      setPassword('')
    }
  }

  return (
    <div className="mx-auto grid w-full max-w-[960px] flex-1 grid-cols-1 content-center gap-12 lg:grid-cols-[minmax(0,1fr)_400px]">
      <section aria-label={brand.productName} className="flex flex-col justify-center gap-4">
        <BrandMark size={48} />
        <div>
          <p className="m-0 text-lg font-semibold tracking-[0.14em]">{brand.productName}</p>
          <p className="m-0 text-md text-ink-2">{brand.descriptor}</p>
        </div>
        <p className="m-0 border-l-2 border-signal pl-3 text-md">{t('signIn.tagline')}</p>
      </section>

      <section className="flex flex-col justify-center">
        <form
          onSubmit={submit}
          noValidate
          className="flex flex-col gap-4 border border-line bg-surface-1 p-6"
        >
          <h1 className="m-0 text-lg font-semibold">{t('signIn.title')}</h1>
          <p className="m-0 text-sm text-ink-2">{t('signIn.intro')}</p>
          {failure && <InlineAlert tone="error">{failure}</InlineAlert>}
          <Input
            label={t('signIn.email')}
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errors.email}
          />
          <Input
            label={t('signIn.password')}
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <Button type="submit" variant="primary" disabled={pending}>
            {pending ? t('signIn.submitting') : t('signIn.submit')}
          </Button>
          {demo && (
            <fieldset className="m-0 flex flex-col gap-2 border border-line p-3">
              <legend className="micro-label px-1">{t('signIn.seat')}</legend>
              <div className="grid grid-cols-2 gap-2">
                {DEMO_SEATS.map((seat) => (
                  <Button key={seat.id} disabled={pending} onClick={() => void pickRole(seat)}>
                    {t(`signIn.seats.${seat.id}`)}
                  </Button>
                ))}
              </div>
              <p className="m-0 text-xs text-ink-2">{t('signIn.demoHint')}</p>
            </fieldset>
          )}
        </form>
      </section>
    </div>
  )
}
