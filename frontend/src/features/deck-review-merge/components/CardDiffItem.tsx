import { useState, type MouseEvent } from 'react'
import {
  CheckSquare,
  Square,
  ChevronDown,
  ChevronUp,
  PlusCircle,
  Edit3,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { CardDiffItemProps } from '../model/types'

export function CardDiffItem({
  item,
  isSelected,
  onToggle,
  className = '',
}: CardDiffItemProps) {
  const [isDetailsExpanded, setIsDetailsExpanded] = useState(false)

  const handleCheckboxClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation()
    onToggle(item.id, e.shiftKey)
  }

  const changeTypeConfig = {
    added: {
      label: 'Thêm mới',
      icon: PlusCircle,
      badgeClass:
        'text-emerald-700 bg-emerald-500/10 border-emerald-500/20 dark:text-emerald-300',
    },
    modified: {
      label: 'Đã sửa',
      icon: Edit3,
      badgeClass:
        'text-amber-800 bg-amber-500/10 border-amber-500/20 dark:text-amber-300',
    },
    removed: {
      label: 'Đã xóa',
      icon: Trash2,
      badgeClass: 'text-rose-700 bg-rose-500/10 border-rose-500/20 dark:text-rose-300',
    },
    conflict: {
      label: 'Xung đột',
      icon: AlertTriangle,
      badgeClass:
        'text-amber-700 bg-amber-500/10 border-amber-500/20 dark:text-amber-300',
    },
  }[item.changeType] || {
    label: item.changeType,
    icon: Edit3,
    badgeClass: 'text-muted-foreground bg-muted border-border',
  }

  const ChangeIcon = changeTypeConfig.icon
  const hasFieldDiffs = Boolean(item.fieldDiffs && item.fieldDiffs.length > 0)

  return (
    <div
      className={`group rounded-xl border border-border/80 bg-card p-3 transition-all hover:border-border hover:shadow-xs ${
        isSelected ? 'bg-primary/5 border-primary/40' : ''
      } ${className}`}
      data-testid={`card-diff-item-${item.id}`}
    >
      {/* Main card row */}
      <div className="flex items-start gap-3">
        {/* Selection Checkbox */}
        <button
          type="button"
          onClick={handleCheckboxClick}
          className="mt-0.5 shrink-0 rounded min-h-[44px] min-w-[44px] inline-flex items-center justify-center -m-2 p-2 rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring cursor-pointer"
          aria-label={isSelected ? `Bỏ chọn thẻ ${item.primaryText}` : `Chọn thẻ ${item.primaryText}`}
          data-testid={`card-checkbox-${item.id}`}
        >
          {isSelected ? (
            <CheckSquare className="size-4 text-primary" />
          ) : (
            <Square className="size-4" />
          )}
        </button>

        {/* Content & Metadata */}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {/* Primary & Secondary Texts */}
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-2">
                <span
                  className="font-semibold text-sm text-foreground truncate"
                  title={item.primaryText || item.noteId}
                >
                  {item.primaryText || item.noteId}
                </span>
                {item.secondaryText && (
                  <span
                    className="text-xs text-muted-foreground truncate"
                    title={item.secondaryText}
                  >
                    · {item.secondaryText}
                  </span>
                )}
              </div>
              <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                <span>{item.noteTypeName}</span>
                {item.status && item.status !== 'pending' && (
                  <Badge
                    variant="outline"
                    className={`text-[9px] h-3.5 px-1 ${
                      item.status === 'approved'
                        ? 'text-emerald-700 dark:text-emerald-300 border-emerald-500/30 bg-emerald-500/10'
                        : 'text-rose-700 dark:text-rose-300 border-rose-500/30 bg-rose-500/10'
                    }`}
                  >
                    {item.status === 'approved' ? 'Đã duyệt' : 'Đã từ chối'}
                  </Badge>
                )}
              </div>
            </div>

            {/* Badges & Actions */}
            <div className="flex items-center gap-2 shrink-0">
              {/* Change Type Badge */}
              <Badge
                variant="outline"
                className={`text-[10px] h-5 gap-1 font-medium capitalize ${changeTypeConfig.badgeClass}`}
              >
                <ChangeIcon className="size-2.5" />
                <span>{changeTypeConfig.label}</span>
              </Badge>

              {/* Toggle Details Button */}
              {hasFieldDiffs && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsDetailsExpanded(!isDetailsExpanded)}
                  className="h-6 px-1.5 text-[11px] text-muted-foreground hover:text-foreground gap-1"
                  aria-expanded={isDetailsExpanded}
                  data-testid={`toggle-details-${item.id}`}
                >
                  <span>{isDetailsExpanded ? 'Ẩn chi tiết' : 'Chi tiết'}</span>
                  {isDetailsExpanded ? (
                    <ChevronUp className="size-3" />
                  ) : (
                    <ChevronDown className="size-3" />
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Collapsible Field Diffs */}
          {hasFieldDiffs && isDetailsExpanded && (
            <div
              className="mt-2 space-y-2 rounded-lg border border-border/60 bg-muted/30 p-3 text-xs animate-in fade-in"
              data-testid={`field-diffs-container-${item.id}`}
            >
              {item.fieldDiffs?.map((field, idx) => (
                <div key={field.fieldDefId || `${field.fieldName}-${idx}`} className="space-y-1">
                  <div className="flex items-center justify-between font-mono text-[11px] text-muted-foreground">
                    <span className="font-semibold break-words">{field.fieldName}</span>
                    {field.isConflict && (
                      <Badge variant="outline" className="text-[9px] h-3.5 text-amber-600 border-amber-500/40">
                        Xung đột
                      </Badge>
                    )}
                  </div>
                  {field.before !== undefined && field.before !== null && (
                    <div className="rounded bg-rose-500/10 px-2 py-0.5 text-rose-800 dark:text-rose-300 font-mono text-[11px] break-words break-all">
                      - {typeof field.before === 'object' ? JSON.stringify(field.before) : String(field.before)}
                    </div>
                  )}
                  {field.after !== undefined && field.after !== null && (
                    <div className="rounded bg-emerald-500/10 px-2 py-0.5 text-emerald-800 dark:text-emerald-300 font-mono text-[11px] break-words break-all">
                      + {typeof field.after === 'object' ? JSON.stringify(field.after) : String(field.after)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
