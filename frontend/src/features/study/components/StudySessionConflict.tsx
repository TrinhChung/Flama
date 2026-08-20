import { useEffect, useRef } from 'react'
import { ArrowRightLeft, LoaderCircle, LogOut, MonitorSmartphone } from 'lucide-react'
import { Button } from '@/components/ui/button'

export type StudySessionTakeoverState =
  | 'idle'
  | 'requesting'
  | 'waiting'
  | 'yielding'
  | 'unavailable'

type StudySessionConflictProps = {
  deckName?: string | null
  takeoverState: StudySessionTakeoverState
  onTakeover: () => void
  onLeave: () => void
}

export function StudySessionConflict({
  deckName,
  takeoverState,
  onTakeover,
  onLeave,
}: StudySessionConflictProps) {
  const titleRef = useRef<HTMLHeadingElement>(null)
  const unavailable = takeoverState === 'unavailable'
  const pending = takeoverState === 'requesting'
    || takeoverState === 'waiting'
    || takeoverState === 'yielding'

  useEffect(() => {
    titleRef.current?.focus()
  }, [])

  const statusMessage = takeoverState === 'waiting'
    ? 'Tab kia đã nhận yêu cầu. Đang hoàn tất thao tác hiện tại rồi chuyển phiên sang tab này…'
    : takeoverState === 'requesting'
      ? 'Đang yêu cầu tab kia bàn giao phiên học…'
      : takeoverState === 'yielding'
        ? 'Đang lưu xong thao tác hiện tại và bàn giao phiên này sang tab được yêu cầu…'
        : unavailable
          ? 'Tab kia chưa phản hồi. Hãy đóng hoặc rời tab kia nếu không còn dùng, rồi thử gửi lại. Khi tab kia đóng, phiên ở đây sẽ tự tiếp tục.'
          : 'Chuyển phiên để học tại tab này, hoặc rời màn hình này và tiếp tục học ở tab kia.'

  return (
    <section
      className="w-full max-w-xl mx-auto py-6 px-4"
      aria-labelledby="study-session-conflict-title"
      aria-describedby="study-session-conflict-description study-session-conflict-status"
    >
      <div className="rounded-2xl border border-amber-200/80 bg-card p-6 text-center shadow-xs space-y-6 dark:border-amber-900/50 sm:p-8">
        <div className="mx-auto inline-flex size-12 items-center justify-center rounded-xl border border-amber-200 bg-amber-500/10 text-amber-600 dark:border-amber-900/50 dark:text-amber-400">
          <MonitorSmartphone className="size-6" aria-hidden="true" />
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-muted-foreground">
            {deckName || 'Phiên học'}
          </div>
          <h1
            ref={titleRef}
            id="study-session-conflict-title"
            tabIndex={-1}
            className="text-2xl font-bold tracking-tight text-foreground outline-none"
          >
            Deck này đang được học ở tab khác
          </h1>
          <p
            id="study-session-conflict-description"
            className="mx-auto max-w-md text-sm leading-relaxed text-muted-foreground"
          >
            Mỗi deck chỉ được học trong một tab để tránh trùng câu trả lời hoặc ghi đè tiến độ.
            Dữ liệu đã lưu vẫn được giữ nguyên khi chuyển phiên.
          </p>
        </div>

        <div
          id="study-session-conflict-status"
          className="rounded-xl border border-amber-200 bg-amber-500/10 p-4 text-sm text-amber-800 dark:border-amber-900/50 dark:text-amber-200"
          role={unavailable ? 'alert' : 'status'}
          aria-live={unavailable ? 'assertive' : 'polite'}
          aria-atomic="true"
        >
          {statusMessage}
        </div>

        <div className="flex flex-col-reverse justify-center gap-3 sm:flex-row">
          <Button
            type="button"
            variant="outline"
            disabled={takeoverState === 'yielding'}
            onClick={onLeave}
            className="w-full sm:w-auto"
          >
            <LogOut className="mr-2 size-4" aria-hidden="true" />
            Rời phiên ở tab này
          </Button>
          <Button
            type="button"
            disabled={pending}
            onClick={onTakeover}
            className="w-full sm:w-auto"
            aria-busy={pending}
          >
            {pending ? (
              <LoaderCircle className="mr-2 size-4 animate-spin" aria-hidden="true" />
            ) : (
              <ArrowRightLeft className="mr-2 size-4" aria-hidden="true" />
            )}
            {pending
              ? 'Đang chuyển phiên…'
              : unavailable
                ? 'Gửi lại yêu cầu'
                : 'Chuyển phiên sang tab này'}
          </Button>
        </div>
      </div>
    </section>
  )
}
