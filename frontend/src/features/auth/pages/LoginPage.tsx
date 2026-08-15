import { AlertCircle, ArrowRight, Eye, EyeOff, Lock, Mail, LoaderCircle } from 'lucide-react'
import { Navigate } from 'react-router-dom'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useBootstrap } from '@/shared/api/bootstrap'
import { AuthCard } from '../components/AuthCard'
import { useLoginForm } from '../hooks/useLoginForm'

export function LoginPage() {
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const { form, showPassword, toggleShowPassword, isPending, error, onSubmit } = useLoginForm()

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
      title="Chào mừng trở lại"
      description="Đăng nhập để tiếp tục phiên học và theo dõi tiến độ của bạn."
      alternateText="Chưa có tài khoản?"
      alternateLabel="Tạo tài khoản ngay"
      alternateTo="/register"
    >
      <form className="space-y-4" onSubmit={onSubmit}>
        {error ? (
          <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
            <AlertCircle className="size-4" />
            <AlertTitle>Đăng nhập không thành công</AlertTitle>
            <AlertDescription>{error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Email field */}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
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
          {form.formState.errors.email?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.email.message}</p>
          ) : null}
        </div>

        {/* Password field with Show/Hide toggle */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Mật khẩu</Label>
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            <Input
              id="password"
              type={showPassword ? 'text' : 'password'}
              placeholder="Nhập mật khẩu"
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
              aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {form.formState.errors.password?.message ? (
            <p className="text-xs font-medium text-destructive">{form.formState.errors.password.message}</p>
          ) : null}
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
              Đăng nhập
              <ArrowRight className="size-4 ml-1.5" />
            </>
          )}
        </Button>
      </form>
    </AuthCard>
  )
}
