import { Check, GitMerge, LoaderCircle, RefreshCcw, Send, X } from 'lucide-react'
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
  onApprove: () => void
  onReject: () => void
  onSync: () => void
  onSubmit: () => void
  isApproving: boolean
  isRejecting: boolean
  isSyncing: boolean
  isSubmitting: boolean
}

export function ChangeRequestDetailActions({
  request,
  isOwner,
  isRequester,
  isBusy,
  reviewComment,
  onReviewCommentChange,
  onApprove,
  onReject,
  onSync,
  onSubmit,
  isApproving,
  isRejecting,
  isSyncing,
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
                  'Lý do merge hoặc từ chối…',
                )}
                rows={3}
                maxLength={5000}
              />
            </div>
            <Button className="w-full" disabled={isBusy} onClick={onApprove}>
              {isApproving ? <LoaderCircle className="animate-spin" /> : <GitMerge />}
              {t('detail.btn_merge', 'Merge vào working deck')}
            </Button>
            <Button
              className="w-full"
              variant="destructive"
              disabled={isBusy || !reviewComment.trim()}
              onClick={onReject}
            >
              {isRejecting ? <LoaderCircle className="animate-spin" /> : <X />}
              {t('detail.btn_reject', 'Từ chối request')}
            </Button>
          </>
        ) : null}

        {request.status === 'needs_sync' ||
        request.status === 'draft' ||
        request.status === 'has_conflict' ? (
          <Button
            className="w-full"
            variant="outline"
            disabled={isBusy || request.can_review}
            onClick={onSync}
          >
            {isSyncing ? <LoaderCircle className="animate-spin" /> : <RefreshCcw />}
            {t('detail.btn_sync_again', 'Đồng bộ lại')}
          </Button>
        ) : null}

        {request.can_submit ? (
          <Button className="w-full" disabled={isBusy} onClick={onSubmit}>
            {isSubmitting ? <LoaderCircle className="animate-spin" /> : <Send />}
            {t('detail.btn_submit_for_review', 'Gửi owner duyệt')}
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
