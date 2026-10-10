import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { CheckCircle2, Eye, Layers, SlidersHorizontal } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { NoteTypeItem } from '../../hooks/useNoteTypeManager'

interface NoteTypeCardProps {
  item: NoteTypeItem
  index: number
}

export function NoteTypeCard({ item, index }: NoteTypeCardProps) {
  const { t } = useTranslation('note_types')

  return (
    <Card
      data-tour={index === 0 ? 'card-first' : undefined}
      className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
    >
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <Badge variant="secondary" className="px-2 py-0.5 text-xs font-semibold rounded-md gap-1">
              <Layers className="text-primary size-3" />
              {t('manager.card.templates_badge', { count: item.templates?.length ?? 0 })}
            </Badge>
            <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md gap-1">
              <SlidersHorizontal className="text-muted-foreground size-3" />
              {t('manager.card.fields_badge', { count: item.field_defs?.length ?? 0 })}
            </Badge>
          </div>

          {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
            <Badge variant="outline" className="text-xs font-semibold rounded-md border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 gap-1">
              <CheckCircle2 className="text-emerald-500 size-3" />
              {t('manager.card.shared_badge')}
            </Badge>
          ) : null}
        </div>

        <div>
          <h3 className="text-base font-bold text-foreground group-hover:text-primary transition-colors">
            <Link to={`/flashcards/note-types/${item.id}/fields`} className="hover:underline">
              {item.name}
            </Link>
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            ID: <span className="font-mono text-[11px]">{item.id}</span>
          </p>
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-border/60">
        <Button
          size="sm"
          asChild
          data-tour={index === 0 ? 'card-view-btn' : undefined}
          className="w-full h-8.5 sm:h-9 text-xs font-bold rounded-xl shadow-xs gap-1.5"
        >
          <Link to={`/flashcards/note-types/${item.id}/fields`}>
            <Eye className="size-3.5" />
            {t('manager.card.btn_view', { defaultValue: 'Xem' })}
          </Link>
        </Button>
      </div>
    </Card>
  )
}
