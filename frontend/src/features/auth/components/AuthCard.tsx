import type { ReactNode } from 'react'
import { Brain, Flame, Layers, ShieldCheck, Zap } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { Card } from '@/components/ui/card'
import { Brand } from '@/shared/components/Brand'

import { AmbientBackground } from '@/components/ambient-background'

type AuthCardProps = {
  title: string
  description: string
  alternateText: string
  alternateLabel: string
  alternateTo: string
  children: ReactNode
}

export function AuthCard({
  title,
  description,
  alternateText,
  alternateLabel,
  alternateTo,
  children,
}: AuthCardProps) {
  const location = useLocation()
  const searchParams = new URLSearchParams(location.search)
  const token = searchParams.get('token') || ''
  const hasToken = Boolean(token.trim())

  const isLogin = location.pathname.startsWith('/login')
  const isRegister = location.pathname.startsWith('/register')
  const isForgotPassword = location.pathname.startsWith('/forgot-password')
  const isResetPassword = location.pathname.startsWith('/reset-password')
  const isRecoveryMode = isForgotPassword || isResetPassword

  return (
    <div className="relative flex min-h-[calc(100svh-4rem)] items-center justify-center overflow-hidden px-4 py-10 lg:py-16">
      {/* Ambient background glow & grid pattern */}
      <AmbientBackground intensity="vibrant" />

      <div className="grid w-full max-w-md items-center gap-8 animate-in fade-in-50 slide-in-from-bottom-4 duration-500 lg:max-w-5xl lg:grid-cols-12 lg:gap-12">
        {/* Left Column (Brand Hero & Slogan) */}
        <div className="space-y-6 text-center lg:col-span-6 lg:space-y-8 lg:text-left">
          <div className="inline-flex items-center gap-2 rounded-2xl bg-primary/10 px-4 py-1.5 text-xs font-semibold text-primary">
            <Flame className="size-4 fill-primary" />
            Flama Study Platform
          </div>

          <div className="space-y-4">
            <Brand size="lg" className="justify-center lg:justify-start" />
            <h1 className="text-3xl font-extrabold tracking-tight text-balance leading-tight sm:text-4xl lg:text-5xl">
              Giữ <span className="bg-gradient-to-r from-primary via-orange-500 to-amber-500 bg-clip-text text-transparent">ngọn lửa</span> học tập cho mọi kiến thức.
            </h1>
            <p className="mx-auto max-w-lg text-base leading-relaxed text-muted-foreground lg:mx-0 lg:text-lg">
              Tự do sáng tạo bộ thẻ theo cách riêng và dùng Spaced Repetition để ghi nhớ từ vựng, IT, Y khoa, Luật hay bất kỳ môn học nào.
            </p>
          </div>

          {/* Feature Highlights on Desktop */}
          <div className="hidden grid-cols-2 gap-4 pt-2 lg:grid">
            <div className="flex items-start gap-3 rounded-2xl border border-border/50 bg-card/60 p-3.5 backdrop-blur-sm">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Zap className="size-4" />
              </span>
              <div>
                <h2 className="text-xs font-bold">Ôn tập ngắt quãng</h2>
                <p className="mt-0.5 text-[11px] text-muted-foreground">Scheduler tính toán nhịp ôn tối ưu</p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-2xl border border-border/50 bg-card/60 p-3.5 backdrop-blur-sm">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Brain className="size-4" />
              </span>
              <div>
                <h2 className="text-xs font-bold">Ghi nhớ dài hạn</h2>
                <p className="mt-0.5 text-[11px] text-muted-foreground">Tập trung vào các thẻ sắp quên</p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-2xl border border-border/50 bg-card/60 p-3.5 backdrop-blur-sm">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Layers className="size-4" />
              </span>
              <div>
                <h2 className="text-xs font-bold">Tạo thẻ linh hoạt</h2>
                <p className="mt-0.5 text-[11px] text-muted-foreground">NoteType tùy chỉnh & audio TTS</p>
              </div>
            </div>

            <div className="flex items-start gap-3 rounded-2xl border border-border/50 bg-card/60 p-3.5 backdrop-blur-sm">
              <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <ShieldCheck className="size-4" />
              </span>
              <div>
                <h2 className="text-xs font-bold">Bảo mật dữ liệu</h2>
                <p className="mt-0.5 text-[11px] text-muted-foreground">Tiến độ cá nhân luôn được giữ kín</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column (Auth Glass Card) */}
        <div className="mx-auto w-full max-w-md lg:col-span-6">
          <Card className="relative overflow-hidden rounded-3xl border border-primary/20 bg-card/90 shadow-2xl backdrop-blur-xl transition-all dark:bg-card/95">
            {/* Top subtle gradient accent line */}
            <div className="h-1 w-full bg-gradient-to-r from-transparent via-primary to-transparent opacity-80" />

            {/* Header with Segmented Pill Controller */}
            <div className="flex flex-col items-center space-y-4 border-b border-border/50 bg-muted/20 px-6 pt-6 pb-5 text-center">
              {/* Premium Pill Segmented Tab Controller */}
              <div
                className={`relative flex w-full items-center rounded-full border border-border/60 bg-muted/60 p-1 shadow-inner dark:bg-muted/40 ${
                  isRecoveryMode ? 'max-w-[290px]' : 'max-w-[260px]'
                }`}
              >
                {isRecoveryMode ? (
                  <>
                    <Link
                      to="/forgot-password"
                      className={`relative z-10 flex-1 rounded-full py-2 text-xs font-bold text-center transition-all duration-300 ${
                        isForgotPassword
                          ? 'text-primary-foreground shadow-md shadow-primary/25'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {isForgotPassword && (
                        <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 transition-all duration-300 animate-in fade-in-50" />
                      )}
                      Quên mật khẩu
                    </Link>

                    {hasToken ? (
                      <Link
                        to={{ pathname: '/reset-password', search: location.search }}
                        className={`relative z-10 flex-1 rounded-full py-2 text-xs font-bold text-center transition-all duration-300 ${
                          isResetPassword
                            ? 'text-primary-foreground shadow-md shadow-primary/25'
                            : 'text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {isResetPassword && (
                          <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 transition-all duration-300 animate-in fade-in-50" />
                        )}
                        Đặt lại mật khẩu
                      </Link>
                    ) : isResetPassword ? (
                      <div className="relative z-10 flex-1 rounded-full py-2 text-xs font-bold text-center text-primary-foreground shadow-md shadow-primary/25 select-none">
                        <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 transition-all duration-300 animate-in fade-in-50" />
                        Đặt lại mật khẩu
                      </div>
                    ) : (
                      <span
                        className="relative z-10 flex-1 rounded-full py-2 text-xs font-medium text-center text-muted-foreground/40 cursor-not-allowed select-none transition-colors"
                        title="Chỉ khả dụng khi mở liên kết xác thực từ email"
                        aria-disabled="true"
                      >
                        Đặt lại mật khẩu
                      </span>
                    )}
                  </>
                ) : (
                  <>
                    <Link
                      to="/login"
                      className={`relative z-10 flex-1 rounded-full py-2 text-xs font-bold text-center transition-all duration-300 ${
                        isLogin
                          ? 'text-primary-foreground shadow-md shadow-primary/25'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {isLogin && (
                        <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 transition-all duration-300 animate-in fade-in-50" />
                      )}
                      Đăng nhập
                    </Link>

                    <Link
                      to="/register"
                      className={`relative z-10 flex-1 rounded-full py-2 text-xs font-bold text-center transition-all duration-300 ${
                        isRegister
                          ? 'text-primary-foreground shadow-md shadow-primary/25'
                          : 'text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {isRegister && (
                        <span className="absolute inset-0 -z-10 rounded-full bg-gradient-to-r from-primary via-orange-500 to-amber-500 transition-all duration-300 animate-in fade-in-50" />
                      )}
                      Đăng ký
                    </Link>
                  </>
                )}
              </div>
            </div>

            {/* Card Body */}
            <div className="p-6 space-y-6 sm:p-8">
              <div className="space-y-1.5 text-center">
                <h2 className="text-2xl font-bold tracking-tight text-foreground">{title}</h2>
                <p className="text-sm text-muted-foreground leading-relaxed">{description}</p>
              </div>

              {children}

              <p className="border-t border-border/60 pt-4 text-center text-xs text-muted-foreground">
                {alternateText}{' '}
                <Link
                  className="font-semibold text-primary underline-offset-4 transition-colors hover:underline"
                  to={alternateTo}
                >
                  {alternateLabel}
                </Link>
              </p>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
