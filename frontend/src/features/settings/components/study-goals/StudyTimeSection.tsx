import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import { STUDY_TIME_OPTIONS } from '@/features/onboarding/constants'
import type { StudyTimeOption } from '@/features/onboarding/types'

interface StudyTimeSectionProps {
  selectedStudyTime: StudyTimeOption
  onSelectStudyTime: (value: StudyTimeOption) => void
}

export function StudyTimeSection({
  selectedStudyTime,
  onSelectStudyTime,
}: StudyTimeSectionProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
        {t('study_goals.sections.study_time_title')}
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
        {STUDY_TIME_OPTIONS.map((timeOpt) => {
          const isSelected = selectedStudyTime === timeOpt.value
          return (
            <div
              key={timeOpt.value}
              onClick={() => onSelectStudyTime(timeOpt.value)}
              className={`p-3.5 rounded-xl border cursor-pointer transition-colors flex items-center justify-between ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                  : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
              }`}
            >
              <div className="min-w-0">
                <div className="text-xs font-bold text-foreground">{timeOpt.label}</div>
                <div className="text-[11px] text-muted-foreground">{timeOpt.sub}</div>
              </div>
              {isSelected && <Check className="size-3.5 text-primary stroke-[3]" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
