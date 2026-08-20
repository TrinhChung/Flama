import { AlertTriangle, Check, Clock3, RefreshCcw, Send, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { ChangeRequestStatus } from '../types'

const STATUS_META: Record<ChangeRequestStatus, {
  label: string
  className: string
}> = {
  needs_sync: {
    label: 'Cần đồng bộ',
    className: 'border-blue-500/35 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  },
  draft: {
    label: 'Bản nháp',
    className: 'border-border bg-muted text-foreground',
  },
  has_conflict: {
    label: 'Có xung đột',
    className: 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  },
  pending_review: {
    label: 'Chờ duyệt',
    className: 'border-violet-500/35 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  },
  rejected: {
    label: 'Đã từ chối',
    className: 'border-red-500/35 bg-red-500/10 text-red-700 dark:text-red-300',
  },
  merged: {
    label: 'Đã merge',
    className: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  },
}

function StatusIcon({ status }: { status: ChangeRequestStatus }) {
  if (status === 'needs_sync') return <RefreshCcw />
  if (status === 'has_conflict') return <AlertTriangle />
  if (status === 'pending_review') return <Send />
  if (status === 'rejected') return <X />
  if (status === 'merged') return <Check />
  return <Clock3 />
}

export function ChangeRequestStatusBadge({
  status,
  className,
}: {
  status: ChangeRequestStatus
  className?: string
}) {
  const meta = STATUS_META[status]
  return (
    <Badge variant="outline" className={cn('border', meta.className, className)}>
      <StatusIcon status={status} />
      {meta.label}
    </Badge>
  )
}
