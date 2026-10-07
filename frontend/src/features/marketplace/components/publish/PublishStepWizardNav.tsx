import '@/shared/config/i18n'
import { Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { WIZARD_STEPS } from './PublishWizardTypes'

interface PublishStepWizardNavProps {
  currentStep: number
  goToStep: (stepNumber: number) => void
}

export function PublishStepWizardNav({
  currentStep,
  goToStep,
}: PublishStepWizardNavProps) {
  const { t } = useTranslation('marketplace')

  return (
    <Card className="rounded-2xl border-border/80 bg-card shadow-xs">
      <CardContent className="p-3 sm:p-4">
        <nav className="flex flex-col sm:flex-row gap-2 sm:gap-4">
          {WIZARD_STEPS.map((s) => {
            const isActive = currentStep === s.id
            const isCompleted = currentStep > s.id
            const stepTitle = t(`publish_deck.steps.step${s.id}` as any, s.title)
            const stepSub = t(`publish_deck.steps.step${s.id}_sub` as any, s.sub)

            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goToStep(s.id)}
                className={`flex-1 flex items-center gap-2.5 p-2.5 sm:p-3 rounded-xl text-left transition-all cursor-pointer border ${
                  isActive
                    ? 'border-primary/60 bg-primary/5 text-foreground font-semibold ring-1 ring-primary/20 shadow-2xs'
                    : isCompleted
                    ? 'border-border/70 bg-card hover:bg-muted/40 text-foreground font-medium'
                    : 'border-border/40 bg-muted/20 text-muted-foreground hover:bg-muted/30 font-medium'
                }`}
              >
                <div
                  className={`w-6 h-6 sm:w-7 sm:h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-2xs'
                      : isCompleted
                      ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-3.5 h-3.5 stroke-[2.5]" /> : s.id}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-bold leading-tight truncate">
                    {stepTitle}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate hidden sm:block">
                    {stepSub}
                  </div>
                </div>
              </button>
            )
          })}
        </nav>
      </CardContent>
    </Card>
  )
}
