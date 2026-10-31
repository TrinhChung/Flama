import { FileDiff, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, Input, Label, Textarea } from '@/shared/ui'
import '@/shared/config/i18n'

export type ContributionMetaCardProps = {
  title: string
  onTitleChange: (value: string) => void
  description: string
  onDescriptionChange: (value: string) => void
  totalNotes?: number
  isPendingReview: boolean
  isBusy: boolean
}

export function ContributionMetaCard({
  title,
  onTitleChange,
  description,
  onDescriptionChange,
  totalNotes,
  isPendingReview,
  isBusy,
}: ContributionMetaCardProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  return (
    <Card className="flex h-full flex-col shadow-xs transition-shadow">
      <CardHeader className="space-y-2 pb-3.5">
        {totalNotes !== undefined ? (
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="gap-1.5 border-primary/20 bg-primary/5 text-primary">
              <FileDiff className="size-3.5" />
              {t('request.changed_notes', {
                count: totalNotes,
                defaultValue: `${totalNotes.toLocaleString(locale)} note thay đổi`,
              })}
            </Badge>
          </div>
        ) : null}
        <CardTitle className="text-base font-bold">{t('request.meta_title', 'Thông tin đóng góp')}</CardTitle>
        <CardDescription className="text-xs leading-relaxed">
          {t('request.meta_desc', 'Khi gửi, hệ thống tự kiểm tra nội dung gốc. Bạn chỉ cần xử lý thêm nếu có xung đột.')}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col justify-between gap-4">
        <div className="space-y-3.5">
          <div className="space-y-2">
            <Label htmlFor="contribution-title">{t('request.field_title_label', 'Tiêu đề')}</Label>
            <Input
              id="contribution-title"
              value={title}
              onChange={(event) => onTitleChange(event.target.value)}
              placeholder={t('request.field_title_placeholder', 'Ví dụ: Sửa nghĩa và cách đọc bài 3')}
              disabled={isPendingReview || isBusy}
              maxLength={255}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contribution-description">{t('request.field_desc_label', 'Mô tả')}</Label>
            <Textarea
              id="contribution-description"
              value={description}
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder={t('request.field_desc_placeholder', 'Giải thích ngắn lý do và phạm vi thay đổi…')}
              className="min-h-20 resize-y"
              disabled={isPendingReview || isBusy}
              rows={3}
              maxLength={5000}
            />
          </div>
        </div>

        {/* Box xanh lá cam kết an toàn & giữ nguyên phần sửa riêng đặt ngay dưới mô tả */}
        <div className="flex items-start gap-2.5 rounded-xl border border-emerald-500/25 bg-emerald-500/8 p-3 text-xs text-emerald-900 shadow-2xs dark:text-emerald-200">
          <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div className="space-y-0.5">
            <p className="font-semibold text-emerald-800 dark:text-emerald-300">
              {t('request.preservation_title', 'Phần sửa riêng và tiến độ học được giữ nguyên')}
            </p>
            <p className="text-[11px] leading-relaxed text-emerald-700/90 dark:text-emerald-300/90">
              {t(
                'request.preservation_description',
                'Gửi đóng góp không thay đổi nội dung bạn đang học. Tác giả sẽ xem xét trước khi đưa thay đổi vào bản phát hành chung.',
              )}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
