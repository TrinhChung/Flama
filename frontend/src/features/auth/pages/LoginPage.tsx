import { useEffect } from 'react'
import { AlertCircle, ArrowRight, Eye, EyeOff, Lock, Mail, LoaderCircle } from 'lucide-react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBootstrap } from '@/shared/api/bootstrap'
import { resolveBackendUrl } from '@/config/env'
import { AuthCard } from '../components/AuthCard'
import { useLoginForm } from '../hooks/useLoginForm'
import { isBackendRoute, isSafeRedirectTarget } from '../utils/redirect'

export function LoginPage() {
  const { t } = useTranslation('auth')
  const [searchParams] = useSearchParams()
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const { form, showPassword, toggleShowPassword, isPending, error, onSubmit } = useLoginForm()

  const nextParam = searchParams.get('next')

  useEffect(() => {
    if (bootstrap?.user && isSafeRedirectTarget(nextParam) && isBackendRoute(nextParam)) {
      window.location.href = resolveBackendUrl(nextParam!)
    }
  }, [bootstrap?.user, nextParam])

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
      </div>
    )
  }

  if (bootstrap?.user) {
    if (isSafeRedirectTarget(nextParam)) {
      if (isBackendRoute(nextParam)) {
        return (
          <div className="flex min-h-80 items-center justify-center">
            <LoaderCircle className="size-7 animate-spin text-primary" />
          </div>
        )
      }
      return <Navigate to={nextParam!} replace />
    }
    return <Navigate to="/dashboard" replace />
  }

  const handleGoogleLogin = () => {
    const nextParam = searchParams.get('next')
    const relativePath = nextParam
      ? `/auth/google?next=${encodeURIComponent(nextParam)}`
      : '/auth/google'
    window.location.href = resolveBackendUrl(relativePath)
  }

  return (
    <AuthCard
      title={t('login.title')}
      description={t('login.description')}
      alternateText={t('login.alternate_text')}
      alternateLabel={t('login.alternate_label')}
      alternateTo="/register"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {error ? (
          <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
            <AlertCircle className="size-4" />
            <AlertTitle>{t('login.error_title')}</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Email field */}
        <div className="space-y-2">
          <Label htmlFor="email">{t('login.email_label')}</Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="email"
              type="email"
              placeholder={t('login.email_placeholder')}
              autoComplete="email"
              autoFocus
              className="pl-9"
              aria-invalid={Boolean(form.formState.errors.email)}
              {...form.register('email')}
            />
          </div>
          {form.formState.errors.email?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        {/* Password field with Show/Hide toggle */}
        <div className="space-y-2">
          <Label htmlFor="password">{t('login.password_label')}</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder={t('login.password_placeholder')}
              autoComplete="current-password"
              className="pl-9 pr-10"
              aria-invalid={Boolean(form.formState.errors.password)}
              {...form.register('password')}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={toggleShowPassword}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              aria-label={showPassword ? t('login.hide_password_aria') : t('login.show_password_aria')}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.password?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.password.message}</p>
          ) : null}

          <div className="flex justify-end pt-1">
            <Link to="/forgot-password" className="text-xs font-medium text-primary hover:underline transition-colors">
              {t('login.forgot_password_link')}
            </Link>
          </div>
        </div>

        <Button
          className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98]"
          size="lg"
          type="submit"
          disabled={isPending}
        >
          {isPending ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <>
              {t('login.submit_btn')}
              <ArrowRight className="size-4 ml-1.5" />
            </>
          )}
        </Button>

        <div className="relative my-4 flex items-center justify-center">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t border-border" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-card px-2 text-muted-foreground font-medium">{t('login.or_divider')}</span>
          </div>
        </div>

        <Button
          type="button"
          variant="outline"
          size="lg"
          className="w-full font-medium transition-all hover:bg-accent hover:text-accent-foreground active:scale-[0.98]"
          onClick={handleGoogleLogin}
        >
          <svg className="size-4 mr-2" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
            />
          </svg>
          {t('login.google_btn')}
        </Button>
      </form>
    </AuthCard>
  )
}
