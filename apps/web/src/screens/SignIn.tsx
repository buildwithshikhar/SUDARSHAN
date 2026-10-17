import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import brand from '../../../../brand.json'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { useVersion } from '../lib/version'
import { BrandMark } from '../ui/BrandMark'
import { Button } from '../ui/Button'
import { Input } from '../ui/Field'
import { InlineAlert } from '../ui/InlineAlert'

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

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const next = {
      email: email.trim() ? undefined : t('signIn.emailRequired'),
      password: password ? undefined : t('signIn.passwordRequired'),
    }
    setErrors(next)
    setFailure(null)
    if (next.email || next.password) return
    setPending(true)
    try {
      await auth.login(email.trim(), password)
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
          {demo && <InlineAlert tone="info">{t('signIn.demoHint')}</InlineAlert>}
        </form>
        <p className="mt-3 text-sm">
          <Link to="/about">{t('signIn.about')}</Link>
        </p>
      </section>
    </div>
  )
}
