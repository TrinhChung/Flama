import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'

export function GuideStepsTab() {
  const { t } = useTranslation('note_types')

  return (
    <div className="grid sm:grid-cols-2 gap-4">
      <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
        <div className="flex items-center gap-3">
          <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
            1
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.steps_tab.step1_title')}
          </h4>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed pl-10">
          {t('guide.steps_tab.step1_desc')}
        </p>
      </Card>

      <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
        <div className="flex items-center gap-3">
          <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
            2
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.steps_tab.step2_title')}
          </h4>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed pl-10">
          {t('guide.steps_tab.step2_desc')}
        </p>
      </Card>

      <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
        <div className="flex items-center gap-3">
          <div className="size-7 rounded-full bg-primary/10 text-primary font-bold text-xs flex items-center justify-center shrink-0">
            3
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.steps_tab.step3_title')}
          </h4>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed pl-10">
          {t('guide.steps_tab.step3_desc')}
        </p>
      </Card>

      <Card className="p-4 sm:p-5 border-border/80 rounded-2xl bg-card space-y-2">
        <div className="flex items-center gap-3">
          <div className="size-7 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-bold text-xs flex items-center justify-center shrink-0">
            4
          </div>
          <h4 className="text-sm font-bold text-foreground">
            {t('guide.steps_tab.step4_title')}
          </h4>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed pl-10">
          {t('guide.steps_tab.step4_desc')}
        </p>
      </Card>
    </div>
  )
}
