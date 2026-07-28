import { AlertCircle, Inbox, LoaderCircle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

export function PageLoading({ label = 'Đang tải dữ liệu…' }: { label?: string }) {
  return (
    <div className="flex min-h-72 flex-col items-center justify-center gap-3 text-muted-foreground">
      <LoaderCircle className="size-7 animate-spin text-primary" />
      <p className="text-sm">{label}</p>
    </div>
  )
}

export function PageError({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : 'Đã xảy ra lỗi không xác định.'
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertTitle>Không thể tải dữ liệu</AlertTitle>
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center gap-2 rounded-xl border border-dashed bg-muted/25 p-8 text-center">
      <div className="mb-2 rounded-full bg-muted p-3 text-muted-foreground">
        <Inbox className="size-5" />
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="max-w-xl text-sm text-muted-foreground">{description}</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </div>
  )
}
