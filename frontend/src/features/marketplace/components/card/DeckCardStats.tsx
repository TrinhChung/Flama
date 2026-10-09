import { BookOpen, Download, Layers, Star } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { DeckCardItem } from '../DeckCard'

interface DeckCardStatsProps {
  item: DeckCardItem
}

export function DeckCardStats({ item }: DeckCardStatsProps) {
  const { t } = useTranslation('marketplace')
  const cardCount = item.card_count || item.note_count

  return (
    <div className="flex items-center justify-between text-xs text-muted-foreground">
      {item.rating_avg !== undefined ? (
        <span className="inline-flex items-center gap-1 font-semibold text-foreground">
          <Star className="size-3.5 fill-amber-400 text-amber-500" />
          <span className="tabular-nums">
            {item.rating_avg.toFixed(1)}
            {item.rating_count ? (
              <span className="text-[11px] font-normal text-muted-foreground ml-0.5">
                ({item.rating_count})
              </span>
            ) : null}
          </span>
        </span>
      ) : (
        <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
          <BookOpen className="size-3 text-primary" />
          <span>
            {item.lesson_count
              ? `${item.lesson_count} ${t('card.lesson_unit')}`
              : `1 ${t('card.lesson_unit')}`}
          </span>
        </span>
      )}

      <div className="flex items-center gap-2 font-medium">
        {item.lesson_count && item.rating_avg !== undefined ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground hidden xs:inline-flex">
            <BookOpen className="size-3 text-primary" />
            <span className="tabular-nums">
              {item.lesson_count} {t('card.lesson_unit')}
            </span>
          </span>
        ) : null}

        {item.note_count ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Layers className="size-3 text-primary" />
            <span className="tabular-nums">
              {item.note_count.toLocaleString()} {t('card.note_unit')}
            </span>
          </span>
        ) : cardCount ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Layers className="size-3 text-primary" />
            <span className="tabular-nums">
              {cardCount} {t('card.card_unit')}
            </span>
          </span>
        ) : null}

        {item.install_count !== undefined ? (
          <span className="inline-flex items-center gap-1">
            <Download className="size-3.5 text-primary" />
            <span className="tabular-nums">
              {item.install_count.toLocaleString()} {t('card.install_unit')}
            </span>
          </span>
        ) : null}
      </div>
    </div>
  )
}
