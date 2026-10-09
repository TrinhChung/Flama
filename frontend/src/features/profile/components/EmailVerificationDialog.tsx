import { useEffect, useState } from 'react'
import { useTranslation, Trans } from 'react-i18next'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertCircle,
  CheckCircle2,
  GraduationCap,
  Loader2,
  Mail,
  RefreshCw,
  Send,
  ShieldCheck,
} from 'lucide-react'
import { toast } from 'sonner'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { profileApi } from '../api/profileApi'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import type { ProfileUser } from '../types/profile'

interface EmailVerificationDialogProps {
  user: ProfileUser
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function EmailVerificationDialog({
  user,
  open,
  onOpenChange,
}: EmailVerificationDialogProps) {
  const { t } = useTranslation('profile')
  const queryClient = useQueryClient()
  const [code, setCode] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [cooldownSeconds, setCooldownSeconds] = useState(0)
  const [codeSent, setCodeSent] = useState(false)

  // Countdown timer for resend
  useEffect(() => {
    if (cooldownSeconds <= 0) return
    const timer = setInterval(() => {
      setCooldownSeconds((prev) => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldownSeconds])

  // Reset states on modal close/open
  useEffect(() => {
    if (open) {
      setCode('')
      setErrorMessage(null)
      setSuccessMessage(null)
    }
  }, [open])

  const sendCodeMutation = useMutation({
    mutationFn: () => profileApi.requestEmailVerification(),
    onSuccess: (data) => {
      setCodeSent(true)
      setErrorMessage(null)
      setCooldownSeconds(60)
      if (data.already_verified) {
        toast.info(data.message || t('verify.toast.already_verified'))
        queryClient.invalidateQueries({ queryKey: ['profile'] })
        queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
        onOpenChange(false)
      } else {
        toast.success(data.message || t('verify.toast.code_sent'))
      }
    },
    onError: (error: any) => {
      const msg =
        error?.message ||
        t('verify.toast.send_code_failed')
      setErrorMessage(msg)
      toast.error(msg)
    },
  })

  const verifyMutation = useMutation({
    mutationFn: (otp: string) => profileApi.verifyEmail(otp),
    onSuccess: (data) => {
      setErrorMessage(null)
      setSuccessMessage(data.message || t('verify.toast.success'))
      toast.success(
        data.is_verified_student
          ? t('verify.toast.student_perk_success')
          : t('verify.toast.email_verified_success')
      )
      queryClient.invalidateQueries({ queryKey: ['profile'] })
      queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      setTimeout(() => {
        onOpenChange(false)
      }, 1500)
    },
    onError: (error: any) => {
      const msg =
        error?.message ||
        t('verify.toast.invalid_code')
      setErrorMessage(msg)
      toast.error(msg)
    },
  })

  const handleSendCode = () => {
    setErrorMessage(null)
    sendCodeMutation.mutate()
  }

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault()
    if (!code.trim()) {
      setErrorMessage(t('verify.validation_error'))
      return
    }
    setErrorMessage(null)
    verifyMutation.mutate(code.trim())
  }

  const isEdu =
    user.is_edu_email ||
    (user.email && user.email.toLowerCase().endsWith('.edu.vn'))

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md max-h-[90vh] overflow-y-auto p-4 sm:p-6">
        <DialogHeader>
          <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            {isEdu ? (
              <GraduationCap className="size-6 text-primary" />
            ) : (
              <ShieldCheck className="size-6 text-primary" />
            )}
          </div>
          <DialogTitle className="text-center text-lg sm:text-xl font-bold">
            {isEdu ? t('verify.title_edu') : t('verify.title_email')}
          </DialogTitle>
          <DialogDescription className="text-center text-xs">
            {t('verify.description_prompt')}{' '}
            <strong className="text-foreground break-all">{user.email}</strong>
          </DialogDescription>
        </DialogHeader>

        {isEdu && (
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs leading-relaxed text-foreground">
            <div className="flex items-start gap-2">
              <GraduationCap className="size-4 shrink-0 text-primary mt-0.5" />
              <span>
                <Trans
                  i18nKey="verify.edu_banner"
                  ns="profile"
                  components={{
                    strong: <strong className="text-primary font-semibold" />,
                  }}
                />
              </span>
            </div>
          </div>
        )}

        {errorMessage && (
          <Alert variant="destructive" className="py-2.5">
            <AlertCircle className="size-4" />
            <AlertDescription className="text-xs">{errorMessage}</AlertDescription>
          </Alert>
        )}

        {successMessage && (
          <Alert className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 py-2.5">
            <CheckCircle2 className="size-4 text-emerald-600" />
            <AlertDescription className="text-xs font-semibold">
              {successMessage}
            </AlertDescription>
          </Alert>
        )}

        {!codeSent ? (
          <div className="space-y-4 pt-2">
            <p className="text-center text-xs text-muted-foreground">
              {t('verify.send_instructions')}
            </p>
            <Button
              type="button"
              className="w-full font-bold cursor-pointer rounded-xl h-11 active:scale-[0.98]"
              onClick={handleSendCode}
              disabled={sendCodeMutation.isPending}
            >
              {sendCodeMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t('verify.btn_sending')}
                </>
              ) : (
                <>
                  <Send className="mr-2 size-4" />
                  {t('verify.btn_send')}
                </>
              )}
            </Button>
          </div>
        ) : (
          <form onSubmit={handleVerify} className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label htmlFor="otp_code" className="text-xs font-semibold">
                {t('verify.otp_label')}
              </Label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                <Input
                  id="otp_code"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={10}
                  placeholder={t('verify.otp_placeholder')}
                  autoFocus
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\s+/g, ''))}
                  className="pl-10 text-center font-mono text-xl font-bold tracking-widest rounded-xl h-12"
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full font-bold rounded-xl cursor-pointer h-11 active:scale-[0.98]"
              disabled={verifyMutation.isPending || !code.trim()}
            >
              {verifyMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  {t('verify.btn_verifying')}
                </>
              ) : (
                t('verify.btn_confirm')
              )}
            </Button>

            <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
              <span>{t('verify.not_received')}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-auto p-0 font-semibold text-primary hover:underline hover:bg-transparent"
                disabled={cooldownSeconds > 0 || sendCodeMutation.isPending}
                onClick={handleSendCode}
              >
                <RefreshCw
                  className={`mr-1 size-3.5 ${
                    sendCodeMutation.isPending ? 'animate-spin' : ''
                  }`}
                />
                {cooldownSeconds > 0
                  ? t('verify.resend_cooldown', { seconds: cooldownSeconds })
                  : t('verify.btn_resend')}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
