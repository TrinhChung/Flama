import {
  UploadCloud,
  ArrowRightLeft,
  Zap,
  Check,
  Layers,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useFileImportWizard } from '../hooks/useFileImportWizard'
import { ImportOptionsStep } from '../components/ImportOptionsStep'
import { ImportFileStep } from '../components/ImportFileStep'
import { ImportMappingStep } from '../components/ImportMappingStep'
import { ImportResultStep } from '../components/ImportResultStep'

export function FileImportPage() {
  const { t } = useTranslation('import')
  const wizard = useFileImportWizard()
  const { optionsQuery, currentStep, token, fields } = wizard

  if (optionsQuery.isPending) return <PageLoading label={t('file_import.loading_config')} />
  if (optionsQuery.error) return <Page><PageError error={optionsQuery.error} /></Page>

  const stepsConfig = [
    {
      step: 1,
      label: t('file_import.stepper.step1_label', { defaultValue: '1. Đích & Thẻ' }),
      desc: t('file_import.stepper.step1_desc', { defaultValue: 'Chọn Deck & NoteType' }),
      icon: Layers,
    },
    {
      step: 2,
      label: t('file_import.stepper.step2_label', { defaultValue: '2. Tải & Parse' }),
      desc: t('file_import.stepper.step2_desc', { defaultValue: 'Kéo thả file dữ liệu' }),
      icon: UploadCloud,
    },
    {
      step: 3,
      label: t('file_import.stepper.step3_label', { defaultValue: '3. Ánh xạ Cột' }),
      desc: t('file_import.stepper.step3_desc', { defaultValue: 'Ghép cột & Chế độ ghi' }),
      icon: ArrowRightLeft,
    },
    {
      step: 4,
      label: t('file_import.stepper.step4_label', { defaultValue: '4. Thực thi' }),
      desc: t('file_import.stepper.step4_desc', { defaultValue: 'Ước lượng & Nạp thẻ' }),
      icon: Zap,
    },
  ]

  return (
    <Page size="wide" className="px-4 lg:px-8 py-3 space-y-6">
      <PageHeader
        title={t('file_import.page_title', { defaultValue: 'Import Note & Thẻ Flashcard' })}
        description={t('file_import.page_desc', { defaultValue: 'Nhập dữ liệu flashcard hàng loạt từ tệp CSV, TSV hoặc định dạng phân tách tùy chỉnh với quy trình rà soát an toàn.' })}
        actions={
          <ContextHelpButton
            guidePath="/guide/import-sync/csv-wizard"
            guideTitle="Hướng dẫn nạp tệp CSV qua Wizard"
            troubleshootPath="/guide/troubleshooting/import-csv"
            troubleshootTitle="Khắc phục lỗi nạp file CSV"
            label={t('file_import.help_btn', { defaultValue: 'Hướng dẫn nạp file' })}
          />
        }
      />

      {/* Modern Stepper Indicator */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stepsConfig.map((s) => {
          const IconComp = s.icon
          const isActive = currentStep === s.step
          const isDone = currentStep > s.step

          return (
            <div
              key={s.step}
              className={`p-3 rounded-2xl border transition-all flex items-center gap-3 ${
                isActive
                  ? 'border-primary bg-primary/5 shadow-xs'
                  : isDone
                  ? 'border-border/80 bg-card/60 text-muted-foreground'
                  : 'border-border/40 bg-card/30 opacity-60'
              }`}
            >
              <div
                className={`size-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-xs'
                    : isDone
                    ? 'bg-primary/15 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {isDone ? <Check className="size-4" /> : <IconComp className="size-4" />}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-bold truncate ${isActive ? 'text-primary' : 'text-foreground'}`}>
                  {s.label}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">{s.desc}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Step 1 Card: Target Deck & Note Type */}
      <ImportOptionsStep wizard={wizard} />

      {/* Step 2 Card: File Upload & Parse */}
      <ImportFileStep wizard={wizard} />

      {/* Step 3 Card: Column Mapping */}
      {fields.length > 0 && token && <ImportMappingStep wizard={wizard} />}

      {/* Step 4 Card: Execution & Report */}
      {token && <ImportResultStep wizard={wizard} />}
    </Page>
  )
}
