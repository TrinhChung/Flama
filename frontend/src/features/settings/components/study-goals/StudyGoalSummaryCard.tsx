import { Trans, useTranslation } from 'react-i18next'
import { Goal } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import type { SubjectOptionConfig } from '@/features/onboarding/constants'
import type { OnboardingPreferences } from '@/features/onboarding/types'

interface StudyGoalSummaryCardProps {
  preferences: OnboardingPreferences
  currentSubjectConfig: SubjectOptionConfig
  currentLevelLabel: string
  currentDailyTargetObj: { value: number; label: string; timeEstimate: string; description: string }
  currentStudyTimeObj: { value: string; label: string; sub: string }
}

export function StudyGoalSummaryCard({
  preferences,
  currentSubjectConfig,
  currentLevelLabel,
  currentDailyTargetObj,
  currentStudyTimeObj,
}: StudyGoalSummaryCardProps) {
  const { t } = useTranslation('settings')

  return (
    <Card className="border border-border/80 bg-card rounded-xl shadow-2xs">
      <CardContent className="p-4 sm:p-5 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Goal className="size-4 text-primary" />
            <span className="text-sm font-bold text-foreground">
              {t('study_goals.summary.current_goal')}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-wrap text-xs">
            <Badge variant="outline" className="font-semibold text-primary border-primary/30">
              {currentSubjectConfig.title} • {currentLevelLabel}
            </Badge>
            <Badge variant="secondary" className="font-medium">
              {t('study_goals.summary.new_cards_per_day', { count: preferences.dailyNewCards })}
            </Badge>
            <Badge variant="secondary" className="font-medium">
              {currentStudyTimeObj.label}
            </Badge>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          <Trans
            i18nKey="study_goals.summary.roadmap_applied"
            t={t}
            values={{
              subject: currentSubjectConfig.title,
              count: preferences.dailyNewCards,
              time: currentDailyTargetObj.timeEstimate,
            }}
            components={{
              bold: <strong />,
            }}
          />
        </p>
      </CardContent>
    </Card>
  )
}
