import { LoaderCircle, Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/shared/ui'
import '@/shared/config/i18n'

export type ContributionMobileBarProps = {
  totalNotes?: number
  selectedNotes?: number
  canSend: boolean
  isSending: boolean
  isBusy: boolean
  isPendingReview: boolean
  onSend: () => void
}

export function ContributionMobileBar({
  totalNotes,
  selectedNotes,
  canSend,
  isSending,
  isBusy,
  isPendingReview,
  onSend,
}: ContributionMobileBarProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <aside
      aria-label={t('request.send_title', 'Gửi cho tác giả')}
      className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-between gap-3 border-t bg-background/95 px-4 py-2.5 shadow-lg backdrop-blur md:hidden"
    >
      <div className="min-w-0 flex-1">
        {selectedNotes !== undefined && totalNotes !== undefined ? (
          <p className="truncate text-xs font-medium text-foreground">
            {t('request.selected_notes_label', 'Note đã chọn')}:{' '}
            <span className="font-bold tabular-nums text-primary">
              {selectedNotes.toLocaleString(locale)}/{totalNotes.toLocaleString(locale)}
            </span>
          </p>
        ) : (
          <p className="truncate text-xs font-medium text-foreground">
            {t('request.title', 'Đóng góp thay đổi')}
          </p>
        )}
      </div>

      <Button
        type="button"
        size="sm"
        className="h-9 shrink-0 rounded-lg px-4 text-xs font-bold"
        disabled={!canSend}
        onClick={onSend}
      >
        {isSending ? <LoaderCircle className="size-3.5 animate-spin" /> : <Send className="size-3.5" />}
        {isBusy
          ? t('request.btn_sending', 'Đang gửi…')
          : isPendingReview
            ? t('request.btn_sent', 'Đã gửi')
            : selectedNotes !== undefined && totalNotes !== undefined && selectedNotes > 0 && selectedNotes < totalNotes
              ? t('request.btn_submit_selected', {
                  count: selectedNotes,
                  defaultValue: `Gửi (${selectedNotes})`,
                })
              : t('request.btn_submit', 'Gửi đóng góp')}
      </Button>
    </aside>
  )
}
