import { useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  GraduationCap,
  LoaderCircle,
  Mail,
  RefreshCw,
  Send,
  ShieldCheck,
  User as UserIcon,
} from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { bootstrapQueryKey, useBootstrap } from '@/shared/api/bootstrap'
import { AuthCard } from '../components/AuthCard'
import { requestEmailVerification, verifyEmail } from '../api'

export function VerifyEmailPage() {
  const { t } = useTranslation('auth')
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()
  const initialCode = searchParams.get('code') || searchParams.get('token') || ''
  const emailParam = searchParams.get('email') || ''

  const bootstrapQuery = useBootstrap()
  const currentUser = bootstrapQuery.data?.user

  const [code, setCode] = useState(initialCode)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [cooldownSeconds, setCooldownSeconds] = useState(0)
  const [codeSent, setCodeSent] = useState(Boolean(initialCode))
  const [isVerifiedSuccess, setIsVerifiedSuccess] = useState(false)
  const [isStudentVerified, setIsStudentVerified] = useState(false)

  // Countdown timer for resend
  useEffect(() => {
    if (cooldownSeconds <= 0) return
    const timer = setInterval(() => {
      setCooldownSeconds((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldownSeconds])

  // Resolve target email
  const targetEmail = currentUser?.email || emailParam

  const isEdu = Boolean(
    targetEmail && targetEmail.toLowerCase().endsWith('.edu.vn')
  )

  // Auto-verify if code/token is provided in URL and user is authenticated
  useEffect(() => {
    if (initialCode && currentUser && !isVerifiedSuccess) {
      handleVerifyCode(initialCode)
    }
  }, [initialCode, currentUser])

  const sendCodeMutation = useMutation({
    mutationFn: () => requestEmailVerification(),
    onSuccess: (data) => {
      setCodeSent(true)
      setErrorMessage(null)
      setCooldownSeconds(data.expires_in_minutes ? 60 : 60)
      if (data.already_verified) {
        setIsVerifiedSuccess(true)
        toast.info(data.message || t('verify.already_verified_toast'))
        void queryClient.invalidateQueries({ queryKey: ['profile'] })
        void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      } else {
        toast.success(
          data.message || t('verify.sent_toast')
        )
      }
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error
          ? err.message
          : t('verify.send_error_toast')
      setErrorMessage(msg)
      toast.error(msg)
    },
  })

  const verifyMutation = useMutation({
    mutationFn: (otpCode: string) => verifyEmail(otpCode),
    onSuccess: (data) => {
      setErrorMessage(null)
      setIsVerifiedSuccess(true)
      setIsStudentVerified(Boolean(data.is_verified_student))
      setSuccessMessage(data.message || t('verify.success_title'))
      toast.success(
        data.is_verified_student
          ? t('verify.student_success')
          : t('verify.success_title')
      )
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      void queryClient.invalidateQueries({ queryKey: ['public-profile'] })
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error
          ? err.message
          : t('verify.invalid_code_toast')
      setErrorMessage(msg)
      toast.error(msg)
    },
  })

  const handleSendCode = () => {
    setErrorMessage(null)
    sendCodeMutation.mutate()
  }

  const handleVerifyCode = (codeToVerify: string) => {
    const clean = codeToVerify.trim()
    if (!clean) {
      setErrorMessage(t('verify.empty_code_msg'))
      return
    }
    setErrorMessage(null)
    verifyMutation.mutate(clean)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    handleVerifyCode(code)
  }

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
      </div>
    )
  }

  // Case: User not logged in and no code in URL
  if (!currentUser && !initialCode) {
    return (
      <AuthCard
        title={t('verify.unauth_title')}
        description={t('verify.unauth_description')}
        alternateText={t('verify.unauth_alt_text')}
        alternateLabel={t('verify.unauth_alt_label')}
        alternateTo="/register"
      >
        <div className="space-y-4 text-center">
          <div className="mx-auto flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            <Mail className="size-7" />
          </div>

          <p className="text-xs text-muted-foreground leading-relaxed">
            {t('verify.unauth_desc')}
          </p>

          <Button
            asChild
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md"
            size="lg"
          >
            <Link to="/login?next=/verify-email">
              {t('verify.login_to_verify')}
              <ArrowRight className="size-4 ml-1.5" />
            </Link>
          </Button>
        </div>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title={isEdu ? t('verify.title_student') : t('verify.title_general')}
      description={
        targetEmail
          ? t('verify.desc_with_email', { email: targetEmail })
          : t('verify.desc_general')
      }
      alternateText={t('verify.alt_check_info')}
      alternateLabel={t('verify.alt_view_profile')}
      alternateTo="/profile"
    >
      {isVerifiedSuccess ? (
        <div className="space-y-5 animate-in fade-in-50 duration-200">
          <Alert className="border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 py-3">
            <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400" />
            <AlertTitle className="text-sm font-bold">{t('verify.success_title')}</AlertTitle>
            <AlertDescription className="text-xs mt-1 leading-relaxed">
              {successMessage || t('verify.success_desc_default')}
            </AlertDescription>
          </Alert>

          {isStudentVerified || isEdu ? (
            <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-3.5 text-xs text-foreground space-y-2">
              <div className="flex items-center gap-2 font-bold text-blue-700 dark:text-blue-400">
                <GraduationCap className="size-4 text-blue-600 dark:text-blue-400" />
                <span>{t('verify.student_perks_title')}</span>
                <Badge className="bg-blue-600 text-white text-[10px] px-1.5 py-0 h-4">
                  {t('verify.student_badge')}
                </Badge>
              </div>
              <p className="text-muted-foreground text-[11px] leading-relaxed">
                {t('verify.student_perks_desc')}
              </p>
            </div>
          ) : null}

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
            <Button asChild variant="outline" className="w-full text-xs font-semibold">
              <Link to="/profile">
                <UserIcon className="mr-1.5 size-3.5" />
                {t('verify.btn_profile')}
              </Link>
            </Button>
            <Button
              asChild
              className="w-full font-bold bg-primary text-primary-foreground hover:bg-primary/90 shadow-xs text-xs"
            >
              <Link to="/dashboard">
                <ArrowRight className="mr-1.5 size-3.5" />
                {t('verify.btn_dashboard')}
              </Link>
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Student Banner */}
          {isEdu && (
            <div className="rounded-xl border border-primary/25 bg-primary/5 p-3 text-xs leading-relaxed text-foreground">
              <div className="flex items-start gap-2">
                <GraduationCap className="size-4 shrink-0 text-primary mt-0.5" />
                <span>
                  {t('verify.edu_banner_desc_prefix')}
                  <strong className="text-primary font-semibold">.edu.vn</strong>
                  {t('verify.edu_banner_desc_suffix')}
                </span>
              </div>
            </div>
          )}

          {/* Error Message */}
          {errorMessage && (
            <Alert variant="destructive" className="animate-in fade-in-50 duration-200 py-2.5">
              <AlertCircle className="size-4" />
              <AlertTitle className="text-xs font-bold">{t('verify.error_title')}</AlertTitle>
              <AlertDescription className="text-xs">{errorMessage}</AlertDescription>
            </Alert>
          )}

          {!codeSent ? (
            <div className="space-y-4 pt-1">
              <div className="rounded-xl border border-border/70 bg-muted/30 p-3.5 text-center space-y-1">
                <p className="text-xs text-muted-foreground">
                  {t('verify.recipient_box_label')}
                </p>
                <p className="font-bold text-foreground text-sm tracking-wide">
                  {targetEmail || t('verify.recipient_default')}
                </p>
              </div>

              <Button
                type="button"
                className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98] rounded-xl cursor-pointer"
                size="lg"
                onClick={handleSendCode}
                disabled={sendCodeMutation.isPending}
              >
                {sendCodeMutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    {t('verify.sending_code')}
                  </>
                ) : (
                  <>
                    <Send className="mr-2 size-4" />
                    {t('verify.send_code_btn')}
                  </>
                )}
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4 pt-1">
              <div className="space-y-2">
                <Label htmlFor="otp-input" className="text-xs font-semibold">
                  {t('verify.code_label')}
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <Input
                    id="otp-input"
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]*"
                    maxLength={10}
                    placeholder="123456"
                    autoFocus
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\s+/g, ''))}
                    className="pl-10 text-center font-mono text-xl font-bold tracking-widest rounded-xl h-12"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground text-center">
                  {t('verify.code_helper')}
                </p>
              </div>

              <Button
                type="submit"
                className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30 active:scale-[0.98] rounded-xl cursor-pointer"
                size="lg"
                disabled={verifyMutation.isPending || !code.trim()}
              >
                {verifyMutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    {t('verify.verifying_code')}
                  </>
                ) : (
                  <>
                    <ShieldCheck className="mr-2 size-4" />
                    {t('verify.submit_code')}
                  </>
                )}
              </Button>

              <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground border-t border-border/50">
                <span>{t('verify.resend_prompt')}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold text-primary hover:underline hover:bg-transparent cursor-pointer"
                  disabled={cooldownSeconds > 0 || sendCodeMutation.isPending}
                  onClick={handleSendCode}
                >
                  <RefreshCw
                    className={`mr-1 size-3.5 ${
                      sendCodeMutation.isPending ? 'animate-spin' : ''
                    }`}
                  />
                  {cooldownSeconds > 0
                    ? t('verify.resend_countdown', { seconds: cooldownSeconds })
                    : t('verify.resend_code')}
                </Button>
              </div>
            </form>
          )}
        </div>
      )}
    </AuthCard>
  )
}
