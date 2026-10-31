import { ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'

export function ContributionSafetyBanner() {
  const { t } = useTranslation('collaboration')

  return (
    <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-xs text-emerald-900 shadow-xs dark:text-emerald-200">
      <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
      <div className="space-y-0.5">
        <p className="font-bold text-emerald-800 dark:text-emerald-300">
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
  )
}
