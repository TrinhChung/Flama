import '@/shared/config/i18n'
import { RotateCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type CardSide = 'front' | 'back'

export interface CardSideToggleProps {
  side: CardSide
  onSideChange: (side: CardSide) => void
  /** `sm` fits panel headers; `default` matches h-8 toolbars. */
  size?: 'sm' | 'default'
  /** Feature-specific labels; defaults to the shared card preview wording. */
  frontLabel?: string
  backLabel?: string
  /** Shows the flip icon on the back button (default: true). */
  showFlipIcon?: boolean
  className?: string
}

/** Segmented front/back switch shared by every card preview surface. */
export function CardSideToggle({ side, onSideChange, size = 'sm', frontLabel, backLabel, showFlipIcon = true, className }: CardSideToggleProps) {
  const { t } = useTranslation('common')
  const buttonClass = cn('text-xs font-bold transition-all', size === 'sm' ? 'h-7 px-3 rounded-lg' : 'h-8 px-3.5 rounded-md')
  return (
    <div role="group" aria-label={t('card_preview.side_group')}
      className={cn('inline-flex border p-0.5 shadow-2xs', size === 'sm' ? 'rounded-xl border-border/80 bg-muted/30' : 'rounded-lg bg-card', className)}>
      <Button type="button" size="sm" variant={side === 'front' ? 'default' : 'ghost'} aria-pressed={side === 'front'}
        className={buttonClass} onClick={() => onSideChange('front')}>
        {frontLabel ?? t('card_preview.front')}
      </Button>
      <Button type="button" size="sm" variant={side === 'back' ? 'default' : 'ghost'} aria-pressed={side === 'back'}
        className={buttonClass} onClick={() => onSideChange('back')}>
        {showFlipIcon && <RotateCcw className="size-3 mr-1" />}{backLabel ?? t('card_preview.back')}
      </Button>
    </div>
  )
}
