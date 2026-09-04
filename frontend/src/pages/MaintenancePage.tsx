import { useCallback, useEffect, useState } from 'react'
import {
  ArrowLeft,
  Clock3,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import {
  clearBackendUnavailable,
  getMaintenanceReturnPath,
} from '@/shared/api/backendAvailability'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { Brand } from '@/shared/components/Brand'

const AUTO_RETRY_SECONDS = 30

export function MaintenancePage() {
  const [isRetrying, setIsRetrying] = useState(false)
  const [countdown, setCountdown] = useState(AUTO_RETRY_SECONDS)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const retryConnection = useCallback(async () => {
    if (isRetrying) return
    setIsRetrying(true)
    clearBackendUnavailable()
    await queryClient.resetQueries({
      queryKey: bootstrapQueryKey,
      exact: true,
    })
    navigate(getMaintenanceReturnPath(), { replace: true })
    // Reset state in case navigation stays on maintenance (backend still unreachable)
    setIsRetrying(false)
    setCountdown(AUTO_RETRY_SECONDS)
  }, [isRetrying, navigate, queryClient])

  // Countdown timer for automatic reconnection attempt
  useEffect(() => {
    if (isRetrying) return

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          void retryConnection()
          return AUTO_RETRY_SECONDS
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [isRetrying, retryConnection])

  // Keyboard shortcut: Press 'R' to retry
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (
        event.key.toLowerCase() === 'r' &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !(event.target instanceof HTMLInputElement) &&
        !(event.target instanceof HTMLTextAreaElement)
      ) {
        event.preventDefault()
        void retryConnection()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [retryConnection])

  return (
    <main className="relative isolate flex min-h-svh flex-col items-center justify-center overflow-hidden px-4 py-12 sm:px-6">
      <AmbientBackground intensity="subtle" />

      {/* Main card container with clean hairline border & refined elevation */}
      <section className="relative w-full max-w-xl rounded-2xl border border-border/80 bg-card/85 p-6 text-center shadow-xl shadow-black/[0.03] backdrop-blur-md sm:p-10 dark:border-border/50 dark:bg-card/75 dark:shadow-black/20">
        {/* Brand header */}
        <div className="mb-6 flex justify-center">
          <Brand
            size="md"
            className="hover:scale-100"
            to={getMaintenanceReturnPath()}
          />
        </div>

        {/* Live system status chip */}
        <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/25 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-800 dark:text-amber-300">
          <span className="relative flex size-2 shrink-0">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-amber-500" />
          </span>
          <span>Bảo dưỡng máy chủ định kỳ</span>
        </div>

        {/* Heading & description */}
        <h1 className="mt-4 text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
          Flama đang được nâng cấp
        </h1>
        <p className="mx-auto mt-3 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
          Chúng tôi đang tối ưu hiệu năng cơ sở dữ liệu để trải nghiệm học thẻ
          của bạn luôn mượt mà. Quá trình nâng cấp sẽ hoàn tất trong ít phút.
        </p>

        {/* System reassurance micro-cards */}
        <div className="my-7 grid grid-cols-1 gap-2.5 text-left sm:grid-cols-3">
          <div className="rounded-xl border border-border/60 bg-muted/40 p-3.5 transition-colors">
            <div className="flex items-center gap-2 text-foreground font-medium text-xs">
              <ShieldCheck className="size-4 text-primary shrink-0" />
              <span>Dữ liệu thẻ</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
              Bảo lưu 100% an toàn trên hệ thống.
            </p>
          </div>

          <div className="rounded-xl border border-border/60 bg-muted/40 p-3.5 transition-colors">
            <div className="flex items-center gap-2 text-foreground font-medium text-xs">
              <Clock3 className="size-4 text-primary shrink-0" />
              <span>Tiến độ SRS</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
              Lịch lặp lại ngắt quãng giữ nguyên vẹn.
            </p>
          </div>

          <div className="rounded-xl border border-border/60 bg-muted/40 p-3.5 transition-colors">
            <div className="flex items-center gap-2 text-foreground font-medium text-xs">
              <Sparkles className="size-4 text-primary shrink-0" />
              <span>Khôi phục</span>
            </div>
            <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">
              Tự đưa bạn về trang học dở khi xong.
            </p>
          </div>
        </div>

        {/* Action button & keyboard hint */}
        <div className="flex flex-col items-center gap-3">
          <Button
            type="button"
            size="lg"
            className="h-10 cursor-pointer rounded-xl px-5 font-semibold transition-all hover:shadow-sm"
            disabled={isRetrying}
            onClick={retryConnection}
          >
            <RefreshCw
              className={cn('size-4 shrink-0', isRetrying && 'animate-spin')}
            />
            <span>{isRetrying ? 'Đang kiểm tra lại…' : 'Thử kết nối lại'}</span>
            <kbd className="ml-1.5 hidden h-5 select-none items-center rounded border border-primary-foreground/30 bg-primary-foreground/15 px-1.5 font-mono text-[10px] font-semibold text-primary-foreground sm:inline-flex">
              R
            </kbd>
          </Button>

          {/* Auto retry countdown indicator */}
          <p className="text-xs text-muted-foreground">
            {isRetrying ? (
              'Đang gửi yêu cầu tới máy chủ…'
            ) : (
              <>
                Tự động kiểm tra lại sau{' '}
                <span className="font-semibold text-foreground">
                  {countdown}s
                </span>
              </>
            )}
          </p>
        </div>

        {/* Minimal return link */}
        <div className="mt-8 border-t border-border/50 pt-5">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            <span>Trở về trang giới thiệu Flama</span>
          </Link>
        </div>
      </section>
    </main>
  )
}

