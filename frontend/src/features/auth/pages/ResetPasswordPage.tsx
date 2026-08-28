import { useState } from 'react'
import { AlertCircle, CheckCircle2, Eye, EyeOff, Lock, LoaderCircle } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { AuthCard } from '../components/AuthCard'
import { resetPassword } from '../api'

export function ResetPasswordPage() {
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
      setError('Liên kết không hợp lệ. Vui lòng kiểm tra lại email của bạn.')
      return
    }

    if (newPassword.length < 6) {
      setError('Mật khẩu mới phải có ít nhất 6 ký tự.')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Xác nhận mật khẩu mới không khớp.')
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
        err instanceof Error ? err.message : 'Đặt lại mật khẩu thất bại. Liên kết có thể đã hết hạn.'
      setError(message)
    } finally {
      setIsPending(false)
    }
  }

  if (!token) {
    return (
      <AuthCard
        title="Liên kết không hợp lệ"
        description="Không tìm thấy mã xác nhận đặt lại mật khẩu."
        alternateText="Cần gửi lại yêu cầu?"
        alternateLabel="Yêu cầu liên kết mới"
        alternateTo="/forgot-password"
      >
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>Lỗi truy cập</AlertTitle>
          <AlertDescription>
            Liên kết đặt lại mật khẩu thiếu tham số token. Vui lòng mở lại liên kết từ email hoặc gửi yêu cầu mới.
          </AlertDescription>
        </Alert>

        <Button asChild className="w-full mt-4" variant="outline">
          <a href="/forgot-password">Gửi lại yêu cầu mới</a>
        </Button>
      </AuthCard>
    )
  }

  return (
    <AuthCard
      title="Đặt lại mật khẩu mới"
      description="Nhập mật khẩu mới cho tài khoản Flama của bạn."
      alternateText="Nhớ mật khẩu cũ?"
      alternateLabel="Quay lại Đăng nhập"
      alternateTo="/login"
    >
      {isSuccess ? (
        <div className="space-y-4 animate-in fade-in-50 duration-200">
          <Alert className="border-emerald-500/50 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-4" />
            <AlertTitle>Thành công!</AlertTitle>
            <AlertDescription className="text-sm mt-1">
              Mật khẩu của bạn đã được cập nhật thành công. Bạn có thể sử dụng mật khẩu mới để đăng nhập ngay.
            </AlertDescription>
          </Alert>

          <Button
            asChild
            className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md"
            size="lg"
          >
            <a href="/login">Đăng nhập ngay</a>
          </Button>
        </div>
      ) : (
        <form className="space-y-4" onSubmit={handleSubmit}>
          {error ? (
            <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
              <AlertCircle className="size-4" />
              <AlertTitle>Đặt lại mật khẩu thất bại</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {/* New password field */}
          <div className="space-y-2">
            <Label htmlFor="newPassword">Mật khẩu mới</Label>
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
            <Label htmlFor="confirmPassword">Xác nhận mật khẩu mới</Label>
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
              'Cập nhật mật khẩu'
            )}
          </Button>
        </form>
      )}
    </AuthCard>
  )
}
