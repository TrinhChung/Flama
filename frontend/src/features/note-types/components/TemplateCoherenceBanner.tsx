import { AlertTriangle, ArrowRight, RefreshCw, X } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { CoherenceWarningType, TemplateCoherenceWarning } from '@/entities/deck-version'

export interface TemplateCoherenceBannerProps {
  warnings: TemplateCoherenceWarning[]
  onAlignTemplatePin?: (templateId: string, targetRelease?: string | null) => void
  onDismiss?: () => void
  className?: string
}

function getWarningBadgeConfig(type: CoherenceWarningType | string): {
  label: string
  className: string
} {
  switch (type) {
    case 'OUTDATED_PIN':
      return {
        label: 'Có bản mới',
        className: 'border-amber-500/40 bg-amber-500/20 text-amber-800 dark:text-amber-300',
      }
    case 'UNCOMMITTED_DRAFT':
      return {
        label: 'Bản nháp chưa công bố',
        className: 'border-purple-500/40 bg-purple-500/20 text-purple-800 dark:text-purple-300',
      }
    case 'UNMAPPED_FIELDS':
      return {
        label: 'Chưa ánh xạ trường',
        className: 'border-rose-500/40 bg-rose-500/20 text-rose-800 dark:text-rose-300',
      }
    default:
      return {
        label: type,
        className: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
      }
  }
}

export function TemplateCoherenceBanner({
  warnings,
  onAlignTemplatePin,
  onDismiss,
  className,
}: TemplateCoherenceBannerProps) {
  if (!warnings || warnings.length === 0) {
    return null
  }

  return (
    <div
      role="alert"
      className={cn(
        'rounded-2xl border border-amber-500/40 bg-amber-500/10 p-4 text-amber-950 dark:text-amber-100 shadow-xs space-y-3',
        className
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 sm:gap-3">
          <AlertTriangle className="size-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-0.5">
            <h4 className="font-semibold text-sm leading-tight text-amber-900 dark:text-amber-200">
              Cảnh báo không đồng bộ Mẫu thẻ (Template Coherence Alert)
            </h4>
            <p className="text-xs text-amber-800/90 dark:text-amber-300/90">
              Phát hiện {warnings.length} Mẫu thẻ gắn kèm có bản phát hành mới hơn, bản nháp chưa công bố
              hoặc thiếu ánh xạ trường. Hãy cập nhật phiên bản tương thích để tránh lỗi hiển thị khi học.
            </p>
          </div>
        </div>

        {onDismiss && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onDismiss}
            className="h-7 w-7 p-0 text-amber-800 hover:text-amber-950 dark:text-amber-300 dark:hover:text-amber-100"
            aria-label="Đóng cảnh báo"
          >
            <X className="size-4" />
          </Button>
        )}
      </div>

      {/* Warning Items */}
      <div className="space-y-2 pt-1">
        {warnings.map((warning, index) => {
          const badgeConfig = getWarningBadgeConfig(warning.warning_type)
          return (
            <div
              key={`${warning.template_id}-${index}`}
              data-testid={`coherence-warning-${warning.template_id}`}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3 rounded-xl border border-amber-500/20 bg-background/80 p-3 text-xs text-foreground shadow-2xs"
            >
              <div className="space-y-1 min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="font-semibold text-foreground truncate max-w-[200px] sm:max-w-xs"
                    title={warning.template_name}
                  >
                    {warning.template_name}
                  </span>
                  <Badge variant="outline" className={cn('text-[10px] h-4', badgeConfig.className)}>
                    {badgeConfig.label}
                  </Badge>
                  {warning.pinned_release && (
                    <Badge variant="outline" className="font-mono text-[10px] h-4">
                      pin: {warning.pinned_release}
                    </Badge>
                  )}
                  {warning.latest_release && warning.latest_release !== warning.pinned_release && (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-amber-700 dark:text-amber-300 font-medium">
                      <ArrowRight className="size-2.5" /> mới nhất: {warning.latest_release}
                    </span>
                  )}
                </div>
                <p className="text-muted-foreground text-[11px] leading-relaxed break-words">
                  {warning.message}
                </p>
                {warning.action_recommendation && (
                  <p className="text-[11px] font-medium text-amber-800 dark:text-amber-300 break-words">
                    💡 Gợi ý: {warning.action_recommendation}
                  </p>
                )}
              </div>

              {onAlignTemplatePin && (
                <Button
                  size="sm"
                  variant="outline"
                  className="shrink-0 w-full sm:w-auto text-center justify-center whitespace-normal sm:whitespace-nowrap h-auto py-1.5 sm:h-7 min-h-[36px] sm:min-h-[28px] text-xs gap-1.5 border-amber-500/40 text-amber-800 hover:bg-amber-500/10 dark:text-amber-300 font-medium"
                  data-testid={`align-template-pin-${warning.template_id}`}
                  onClick={() => onAlignTemplatePin(warning.template_id, warning.latest_release)}
                >
                  <RefreshCw className="size-3" />
                  <span>Cập nhật phiên bản Template tương thích</span>
                </Button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
