import React from 'react'
import { useTranslation } from 'react-i18next'
import { Check } from 'lucide-react'
import { WIZARD_STEPS, type WizardStepConfig, type WizardStepId } from '../config/wizardSteps'

export type { WizardStepId }

export interface WizardStep {
  id: WizardStepId
  number: number
  label: string
  shortLabel: string
  icon: WizardStepConfig['icon']
}

export interface WorksheetWizardStepperProps {
  currentStep: WizardStepId
  onSelectStep?: (step: WizardStepId) => void
  isStandalone?: boolean
  className?: string
}

export const WorksheetWizardStepper: React.FC<WorksheetWizardStepperProps> = ({
  currentStep,
  onSelectStep,
  isStandalone = false,
  className = '',
}) => {
  const { t } = useTranslation('worksheets')

  // If standalone (no deck required), step 2 (mapping) is skipped
  const visibleSteps = React.useMemo<WizardStep[]>(
    () =>
      WIZARD_STEPS
        .filter((step) => !isStandalone || step.id !== 'mapping')
        .map((step, idx) => ({
          id: step.id,
          number: isStandalone ? idx + 1 : step.number,
          label: t(step.labelKey, step.label),
          shortLabel: t(step.shortLabelKey, step.shortLabel),
          icon: step.icon,
        })),
    [isStandalone, t],
  )

  const currentIndex = visibleSteps.findIndex((s) => s.id === currentStep)
  const currentStepObj = visibleSteps[currentIndex] || visibleSteps[0]
  const progressPercent = Math.round(((currentIndex + 1) / visibleSteps.length) * 100)

  return (
    <div className={`w-full ${className}`}>
      {/* Desktop Stepper */}
      <div className="hidden sm:flex items-center justify-between gap-2 px-4 py-2.5 bg-muted/40 border-b border-border/80">
        {visibleSteps.map((step, idx) => {
          const isCompleted = idx < currentIndex
          const isCurrent = step.id === currentStep
          const isClickable = Boolean(onSelectStep && (isCompleted || isCurrent))
          const StepIcon = step.icon

          return (
            <React.Fragment key={step.id}>
              {idx > 0 && (
                <div
                  className={`h-0.5 flex-1 min-w-4 transition-colors ${
                    idx <= currentIndex ? 'bg-primary' : 'bg-border/80'
                  }`}
                />
              )}
              <button
                type="button"
                disabled={!isClickable}
                onClick={() => isClickable && onSelectStep?.(step.id)}
                className={`flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isCurrent
                    ? 'bg-primary text-primary-foreground shadow-xs ring-2 ring-primary/20'
                    : isCompleted
                    ? 'text-foreground hover:bg-muted/70 cursor-pointer'
                    : 'text-muted-foreground cursor-not-allowed opacity-60'
                }`}
              >
                <div
                  className={`size-5.5 rounded-full flex items-center justify-center text-[11px] font-bold shrink-0 ${
                    isCurrent
                      ? 'bg-primary-foreground text-primary'
                      : isCompleted
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted border border-border text-muted-foreground'
                  }`}
                >
                  {isCompleted ? <Check className="size-3 stroke-[3]" /> : step.number}
                </div>
                <div className="flex items-center gap-1.5">
                  <StepIcon className="size-3.5 shrink-0" />
                  <span className="truncate">{step.label}</span>
                </div>
              </button>
            </React.Fragment>
          )
        })}
      </div>

      {/* Mobile Compact Stepper */}
      <div className="sm:hidden px-3.5 py-2 bg-muted/40 border-b border-border/80 space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-1.5 font-bold text-foreground">
            <span className="size-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-[10.5px]">
              {currentStepObj.number}
            </span>
            <span>{currentStepObj.label}</span>
          </div>
          <span className="text-[11px] font-semibold text-muted-foreground">
            {t('stepper.step_counter', 'Bước {{current}}/{{total}}', {
              current: currentStepObj.number,
              total: visibleSteps.length,
            })}
          </span>
        </div>
        {/* Progress Bar */}
        <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary transition-all duration-300 rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
    </div>
  )
}
