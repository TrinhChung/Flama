import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import '@/shared/config/i18n'
import { formatDate } from '../../hooks/useChangeRequestInbox'
import { ChangeRequestStatusBadge } from '../ChangeRequestStatusBadge'
import type { DeckChangeRequest } from '../../types'
import { ContributorIdentity } from './ContributorIdentity'

export function ChangeRequestMetaCard({ request }: { request: DeckChangeRequest }) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const sentAt = formatDate(request.submitted_at || request.created_at, locale)
  const noteCount = request.note_count ?? request.item_count

  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ContributorIdentity
            actor={request.requester}
            caption={sentAt
              ? t('detail.sent_at', { date: sentAt, defaultValue: `Gửi lúc ${sentAt}` })
              : t('detail.sent_by', 'Người gửi')}
          />
          <div className="flex flex-wrap items-center gap-2">
            <ChangeRequestStatusBadge status={request.status} />
            <Badge variant="secondary">
              {t('detail.note_count', {
                count: noteCount,
                formatted: noteCount.toLocaleString(locale),
                defaultValue: `${noteCount.toLocaleString(locale)} note thay đổi`,
              })}
            </Badge>
          </div>
        </div>
        <CardTitle className="text-base">{t('detail.description_title', 'Mô tả đóng góp')}</CardTitle>
        <CardDescription className="whitespace-pre-wrap">
          {request.description || t('detail.description_empty', 'Người đóng góp không thêm mô tả.')}
        </CardDescription>
      </CardHeader>
      {request.review_comment ? (
        <CardContent>
          <Alert>
            <AlertTitle>{t('detail.owner_response_title', 'Phản hồi từ tác giả')}</AlertTitle>
            <AlertDescription className="whitespace-pre-wrap">{request.review_comment}</AlertDescription>
          </Alert>
        </CardContent>
      ) : null}
    </Card>
  )
}
