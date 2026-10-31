import { LoaderCircle, Send } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/ui'
import { ChangeRequestStatusBadge } from '../ChangeRequestStatusBadge'
import type { DeckChangeRequest } from '../../types'
import '@/shared/config/i18n'

export type ContributionSendCardProps = {
  activeRequest: DeckChangeRequest | null | undefined
  totalNotes?: number
  selectedNotes?: number
  hasSelection?: boolean
  hasLocalChanges: boolean
  isPendingReview: boolean
  isBusy: boolean
  isSending: boolean
  canSend: boolean
  onSend: () => void
}

export function ContributionSendCard({
  activeRequest,
  totalNotes,
  selectedNotes,
  hasSelection = true,
  hasLocalChanges,
  isPendingReview,
  isBusy,
  isSending,
  canSend,
  onSend,
}: ContributionSendCardProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Card className="flex h-full flex-col shadow-xs">
      <CardHeader className="pb-3.5">
        <CardTitle className="text-base font-bold">{t('request.send_title', 'Gửi cho tác giả')}</CardTitle>
        <CardDescription className="text-xs">
          {t('request.send_description', 'Chọn nội dung bên dưới, thêm ghi chú rồi gửi để tác giả duyệt.')}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4">
        <div className="space-y-3">
          {activeRequest ? (
            <div className="space-y-2 rounded-xl border bg-muted/30 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-medium">{t('request.current_request_title', 'Request hiện tại')}</span>
                <ChangeRequestStatusBadge status={activeRequest.status} />
              </div>
              <Button variant="link" asChild className="h-auto p-0 text-xs">
                <Link to={`/flashcards/change-requests/${activeRequest.id}`}>
                  {t('request.btn_view_detail', 'Mở màn chi tiết')}
                </Link>
              </Button>
            </div>
          ) : null}

          {selectedNotes !== undefined && totalNotes !== undefined ? (
            <div className="flex items-center justify-between gap-2.5 rounded-xl border border-primary/20 bg-primary/5 p-3 text-xs">
              <span className="text-muted-foreground">{t('request.selected_notes_label', 'Note đã chọn')}</span>
              <span className="font-bold tabular-nums text-foreground">
                {selectedNotes.toLocaleString(locale)} / {totalNotes.toLocaleString(locale)}
              </span>
            </div>
          ) : null}

          <Button
            type="button"
            className="h-10 w-full rounded-xl text-xs font-bold"
            disabled={!canSend}
            aria-describedby="contribution-send-status"
            onClick={onSend}
          >
            {isSending ? <LoaderCircle className="animate-spin" /> : <Send />}
            {isBusy
              ? t('request.btn_sending', 'Đang gửi đóng góp…')
              : isPendingReview
                ? t('request.btn_sent', 'Đã gửi · Chờ tác giả duyệt')
                : selectedNotes !== undefined && totalNotes !== undefined && selectedNotes > 0 && selectedNotes < totalNotes
                  ? t('request.btn_submit_selected', {
                      count: selectedNotes,
                      defaultValue: `Gửi ${selectedNotes} note đã chọn`,
                    })
                  : t('request.btn_submit', 'Gửi đóng góp')}
          </Button>
        </div>

        <div className="rounded-xl border border-border/50 bg-muted/20 p-2.5">
          <p id="contribution-send-status" role="status" className="text-xs leading-relaxed text-muted-foreground">
            {isPendingReview
              ? t('request.pending_notice', 'Đóng góp đã được gửi. Bạn vẫn có thể tiếp tục sửa riêng trong thư viện.')
              : !hasLocalChanges
                ? t('request.no_local_changes_title', 'Chưa có thay đổi đã lưu')
                : !hasSelection
                  ? t('request.nothing_selected', 'Hãy chọn ít nhất một note để gửi.')
                  : selectedNotes === 0
                    ? t('request.schema_selected', 'Các thay đổi cấu trúc đã chọn sẽ được gửi cho tác giả duyệt.')
                    : selectedNotes === undefined
                      ? t(
                          'request.send_ready',
                          'Các thay đổi bên dưới sẽ được gửi cho tác giả duyệt. Nội dung chung chỉ thay đổi sau khi tác giả duyệt và phát hành.',
                        )
                      : t(
                          'request.send_selected_ready',
                          'Chỉ những note được chọn bên dưới sẽ được gửi cho tác giả duyệt. Nội dung chung chỉ thay đổi sau khi tác giả duyệt và phát hành.',
                        )}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}
