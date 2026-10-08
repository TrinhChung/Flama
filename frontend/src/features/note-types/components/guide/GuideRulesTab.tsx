import { useTranslation } from 'react-i18next'
import { Card } from '@/components/ui/card'

export function GuideRulesTab() {
  const { t } = useTranslation('note_types')

  return (
    <div className="space-y-3">
      <Card className="p-4 border-amber-500/30 bg-amber-500/5 rounded-2xl space-y-1.5">
        <h4 className="text-sm font-bold text-amber-900 dark:text-amber-200 flex items-center gap-2">
          {t('guide.rules_tab.rule1_title')}
        </h4>
        <p className="text-xs text-amber-800 dark:text-amber-300/90 leading-relaxed">
          {t('guide.rules_tab.rule1_desc')}
        </p>
      </Card>

      <Card className="p-4 border-blue-500/30 bg-blue-500/5 rounded-2xl space-y-1.5">
        <h4 className="text-sm font-bold text-blue-900 dark:text-blue-200 flex items-center gap-2">
          {t('guide.rules_tab.rule2_title')}
        </h4>
        <p className="text-xs text-blue-800 dark:text-blue-300/90 leading-relaxed">
          {t('guide.rules_tab.rule2_desc')}
        </p>
      </Card>

      <Card className="p-4 border-emerald-500/30 bg-emerald-500/5 rounded-2xl space-y-1.5">
        <h4 className="text-sm font-bold text-emerald-900 dark:text-emerald-200 flex items-center gap-2">
          {t('guide.rules_tab.rule3_title')}
        </h4>
        <p className="text-xs text-emerald-800 dark:text-emerald-300/90 leading-relaxed">
          {t('guide.rules_tab.rule3_desc')}
        </p>
      </Card>
    </div>
  )
}
