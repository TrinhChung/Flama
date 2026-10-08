import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import { SUBJECT_OPTIONS } from '@/features/onboarding/constants'
import type { OnboardingSubject } from '@/features/onboarding/types'

interface SubjectSelectSectionProps {
  selectedSubject: OnboardingSubject
  onSelectSubject: (subject: OnboardingSubject) => void
}

export function SubjectSelectSection({
  selectedSubject,
  onSelectSubject,
}: SubjectSelectSectionProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-bold text-foreground uppercase tracking-wide text-muted-foreground">
        {t('study_goals.sections.subject_title')}
      </h3>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        {SUBJECT_OPTIONS.map((subj) => {
          const isSelected = selectedSubject === subj.id
          return (
            <div
              key={subj.id}
              onClick={() => onSelectSubject(subj.id)}
              className={`p-3.5 rounded-xl border cursor-pointer transition-colors text-left flex flex-col justify-between space-y-2 ${
                isSelected
                  ? 'border-primary bg-primary/5 ring-1 ring-primary/40 font-semibold'
                  : 'border-border/70 bg-card hover:bg-muted/40 hover:border-primary/30'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-base font-bold text-foreground">{subj.title}</span>
                {isSelected && (
                  <span className="size-4 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                    <Check className="size-2.5 stroke-[3]" />
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground line-clamp-2">
                {subj.subtitle}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
