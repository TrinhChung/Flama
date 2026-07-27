import { useState } from 'react'
import { AlertCircle, ArrowRight, Eye, EyeOff, Lock, Mail, LoaderCircle } from 'lucide-react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { bootstrapQueryKey, useBootstrap } from '@/shared/api/bootstrap'
import type { FrontendBootstrap } from '@/shared/types/api'
import { login } from '../api'
import { loginSchema, type LoginFormValues } from '../schemas'
import { AuthCard } from '../components/AuthCard'

export function LoginPage() {
  const bootstrapQuery = useBootstrap()
  const bootstrap = bootstrapQuery.data
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const next = searchParams.get('next') || ''
  const [showPassword, setShowPassword] = useState(false)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  const mutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      queryClient.setQueryData<FrontendBootstrap>(
        bootstrapQueryKey,
        (current) => (current ? { ...current, user: result.user, messages: [] } : current),
      )
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      toast.success('Đăng nhập thành công.')
      if (next.startsWith('/') && !next.startsWith('//')) {
        navigate(next, { replace: true })
      } else if (result.redirect_to.startsWith('/app/')) {
        navigate(result.redirect_to.slice('/app'.length), { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
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

  return (
    <AuthCard
      title="Chào mừng trở lại"
      description="Đăng nhập để tiếp tục phiên học và theo dõi tiến độ của bạn."
      alternateText="Chưa có tài khoản?"
      alternateLabel="Tạo tài khoản ngay"
      alternateTo="/register"
    >
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit((values) => mutation.mutate({ ...values, next }))}
      >
        {mutation.error ? (
          <Alert variant="destructive" className="animate-in fade-in-50 duration-200">
            <AlertCircle className="size-4" />
            <AlertTitle>Đăng nhập không thành công</AlertTitle>
            <AlertDescription>{mutation.error.message}</AlertDescription>
          </Alert>
        ) : null}

        {/* Email field */}
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

        {/* Password field with Show/Hide toggle */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Mật khẩu</Label>
          </div>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
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
              Đăng nhập
              <ArrowRight className="size-4 ml-1.5" />
            </>
          )}
        </Button>
      </form>
    </AuthCard>
  )
}
