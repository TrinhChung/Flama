import { useEffect, useState } from 'react'
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
        toast.info(data.message || 'Email của bạn đã được xác thực trước đó.')
        queryClient.invalidateQueries({ queryKey: ['profile'] })
        queryClient.invalidateQueries({ queryKey: ['bootstrap'] })
        onOpenChange(false)
      } else {
        toast.success(data.message || 'Mã xác thực đã được gửi đến email của bạn.')
      }
    },
    onError: (error: any) => {
      const msg =
        error?.message ||
        'Không thể gửi mã xác thực. Vui lòng thử lại sau.'
      setErrorMessage(msg)
      toast.error(msg)
    },
  })

  const verifyMutation = useMutation({
    mutationFn: (otp: string) => profileApi.verifyEmail(otp),
    onSuccess: (data) => {
      setErrorMessage(null)
      setSuccessMessage(data.message || 'Xác thực email thành công!')
      toast.success(
        data.is_verified_student
          ? 'Chúc mừng! Bạn đã được kích hoạt ưu đãi Sinh viên thành công!'
          : 'Xác thực địa chỉ email thành công!'
      )
      queryClient.invalidateQueries({ queryKey: ['profile'] })
      queryClient.invalidateQueries({ queryKey: ['bootstrap'] })
      setTimeout(() => {
        onOpenChange(false)
      }, 1500)
    },
    onError: (error: any) => {
      const msg =
        error?.message ||
        'Mã xác thực không hợp lệ hoặc đã hết hạn.'
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
      setErrorMessage('Vui lòng nhập mã xác thực gồm 6 chữ số.')
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
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="mx-auto mb-2 flex size-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
            {isEdu ? (
              <GraduationCap className="size-6 text-primary" />
            ) : (
              <ShieldCheck className="size-6 text-primary" />
            )}
          </div>
          <DialogTitle className="text-center text-xl font-bold">
            {isEdu ? 'Xác thực Email Sinh viên' : 'Xác thực Địa chỉ Email'}
          </DialogTitle>
          <DialogDescription className="text-center text-xs">
            Mã xác thực 6 chữ số sẽ được gửi tới hòm thư:{' '}
            <strong className="text-foreground">{user.email}</strong>
          </DialogDescription>
        </DialogHeader>

        {isEdu && (
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs leading-relaxed text-foreground">
            <div className="flex items-start gap-2">
              <GraduationCap className="size-4 shrink-0 text-primary mt-0.5" />
              <span>
                Hệ thống phát hiện email trường học kết thúc bằng{' '}
                <strong className="text-primary font-semibold">.edu.vn</strong>.
                Sau khi xác thực, tài khoản của bạn sẽ nhận ngay huy hiệu Sinh viên và
                tự động áp dụng các ưu đãi giảm giá hoặc tải miễn phí trên Marketplace!
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
              Bấm nút bên dưới để nhận mã xác thực qua email. Mã có hiệu lực trong vòng 15 phút.
            </p>
            <Button
              type="button"
              className="w-full font-bold cursor-pointer rounded-xl"
              onClick={handleSendCode}
              disabled={sendCodeMutation.isPending}
            >
              {sendCodeMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Đang gửi mã...
                </>
              ) : (
                <>
                  <Send className="mr-2 size-4" />
                  Gửi mã xác thực đến email
                </>
              )}
            </Button>
          </div>
        ) : (
          <form onSubmit={handleVerify} className="space-y-4 pt-2">
            <div className="space-y-2">
              <Label htmlFor="otp_code" className="text-xs font-semibold">
                Nhập mã xác thực (6 chữ số)
              </Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                <Input
                  id="otp_code"
                  type="text"
                  maxLength={10}
                  placeholder="123456"
                  autoFocus
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\s+/g, ''))}
                  className="pl-9 text-center font-mono text-lg font-bold tracking-widest rounded-xl"
                />
              </div>
            </div>

            <Button
              type="submit"
              className="w-full font-bold rounded-xl cursor-pointer"
              disabled={verifyMutation.isPending || !code.trim()}
            >
              {verifyMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 size-4 animate-spin" />
                  Đang xác thực...
                </>
              ) : (
                'Xác nhận mã'
              )}
            </Button>

            <div className="flex items-center justify-between pt-1 text-xs text-muted-foreground">
              <span>Chưa nhận được mã?</span>
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
                  ? `Gửi lại sau (${cooldownSeconds}s)`
                  : 'Gửi lại mã'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}
