import { Check, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import '@/shared/config/i18n'
import type { ReviewDecision } from '../../types'

export function ReviewDecisionBadge({ decision }: { decision: ReviewDecision }) {
  const { t } = useTranslation('collaboration')
  return decision === 'accepted' ? (
    <Badge variant="outline" className="h-5 border-emerald-500/40 px-1.5 text-[10px] text-emerald-700 dark:text-emerald-300">
      <Check />
      {t('notes.decision_accepted', 'Đã nhận')}
    </Badge>
  ) : (
    <Badge variant="outline" className="h-5 px-1.5 text-[10px] text-muted-foreground">
      <X />
      {t('notes.decision_declined', 'Không nhận')}
    </Badge>
  )
}
