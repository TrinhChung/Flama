import { useState } from 'react'
import { AlertCircle, CheckCircle2, Eye, EyeOff, Lock, LoaderCircle } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthCard } from '../components/AuthCard'
import { resetPassword } from '../api'

export function ResetPasswordPage() {
  const { t } = useTranslation('auth')
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isSuccess, setIsSuccess] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) {
      setError(t('reset.err_invalid_token'))
      return
    }

    if (newPassword.length < 6) {
      setError(t('reset.err_min_length'))
      return
    }

    if (newPassword !== confirmPassword) {
      setError(t('reset.err_mismatch'))
      return
    }

    setIsPending(true)
    setError(null)

    try {
      await resetPassword({
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      })
      setIsSuccess(true)
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : t('reset.default_error')
      setError(message)
    } finally {
      setIsPending(false)
    }
  }

  if (!token) {
    return (
      <AuthCard
        title={t('reset.missing_token_title')}
        description={t('reset.missing_token_desc')}
        alternateText={t('reset.missing_token_alt_text')}
        alternateLabel={t('reset.missing_token_alt_label')}
        alternateTo="/forgot-password"
      >
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>{t('reset.access_error_title')}</AlertTitle>
          <AlertDescription>
            {t('reset.missing_token_alert')}
          </AlertDescription>
        </Alert>

        <Button asChild className="w-full mt-4" variant="outline">
          <Link to="/forgot-password">{t('reset.resend_btn')}</Link>
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={t('reset.title')}
      description={t('reset.description')}
      alternateText={t('reset.alternate_text')}
      alternateLabel={t('reset.alternate_label')}
      alternateTo="/login"
    >
      {isSuccess ? (
        <div className="space-y-4 animate-in fade-in-50 duration-200">
          <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />
            <AlertTitle>{t('reset.success_title')}</AlertTitle>
            <AlertDescription className="text-sm mt-1">
              {t('reset.success_desc')}
            </AlertDescription>
          </Alert>

          <Button
            asChild
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md"
            size="lg"
          >
            <Link to="/login">{t('reset.login_now_btn')}</Link>
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error ? (
            <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
              <AlertCircle className="size-4" />
              <AlertTitle>{t('reset.error_title')}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {/* New password field */}
          <div className="space-y-2">
            <Label htmlFor="newPassword">{t('reset.new_password_label')}</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <Input
                id="newPassword"
                type={showPassword ? 'text' : 'password'}
                required
                placeholder="Ít nhất 6 ký tự"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="pl-9 pr-10"
                autoFocus
              />
              <button
                type="button"
                tabIndex={-1}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
              >
                {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>

          {/* Confirm password field */}
          <div className="space-y-2">
            <Label htmlFor="confirmPassword">{t('reset.confirm_new_label')}</Label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <Input
                id="confirmPassword"
                type={showPassword ? 'text' : 'password'}
                required
                placeholder="Nhập lại mật khẩu mới"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          <Button
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98]"
            size="lg"
            type="submit"
            disabled={isPending || !newPassword || !confirmPassword}
          >
            {isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              t('reset.submit_btn')
            )}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
