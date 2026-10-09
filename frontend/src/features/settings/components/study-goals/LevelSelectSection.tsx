import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import type { SubjectOptionConfig } from '@/features/onboarding/constants'

interface LevelSelectSectionProps {
  currentSubjectConfig: SubjectOptionConfig
  selectedLevel: string
  onSelectLevel: (levelId: string, difficultyBand: 'beginner' | 'intermediate' | 'advanced') => void
}

export function LevelSelectSection({
  currentSubjectConfig,
  selectedLevel,
  onSelectLevel,
}: LevelSelectSectionProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
          {t('study_goals.sections.level_title')}
        </h3>
        <span className="text-xs text-muted-foreground">{currentSubjectConfig.title}</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
        {currentSubjectConfig.levels.map((lvl) => {
          const isSelected = selectedLevel === lvl.id
          return (
            <div
              key={lvl.id}
              onClick={() => onSelectLevel(lvl.id, lvl.difficulty_band)}
              className={`p-3 rounded-xl border cursor-pointer transition-colors flex items-center justify-between gap-2 ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                  : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
              }`}
            >
              <span className="text-xs font-medium text-foreground truncate">{lvl.label}</span>
              {isSelected && <Check className="size-3.5 text-primary shrink-0 stroke-[3]" />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
