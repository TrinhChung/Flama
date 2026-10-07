import { ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { TAXONOMY_DIFFICULTIES } from '../../utils/publishTaxonomyConstants'
import { WIZARD_STEPS } from './PublishWizardTypes'

interface PublishDeckSummaryFooterProps {
  currentStep: number
  title: string
  taxonomySubject: string
  taxonomyDifficulty: string
  distributionMode: 'free' | 'paid' | 'course_key'
  priceAmountMinor: number
  availableSubjects: Array<{ id: string; label: string }>
  isEditMode: boolean
  isPending: boolean
  onPrevStep: () => void
  onNextStep: () => void
  onPublish: () => void
}

export function PublishDeckSummaryFooter({
  currentStep,
  title,
  taxonomySubject,
  taxonomyDifficulty,
  distributionMode,
  priceAmountMinor,
  availableSubjects,
  isEditMode,
  isPending,
  onPrevStep,
  onNextStep,
  onPublish,
}: PublishDeckSummaryFooterProps) {
  const { t } = useTranslation('marketplace')

  return (
    <>
      {currentStep === 4 && (
        <div className="p-4 rounded-xl border border-border/80 bg-muted/30 space-y-2.5 text-xs">
          <div className="font-bold text-foreground flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-muted-foreground" />
            <span>{t('publish_deck.step4.summary_box_title', { defaultValue: 'Tóm tắt thông tin xuất bản:' })}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-muted-foreground">
            <div>
              {t('publish_deck.summary_title', { defaultValue: 'Tiêu đề:' })}{' '}
              <strong className="text-foreground">{title || t('publish_deck.summary_not_set', { defaultValue: 'Chưa đặt' })}</strong>
            </div>
            <div>
              {t('publish_deck.summary_subject', { defaultValue: 'Môn học:' })}{' '}
              <strong className="text-foreground">
                {availableSubjects.find((s) => s.id === taxonomySubject)?.label || taxonomySubject}
              </strong>
            </div>
            <div>
              {t('publish_deck.summary_difficulty', { defaultValue: 'Độ khó:' })}{' '}
              <strong className="text-foreground">
                {TAXONOMY_DIFFICULTIES.find((d) => d.id === taxonomyDifficulty)?.label || taxonomyDifficulty}
              </strong>
            </div>
            <div>
              {t('publish_deck.summary_model', { defaultValue: 'Mô hình:' })}{' '}
              <strong className="text-foreground">
                {distributionMode === 'course_key'
                  ? t('publish_deck.step4.mode_key_title', { defaultValue: 'Mã lớp học (Keys)' })
                  : distributionMode === 'paid'
                    ? `${priceAmountMinor.toLocaleString('vi-VN')} đ`
                    : t('card.free', { defaultValue: 'Miễn phí' })}
              </strong>
            </div>
          </div>
        </div>
      )}

      {/* Step Navigation Actions Footer */}
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
            disabled={isPending}
            className="h-11 sm:h-10 px-6 text-xs font-bold rounded-xl bg-primary text-primary-foreground shadow-md hover:bg-primary/90 transition-all cursor-pointer flex-1 sm:flex-initial justify-center"
          >
            <CheckCircle2 className="w-4 h-4 mr-1.5" />
            <span>
              {isPending
                ? t('publish_deck.step4.submitting', { defaultValue: 'Đang lưu…' })
                : isEditMode
                  ? t('publish_deck.step4.btn_submit_edit', { defaultValue: 'Cập nhật cấu hình chia sẻ' })
                  : t('publish_deck.step4.btn_submit_create', { defaultValue: 'Xuất bản Bộ thẻ ngay' })}
            </span>
          </Button>
        )}
      </div>
    </>
  )
}
