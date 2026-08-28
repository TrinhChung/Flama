import { useState } from 'react'
import { AlertCircle, ArrowLeft, CheckCircle2, LoaderCircle, Mail } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthCard } from '../components/AuthCard'
import { forgotPassword } from '../api'

export function ForgotPasswordPage() {
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
      setSuccessMessage(
        res.message ||
          'Nếu địa chỉ email tồn tại trong hệ thống, chúng tôi đã gửi liên kết đặt lại mật khẩu đến hộp thư của bạn.',
      )
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Có lỗi xảy ra khi gửi yêu cầu. Vui lòng thử lại.'
      setError(message)
    } finally {
      setIsPending(false)
    }
  }

  return (
    <AuthCard
      title="Khôi phục mật khẩu"
      description="Nhập địa chỉ email đăng ký để nhận liên kết đặt lại mật khẩu."
      alternateText="Nhớ mật khẩu?"
      alternateLabel="Quay lại Đăng nhập"
      alternateTo="/login"
    >
      {successMessage ? (
        <div className="space-y-4 animate-in fade-in-50 duration-200">
          <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />
            <AlertTitle>Đã gửi yêu cầu</AlertTitle>
            <AlertDescription className="text-sm mt-1">{successMessage}</AlertDescription>
          </Alert>

          <p className="text-xs text-muted-foreground text-center">
            Vui lòng kiểm tra kỹ hộp thư (bao gồm cả thư mục Spam/Quảng cáo).
          </p>

          <Button
            asChild
            variant="outline"
            className="w-full mt-2"
          >
            <a href="/login">
              <ArrowLeft className="size-4 mr-1.5" />
              Quay lại trang Đăng nhập
            </a>
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error ? (
            <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
              <AlertCircle className="size-4" />
              <AlertTitle>Không thể gửi yêu cầu</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="email">Địa chỉ Email đăng ký</Label>
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
              'Gửi liên kết khôi phục'
            )}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
