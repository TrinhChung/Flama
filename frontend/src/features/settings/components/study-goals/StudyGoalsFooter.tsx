import { useTranslation } from 'react-i18next'
import { CheckCircle2, RotateCcw, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface StudyGoalsFooterProps {
  isSaved: boolean
  onResetDefaults: () => void
  onSave: () => void
}

export function StudyGoalsFooter({
  isSaved,
  onResetDefaults,
  onSave,
}: StudyGoalsFooterProps) {
  const { t } = useTranslation('settings')

  return (
    <div className="p-4 rounded-xl border border-border/80 bg-card flex items-center justify-between gap-3">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={onResetDefaults}
        className="text-xs text-muted-foreground hover:text-foreground h-8"
      >
        <RotateCcw className="size-3.5 mr-1.5" /> {t('study_goals.actions.reset_defaults')}
      </Button>

      <Button
        type="button"
        size="sm"
        onClick={onSave}
        className="bg-primary text-primary-foreground font-semibold rounded-lg text-xs h-8 px-4 shadow-xs"
      >
        {isSaved ? (
          <>
            <CheckCircle2 className="size-3.5 mr-1.5" /> {t('study_goals.actions.saved')}
          </>
        ) : (
          <>
            <Save className="size-3.5 mr-1.5" /> {t('study_goals.actions.save')}
          </>
        )}
      </Button>
    </div>
  )
}
