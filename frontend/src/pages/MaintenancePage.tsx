import { useState } from 'react'
import { Clock3, RefreshCw, ServerOff } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { AmbientBackground } from '@/components/ambient-background'
import { Button } from '@/components/ui/button'
import {
  clearBackendUnavailable,
  getMaintenanceReturnPath,
} from '@/shared/api/backendAvailability'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import { Brand } from '@/shared/components/Brand'

export function MaintenancePage() {
  const [isRetrying, setIsRetrying] = useState(false)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  async function retryConnection() {
    setIsRetrying(true)
    clearBackendUnavailable()
    await queryClient.resetQueries({
      queryKey: bootstrapQueryKey,
      exact: true,
    })
    navigate(getMaintenanceReturnPath(), { replace: true })
  }

  return (
    <main className="relative isolate flex min-h-svh items-center justify-center overflow-hidden px-5 py-12">
      <AmbientBackground intensity="vibrant" />

      <div
        aria-hidden="true"
        className="absolute top-[12%] left-[8%] size-48 rounded-full bg-primary/10 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="absolute right-[6%] bottom-[10%] size-56 rounded-full bg-amber-400/10 blur-3xl"
      />

      <section className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-border/70 bg-card/90 px-6 py-10 text-center shadow-2xl shadow-primary/10 backdrop-blur-xl sm:px-12 sm:py-14">
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-transparent via-primary to-transparent" />

        <Brand
          size="lg"
          className="mb-9 justify-center hover:scale-100"
        />

        <div className="mx-auto mb-7 flex size-24 items-center justify-center rounded-full border border-primary/20 bg-primary/8 shadow-inner shadow-primary/10">
          <div className="relative flex size-16 items-center justify-center rounded-2xl bg-background shadow-lg">
            <span className="absolute top-1.5 right-1.5 size-2.5 rounded-full bg-amber-500">
              <span className="absolute inset-0 animate-ping rounded-full bg-amber-500 opacity-60" />
            </span>
            <ServerOff className="size-8 text-primary" strokeWidth={1.8} />
          </div>
        </div>

        <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-amber-500/20 bg-amber-500/8 px-3 py-1 text-[11px] font-bold tracking-[0.14em] text-amber-700 uppercase dark:text-amber-300">
          <Clock3 className="size-3.5" />
          Kết nối tạm gián đoạn
        </div>

        <h1 className="text-3xl font-black tracking-tight text-foreground sm:text-4xl">
          Máy chủ đang bảo trì
        </h1>
        <p className="mx-auto mt-4 max-w-lg text-sm leading-6 text-muted-foreground sm:text-base sm:leading-7">
          Flama hiện chưa thể kết nối tới máy chủ. Hệ thống có thể đang được
          cập nhật hoặc tạm thời chưa sẵn sàng. Bạn vui lòng thử lại sau ít
          phút.
        </p>

        <Button
          type="button"
          size="lg"
          className="mt-8 h-11 rounded-xl px-6 font-bold shadow-lg shadow-primary/20"
          disabled={isRetrying}
          onClick={retryConnection}
        >
          <RefreshCw className={isRetrying ? 'animate-spin' : ''} />
          {isRetrying ? 'Đang kết nối lại…' : 'Thử kết nối lại'}
        </Button>

        <p className="mt-6 text-xs leading-5 text-muted-foreground">
          Khi máy chủ hoạt động trở lại, Flama sẽ đưa bạn về màn hình đang sử
          dụng trước đó.
        </p>
      </section>
    </main>
  )
}
