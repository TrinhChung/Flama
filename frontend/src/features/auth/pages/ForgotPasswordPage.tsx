import { useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, LoaderCircle, Mail } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthCard } from '../components/AuthCard'
import { forgotPassword } from '../api'

export function ForgotPasswordPage() {
  const { t } = useTranslation('auth')
  const [email, setEmail] = useState('')
  const [isPending, setIsPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return

    setIsPending(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const res = await forgotPassword({ email: email.trim() })
      setSuccessMessage(res.message || t('forgot.default_success_desc'))
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : t('forgot.default_error')
      setError(message)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <AuthCard
      title={t('forgot.title')}
      description={t('forgot.description')}
      alternateText={t('forgot.alternate_text')}
      alternateLabel={t('forgot.alternate_label')}
      alternateTo="/login"
    >
      {successMessage ? (
        <div className="space-y-4 animate-in fade-in-50 duration-200">
          <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />
            <AlertTitle>{t('forgot.success_title')}</AlertTitle>
            <AlertDescription className="text-sm mt-1">{successMessage}</AlertDescription>
          </Alert>

          <p className="text-xs text-muted-foreground text-center">
            {t('forgot.check_spam_hint')}
          </p>

          <Button
            asChild
            variant="outline"
            className="w-full mt-2"
          >
            <Link to="/login">
              <ArrowLeft className="size-4 mr-1.5" />
              {t('forgot.back_to_login_btn')}
            </Link>
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error ? (
            <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
              <AlertCircle className="size-4" />
              <AlertTitle>{t('forgot.error_title')}</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="email">{t('forgot.email_label')}</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
              <Input
                id="email"
                type="email"
                required
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="pl-9"
                autoFocus
              />
            </div>
          </div>

          <Button
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98]"
            size="lg"
            type="submit"
            disabled={isPending || !email.trim()}
          >
            {isPending ? (
              <LoaderCircle className="size-4 animate-spin" />
            ) : (
              t('forgot.submit_btn')
            )}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
