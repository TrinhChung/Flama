import {
  UploadCloud,
  ArrowRightLeft,
  Zap,
  Check,
  Layers,
} from 'lucide-react'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'

import { useFileImportWizard } from '../hooks/useFileImportWizard'
import { ImportOptionsStep } from '../components/ImportOptionsStep'
import { ImportFileStep } from '../components/ImportFileStep'
import { ImportMappingStep } from '../components/ImportMappingStep'
import { ImportResultStep } from '../components/ImportResultStep'

export function FileImportPage() {
  const wizard = useFileImportWizard()
  const { optionsQuery, currentStep, token, fields } = wizard

  if (optionsQuery.isPending) return <PageLoading label="Đang tải cấu hình import…" />
  if (optionsQuery.error) return <Page><PageError error={optionsQuery.error} /></Page>

  return (
    <Page className="w-full max-w-6xl px-4 lg:px-8 py-3 space-y-6">
      <PageHeader
        title="Import Note & Thẻ Flashcard"
        description="Nhập dữ liệu flashcard hàng loạt từ tệp CSV, TSV hoặc định dạng phân tách tùy chỉnh với quy trình rà soát an toàn."
        actions={
          <ContextHelpButton
            guidePath="/guide/import-sync/csv-wizard"
            guideTitle="Hướng dẫn nạp tệp CSV qua Wizard"
            troubleshootPath="/guide/troubleshooting/import-csv"
            troubleshootTitle="Khắc phục lỗi nạp file CSV"
            label="Hướng dẫn nạp file"
          />
        }
      />

      {/* Modern Stepper Indicator */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { step: 1, label: '1. Đích & Thẻ', desc: 'Chọn Deck & NoteType', icon: Layers },
          { step: 2, label: '2. Tải & Parse', desc: 'Kéo thả file dữ liệu', icon: UploadCloud },
          { step: 3, label: '3. Ánh xạ Cột', desc: 'Ghép cột & Chế độ ghi', icon: ArrowRightLeft },
          { step: 4, label: '4. Thực thi', desc: 'Ước lượng & Nạp thẻ', icon: Zap },
        ].map((s) => {
          const IconComp = s.icon
          const isActive = currentStep === s.step
          const isDone = currentStep > s.step

          return (
            <div
              key={s.step}
              className={`p-3 rounded-2xl border transition-all flex items-center gap-3 ${
                isActive
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : isDone
                  ? 'border-border/80 bg-card/60 text-muted-foreground'
                  : 'border-border/40 bg-card/30 opacity-60'
              }`}
            >
              <div
                className={`size-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-sm'
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
