import { Check } from 'lucide-react'
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
  return (
    <Card className="rounded-2xl border-border/80 bg-card shadow-xs">
      <CardContent className="p-3 sm:p-4">
        <nav className="flex flex-col sm:flex-row gap-2 sm:gap-4">
          {WIZARD_STEPS.map((s) => {
            const Icon = s.icon
            const isActive = currentStep === s.id
            const isCompleted = currentStep > s.id

            return (
              <button
                key={s.id}
                type="button"
                onClick={() => goToStep(s.id)}
                className={`flex-1 flex items-center gap-3 p-2.5 sm:p-3 rounded-xl text-left transition-all cursor-pointer ${
                  isActive
                    ? 'bg-muted/80 text-foreground font-semibold ring-1 ring-border shadow-xs'
                    : isCompleted
                    ? 'text-foreground/80 hover:bg-muted/50'
                    : 'text-muted-foreground/60 hover:text-muted-foreground hover:bg-muted/30'
                }`}
              >
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-foreground text-background shadow-xs'
                      : isCompleted
                      ? 'bg-primary/15 text-primary'
                      : 'bg-muted text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-bold leading-tight truncate">
                    {s.id}. {s.title}
                  </div>
                  <div className="text-[10px] text-muted-foreground truncate hidden sm:block">
                    {s.sub}
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
