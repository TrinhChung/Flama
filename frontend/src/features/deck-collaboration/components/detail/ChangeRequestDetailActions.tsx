import { Check, CheckCheck, ListChecks, LoaderCircle, Send, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import '@/shared/config/i18n'
import type { DeckChangeRequest } from '../../types'

type ChangeRequestDetailActionsProps = {
  request: DeckChangeRequest
  isOwner: boolean
  isRequester: boolean
  isBusy: boolean
  reviewComment: string
  onReviewCommentChange: (value: string) => void
  /** Selected changes out of all, when the owner unticked some. */
  acceptsEverything: boolean
  selectedCount: number
  onApprove: (scope: 'selected' | 'all') => void
  onReject: () => void
  onSubmit: () => void
  isApproving: boolean
  isRejecting: boolean
  isSubmitting: boolean
}

export function ChangeRequestDetailActions({
  request,
  isOwner,
  isRequester,
  isBusy,
  reviewComment,
  onReviewCommentChange,
  acceptsEverything,
  selectedCount,
  onApprove,
  onReject,
  onSubmit,
  isApproving,
  isRejecting,
  isSubmitting,
}: ChangeRequestDetailActionsProps) {
  const { t } = useTranslation('collaboration')

  return (
    <Card className="h-fit lg:sticky lg:top-4">
      <CardHeader>
        <CardTitle className="text-base">{t('detail.actions_title', 'Hành động')}</CardTitle>
        <CardDescription>
          {t('detail.actions_desc', 'Action khả dụng phụ thuộc vai trò và trạng thái request.')}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {request.can_review ? (
          <>
            <div className="space-y-2">
              <Label htmlFor="review-comment">
                {t('detail.review_comment_label', 'Phản hồi cho người đóng góp')}
              </Label>
              <Textarea
                id="review-comment"
                value={reviewComment}
                onChange={(event) => onReviewCommentChange(event.target.value)}
                placeholder={t(
                  'detail.review_comment_placeholder',
                  'Lý do nhận hoặc từ chối…',
                )}
                rows={3}
                maxLength={5000}
              />
            </div>
            {acceptsEverything ? null : (
              <Button className="w-full" disabled={isBusy || selectedCount === 0} onClick={() => onApprove('selected')}>
                {isApproving ? <LoaderCircle className="animate-spin" /> : <ListChecks />}
                {t('detail.btn_accept_selected', {
                  count: selectedCount,
                  defaultValue: `Nhận ${selectedCount} thay đổi đã chọn`,
                })}
              </Button>
            )}
            <Button
              className="w-full"
              variant={acceptsEverything ? 'default' : 'outline'}
              disabled={isBusy}
              onClick={() => onApprove('all')}
            >
              {isApproving && acceptsEverything ? <LoaderCircle className="animate-spin" /> : <CheckCheck />}
              {t('detail.btn_accept_all', 'Nhận tất cả')}
            </Button>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {selectedCount === 0 && !acceptsEverything
                ? t('detail.nothing_selected', 'Hãy chọn ít nhất một thay đổi để nhận.')
                : t('detail.accept_hint', 'Bỏ chọn note hoặc trường bạn không muốn nhận. Phần không nhận vẫn nằm trong bản sửa riêng của người đóng góp.')}
            </p>
            <Button
              className="w-full"
              variant="destructive"
              disabled={isBusy || !reviewComment.trim()}
              onClick={onReject}
            >
              {isRejecting ? <LoaderCircle className="animate-spin" /> : <X />}
              {t('detail.btn_reject', 'Từ chối đóng góp')}
            </Button>
          </>
        ) : null}

        {isRequester && (request.status === 'needs_sync' || request.status === 'draft') ? (
          <Button className="w-full" disabled={isBusy || request.unresolved_conflict_count > 0 || !request.item_count} onClick={onSubmit}>
            {isSubmitting ? <LoaderCircle className="animate-spin" /> : <Send />}
            {isSubmitting ? t('request.btn_sending', 'Đang gửi đóng góp…') : t('request.btn_submit', 'Gửi đóng góp')}
          </Button>
        ) : null}

        {request.status === 'merged' && isOwner ? (
          <Button className="w-full" asChild>
            <Link to={`/creator/decks/${request.deck_item_id}/releases/new`}>
              <Check />
              {t('detail.btn_create_release', 'Tạo release mới')}
            </Link>
          </Button>
        ) : null}

        {request.status === 'pending_review' && isRequester ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t(
              'detail.pending_review_notice',
              'Đóng góp đang chờ chủ sở hữu duyệt. Deck local của bạn vẫn có thể tiếp tục được chỉnh sửa.',
            )}
          </p>
        ) : null}

        {request.status === 'merged' && !isOwner ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t(
              'detail.merged_notice',
              'Đóng góp đã được merge vào working deck. Người dùng khác chỉ nhận thay đổi sau khi chủ sở hữu phát hành release mới.',
            )}
          </p>
        ) : null}

        {request.status === 'rejected' ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {t(
              'detail.rejected_notice',
              'Request bị từ chối nhưng overlay local của người sửa không bị xóa.',
            )}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
