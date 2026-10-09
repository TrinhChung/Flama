import { AlertTriangle, Check, Clock3, RefreshCcw, Send, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import '@/shared/config/i18n'
import type { ChangeRequestStatus } from '../types'

const STATUS_CLASSES: Record<ChangeRequestStatus, string> = {
  needs_sync: 'border-blue-500/35 bg-blue-500/10 text-blue-700 dark:text-blue-300',
  draft: 'border-border bg-muted text-foreground',
  has_conflict: 'border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200',
  pending_review: 'border-violet-500/35 bg-violet-500/10 text-violet-700 dark:text-violet-300',
  rejected: 'border-red-500/35 bg-red-500/10 text-red-700 dark:text-red-300',
  merged: 'border-emerald-500/35 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
}

const DEFAULT_LABELS: Record<ChangeRequestStatus, string> = {
  needs_sync: 'Cần đồng bộ',
  draft: 'Bản nháp',
  has_conflict: 'Có xung đột',
  pending_review: 'Chờ duyệt',
  rejected: 'Đã từ chối',
  merged: 'Đã merge',
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
  const { t } = useTranslation('collaboration')
  const label = t(`status.${status}`, DEFAULT_LABELS[status])

  return (
    <Badge variant="outline" className={cn('border', STATUS_CLASSES[status], className)}>
      <StatusIcon status={status} />
      {label}
    </Badge>
  )
}
