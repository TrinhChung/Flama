import { ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'

const WIZARD_STEPS = [
  { id: 1, title: 'Mẫu thẻ & Mô tả' },
  { id: 2, title: 'Phân loại & Trình độ' },
  { id: 3, title: 'Mục tiêu & Kỹ năng' },
  { id: 4, title: 'Giá bán & Đăng tải' },
]

interface PublishNoteTypeSummaryFooterProps {
  currentStep: number
  isEditMode: boolean
  isPending: boolean
  isSelectedInstalledCopy: boolean
  isSelectedAlreadyPublished: boolean
  onPrevStep: () => void
  onNextStep: () => void
  onPublish: () => void
}

export function PublishNoteTypeSummaryFooter({
  currentStep,
  isEditMode,
  isPending,
  isSelectedInstalledCopy,
  isSelectedAlreadyPublished,
  onPrevStep,
  onNextStep,
  onPublish,
}: PublishNoteTypeSummaryFooterProps) {
  const { t } = useTranslation('marketplace')

  return (
    <div className="p-4 sm:p-6 border-t border-border/40 bg-muted/10 flex items-center justify-between gap-3">
      <Button
        type="button"
        variant="outline"
        size="default"
        onClick={onPrevStep}
        disabled={currentStep === 1}
        className="h-11 sm:h-10 px-4 text-xs font-semibold rounded-xl shrink-0"
      >
        <ArrowLeft className="w-3.5 h-3.5 mr-1.5" />
        {t('publish_deck.btn_prev', { defaultValue: 'Quay lại' })}
      </Button>

      <div className="text-xs text-muted-foreground font-medium hidden sm:block">
        {t('publish_deck.step_counter', {
          defaultValue: `Bước ${currentStep} / 4: ${WIZARD_STEPS[currentStep - 1]?.title || ''}`,
          current: currentStep,
          total: 4,
          title: WIZARD_STEPS[currentStep - 1]?.title || '',
        })}
      </div>

      {currentStep < 4 ? (
        <Button
          type="button"
          size="default"
          onClick={onNextStep}
          className="h-11 sm:h-10 px-5 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-xs hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
        >
          <span>
            {t('publish_deck.btn_next', {
              defaultValue: `Tiếp tục (Bước ${currentStep + 1})`,
              step: currentStep + 1,
            })}
          </span>
          <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
        </Button>
      ) : (
        <Button
          type="button"
          size="default"
          onClick={onPublish}
          disabled={isSelectedInstalledCopy || isSelectedAlreadyPublished || isPending}
          className="h-11 sm:h-10 px-6 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-md hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
        >
          <CheckCircle2 className="w-4 h-4 mr-1.5" />
          <span>
            {isSelectedInstalledCopy
              ? 'Bản cài Marketplace (Không thể xuất bản)'
              : isSelectedAlreadyPublished
                ? 'Đã xuất bản (Bấm Chỉnh sửa ở trên)'
                : isPending
                  ? t('publish_deck.step4.submitting', { defaultValue: 'Đang lưu…' })
                  : isEditMode
                    ? t('publish_deck.step4.btn_submit_edit', { defaultValue: 'Cập nhật cấu hình chia sẻ' })
                    : 'Xuất bản Loại thẻ ngay'}
          </span>
        </Button>
      )}
    </div>
  )
}
