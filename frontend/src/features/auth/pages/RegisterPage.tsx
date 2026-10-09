import { AlertCircle, ArrowRight, Check, Eye, EyeOff, GraduationCap, Lock, Mail, User, LoaderCircle, X } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBootstrap } from '@/shared/api/bootstrap'
import { AuthCard } from '../components/AuthCard'
import { useRegisterForm } from '../hooks/useRegisterForm'

export function RegisterPage() {
  const { t } = useTranslation('auth')
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const {
    form,
    showPassword,
    toggleShowPassword,
    showConfirmPassword,
    toggleShowConfirmPassword,
    isPending,
    error,
    passwordValue,
    confirmPasswordValue,
    isMinLength,
    isMatching,
    onSubmit,
  } = useRegisterForm()

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
      </div>
    )
  }

  if (bootstrap?.user) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <AuthCard
      title={t('register.title')}
      description={t('register.description')}
      alternateText={t('register.alternate_text')}
      alternateLabel={t('register.alternate_label')}
      alternateTo="/login"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {error ? (
          <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
            <AlertCircle className="size-4" />
            <AlertTitle>{t('register.error_title')}</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Email */}
        <div className="space-y-2">
          <Label htmlFor="email">{t('register.email_label')}</Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              autoComplete="email"
              autoFocus
              className="pl-9"
              aria-invalid={Boolean(form.formState.errors.email)}
              {...form.register('email')}
            />
          </div>
          <p className="text-[11px] leading-relaxed text-muted-foreground/85 flex items-start gap-1.5 pt-0.5">
            <GraduationCap className="size-3.5 shrink-0 text-primary/80 mt-0.5" />
            <span>
              {t('register.student_hint_prefix')}
              <code className="text-[10px] font-semibold bg-muted px-1 py-0.5 rounded text-foreground">.edu.vn</code>
              {t('register.student_hint_suffix')}
            </span>
          </p>
          {form.formState.errors.email?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        {/* Username */}
        <div className="space-y-2">
          <Label htmlFor="username">{t('register.username_label')}</Label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="username"
              type="text"
              placeholder={t('register.username_placeholder')}
              autoComplete="username"
              className="pl-9"
              aria-invalid={Boolean(form.formState.errors.username)}
              {...form.register('username')}
            />
          </div>
          {form.formState.errors.username?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.username.message}</p>
          ) : null}
        </div>

        {/* Password */}
        <div className="space-y-2">
          <Label htmlFor="password">{t('register.password_label')}</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder={t('register.password_placeholder')}
              autoComplete="new-password"
              className="pl-9 pr-10"
              aria-invalid={Boolean(form.formState.errors.password)}
              {...form.register('password')}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={toggleShowPassword}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.password?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>

        {/* Confirm Password */}
        <div className="space-y-2">
          <Label htmlFor="confirm_password">{t('register.confirm_label')}</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="confirm_password"
              type={showConfirmPassword ? 'text' : 'password'}
              placeholder={t('register.confirm_placeholder')}
              autoComplete="new-password"
              className="pl-9 pr-10"
              aria-invalid={Boolean(form.formState.errors.confirm_password)}
              {...form.register('confirm_password')}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={toggleShowConfirmPassword}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              aria-label={showConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {showConfirmPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.confirm_password?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.confirm_password.message}</p>
          ) : null}
        </div>

        {/* Live Validation Hints */}
        {passwordValue.length > 0 ? (
          <div className="rounded-xl border border-border/70 bg-muted/40 p-3 text-xs space-y-1.5 animate-in fade-in-50 duration-200">
            <div className={`flex items-center gap-2 ${isMinLength ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-muted-foreground'}`}>
              {isMinLength ? <Check className="size-3.5" /> : <X className="size-3.5 text-muted-foreground/60" />}
              <span>{t('register.check_min_length')}</span>
            </div>
            {confirmPasswordValue.length > 0 ? (
              <div className={`flex items-center gap-2 ${isMatching ? 'text-emerald-600 dark:text-emerald-400 font-medium' : 'text-destructive'}`}>
                {isMatching ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                <span>{t('register.check_matching')}</span>
              </div>
            ) : null}
          </div>
        ) : null}

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
              {t('register.submit_btn')}
              <ArrowRight className="size-4 ml-1.5" />
            </>
          )}
        </Button>
      </form>
    </AuthCard>
  )
}
