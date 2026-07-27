import { useState } from 'react'
import { AlertCircle, ArrowRight, Check, Eye, EyeOff, Lock, Mail, User, LoaderCircle, X } from 'lucide-react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBootstrap } from '@/shared/api/bootstrap'
import { register } from '../api'
import { registerSchema, type RegisterFormValues } from '../schemas'
import { AuthCard } from '../components/AuthCard'

export function RegisterPage() {
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { email: '', username: '', password: '', confirm_password: '' },
    mode: 'onChange',
  })

  const mutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      toast.success(result.message)
      navigate('/login', { replace: true })
    },
  })

  if (bootstrapQuery.isPending) {
    return (
      <div className="flex min-h-80 items-center justify-center">
        <LoaderCircle className="size-7 animate-spin text-primary" />
      </div>
    )
  }
  if (bootstrap?.user) return <Navigate to="/dashboard" replace />

  const passwordValue = form.watch('password') || ''
  const confirmPasswordValue = form.watch('confirm_password') || ''
  const isMinLength = passwordValue.length >= 8
  const isMatching = confirmPasswordValue.length > 0 && passwordValue === confirmPasswordValue

  return (
    <AuthCard
      title="Tạo tài khoản mới"
      description="Bắt đầu xây dựng bộ thẻ và lịch học thông minh của riêng bạn."
      alternateText="Đã có tài khoản?"
      alternateLabel="Đăng nhập ngay"
      alternateTo="/login"
    >
      <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
        {mutation.error ? (
          <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
            <AlertCircle className="size-4" />
            <AlertTitle>Đăng ký không thành công</AlertTitle>
            <AlertDescription>{mutation.error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Email */}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
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
          {form.formState.errors.email?.message ? (
            <p className="text-xs text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        {/* Username */}
        <div className="space-y-2">
          <Label htmlFor="username">Tên đăng nhập</Label>
          <div className="relative">
            <User className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="username"
              type="text"
              placeholder="Tên hiển thị của bạn"
              autoComplete="username"
              className="pl-9"
              aria-invalid={Boolean(form.formState.errors.username)}
              {...form.register('username')}
            />
          </div>
          {form.formState.errors.username?.message ? (
            <p className="text-xs text-destructive">{form.formState.errors.username.message}</p>
          ) : null}
        </div>

        {/* Password */}
        <div className="space-y-2">
          <Label htmlFor="password">Mật khẩu</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Ít nhất 8 ký tự"
              autoComplete="new-password"
              className="pl-9 pr-10"
              aria-invalid={Boolean(form.formState.errors.password)}
              {...form.register('password')}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.password?.message ? (
            <p className="text-xs text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
        </div>

        {/* Confirm Password */}
        <div className="space-y-2">
          <Label htmlFor="confirm_password">Xác nhận mật khẩu</Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              id="confirm_password"
              type={showConfirmPassword ? 'text' : 'password'}
              placeholder="Nhập lại mật khẩu"
              autoComplete="new-password"
              className="pl-9 pr-10"
              aria-invalid={Boolean(form.formState.errors.confirm_password)}
              {...form.register('confirm_password')}
            />
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShowConfirmPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              aria-label={showConfirmPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {showConfirmPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.confirm_password?.message ? (
            <p className="text-xs text-destructive">{form.formState.errors.confirm_password.message}</p>
          ) : null}
        </div>

        {/* Live Validation Hints */}
        {passwordValue.length > 0 ? (
          <div className="rounded-lg border bg-muted/30 p-2.5 text-xs space-y-1.5 animate-in fade-in-50 duration-200">
            <div className={`flex items-center gap-1.5 ${isMinLength ? 'text-emerald-600 font-medium' : 'text-muted-foreground'}`}>
              {isMinLength ? <Check className="size-3.5" /> : <X className="size-3.5 text-muted-foreground/60" />}
              <span>Mật khẩu ít nhất 8 ký tự</span>
            </div>
            {confirmPasswordValue.length > 0 ? (
              <div className={`flex items-center gap-1.5 ${isMatching ? 'text-emerald-600 font-medium' : 'text-destructive'}`}>
                {isMatching ? <Check className="size-3.5" /> : <X className="size-3.5" />}
                <span>Mật khẩu xác nhận trùng khớp</span>
              </div>
            ) : null}
          </div>
        ) : null}

        <Button
          className="w-full font-bold bg-gradient-to-r from-primary via-orange-500 to-amber-500 hover:opacity-95 text-primary-foreground shadow-md shadow-primary/20 transition-all hover:shadow-lg hover:shadow-primary/30"
          size="lg"
          type="submit"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <LoaderCircle className="size-4 animate-spin" />
          ) : (
            <>
              Tạo tài khoản
              <ArrowRight className="size-4 ml-1.5" />
            </>
          )}
        </Button>
      </form>
    </AuthCard>
  )
}
