import type { ComponentType } from 'react'
import { CheckCircle2, AlertTriangle, Sparkles } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { DependencyStatusBadgeProps } from '../model/types'

interface StatusDetail {
  label: string
  icon: ComponentType<{ className?: string }>
  className: string
}

const STATUS_MAP: Record<string, StatusDetail> = {
  synced: {
    label: 'Synced',
    icon: CheckCircle2,
    className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  },
  update_available: {
    label: 'Update Available',
    icon: AlertTriangle,
    className: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  },
  draft_changes: {
    label: 'Draft Changes',
    icon: Sparkles,
    className: 'border-purple-500/30 bg-purple-500/10 text-purple-700 dark:text-purple-300',
  },
}

export function DependencyStatusBadge({
  status,
  className,
  showIcon = true,
  size = 'default',
  customLabel,
}: DependencyStatusBadgeProps) {
  const normalizedKey = (status || '').toLowerCase().replace(/[-\s]+/g, '_')
  const config = STATUS_MAP[normalizedKey] ?? {
    label: status || 'Unknown',
    icon: AlertTriangle,
    className: 'border-border bg-muted/30 text-muted-foreground',
  }

  const IconComponent = config.icon
  const displayLabel = customLabel ?? config.label

  return (
    <Badge
      variant="outline"
      data-status={normalizedKey}
      className={cn(
        'inline-flex items-center gap-1 font-medium transition-colors',
        size === 'sm' ? 'px-1.5 py-0.5 text-[10px] h-4' : 'px-2 py-0.5 text-xs h-5',
        config.className,
        className
      )}
    >
      {showIcon && <IconComponent className={cn(size === 'sm' ? 'size-2.5' : 'size-3')} />}
      <span>{displayLabel}</span>
    </Badge>
  )
}
