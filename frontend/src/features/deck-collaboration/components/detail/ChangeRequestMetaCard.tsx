import { useTranslation } from 'react-i18next'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import '@/shared/config/i18n'
import { ChangeRequestStatusBadge } from '../ChangeRequestStatusBadge'
import type { DeckChangeRequest } from '../../types'

export function ChangeRequestMetaCard({ request }: { request: DeckChangeRequest }) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <ChangeRequestStatusBadge status={request.status} />
          <Badge variant="outline">
            {t('detail.revision_badge', {
              revision: request.revision,
              defaultValue: `Revision ${request.revision}`,
            })}
          </Badge>
          <Badge variant="secondary">
            {t('detail.changes_count', {
              count: request.item_count.toLocaleString(locale),
              defaultValue: `${request.item_count.toLocaleString(locale)} thay đổi`,
            })}
          </Badge>
        </div>
        <CardTitle className="text-base">{t('detail.description_title', 'Mô tả đóng góp')}</CardTitle>
        <CardDescription className="whitespace-pre-wrap">
          {request.description || t('detail.description_empty', 'Người đóng góp không thêm mô tả.')}
        </CardDescription>
      </CardHeader>
      {request.review_comment ? (
        <CardContent>
          <Alert>
            <AlertTitle>{t('detail.owner_response_title', 'Phản hồi từ owner')}</AlertTitle>
            <AlertDescription className="whitespace-pre-wrap">{request.review_comment}</AlertDescription>
          </Alert>
        </CardContent>
      ) : null}
    </Card>
  )
}
