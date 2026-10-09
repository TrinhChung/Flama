import { ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'

export function LearningProgressGuarantee() {
  const { t } = useTranslation('collaboration')

  return (
    <div className="flex items-start gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-xs text-emerald-900 dark:text-emerald-200">
      <ShieldCheck className="size-5 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
      <div className="space-y-0.5">
        <span className="font-bold text-emerald-800 dark:text-emerald-300">
          {t('update.progress_guarantee_title', 'Tiến độ học tập luôn được bảo toàn 100%')}
        </span>
        <p className="text-[11px] text-emerald-700/90 dark:text-emerald-300/90 leading-relaxed">
          {t(
            'update.progress_guarantee_desc',
            'Lịch sử ôn tập, thuật toán lặp lại ngắt quãng (SRS/FSRS/SM-2) và trạng thái thẻ học của bạn gắn liền với tài khoản và không bao giờ bị ghi đè khi cập nhật nội dung deck.',
          )}
        </p>
      </div>
    </div>
  )
}
