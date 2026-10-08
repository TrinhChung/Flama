import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import { DAILY_TARGET_OPTIONS } from '@/features/onboarding/constants'
import type { DailyTargetOption } from '@/features/onboarding/types'

interface DailyTargetSectionProps {
  selectedDailyTarget: DailyTargetOption
  onSelectDailyTarget: (value: DailyTargetOption) => void
}

export function DailyTargetSection({
  selectedDailyTarget,
  onSelectDailyTarget,
}: DailyTargetSectionProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
        {t('study_goals.sections.daily_target_title')}
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {DAILY_TARGET_OPTIONS.map((opt) => {
          const isSelected = selectedDailyTarget === opt.value
          return (
            <div
              key={opt.value}
              onClick={() => onSelectDailyTarget(opt.value)}
              className={`p-3.5 rounded-xl border cursor-pointer transition-colors flex flex-col justify-between space-y-1.5 ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                  : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-bold text-foreground">{opt.label}</span>
                {isSelected && <Check className="size-3.5 text-primary stroke-[3]" />}
              </div>
              <div className="text-[11px] text-primary font-medium">{opt.timeEstimate}</div>
              <p className="text-[11px] text-muted-foreground line-clamp-2">{opt.description}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
