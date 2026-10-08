import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import {
  faArrowUpRightFromSquare,
  faCircleCheck,
  faCode,
  faLayerGroup,
  faShareNodes,
  faSliders,
  faTrashCan,
} from '@fortawesome/free-solid-svg-icons'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import type { NoteTypeItem } from '../../hooks/useNoteTypeManager'

interface NoteTypeCardProps {
  item: NoteTypeItem
  index: number
  onDelete: (item: NoteTypeItem) => void
}

export function NoteTypeCard({ item, index, onDelete }: NoteTypeCardProps) {
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
              <FontAwesomeIcon icon={faLayerGroup} className="text-primary text-[10px]" />
              {t('manager.card.templates_badge', { count: item.templates?.length ?? 0 })}
            </Badge>
            <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md gap-1">
              <FontAwesomeIcon icon={faSliders} className="text-muted-foreground text-[10px]" />
              {t('manager.card.fields_badge', { count: item.field_defs?.length ?? 0 })}
            </Badge>
          </div>

          {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
            <Badge variant="outline" className="text-xs font-semibold rounded-md border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 gap-1">
              <FontAwesomeIcon icon={faCircleCheck} className="text-emerald-500 text-[10px]" />
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

      <div className="mt-4 pt-3 border-t border-border/60 flex flex-wrap items-center justify-between gap-1.5 sm:gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            asChild
            data-tour={index === 0 ? 'card-fields-btn' : undefined}
            className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl gap-1"
          >
            <Link to={`/flashcards/note-types/${item.id}/fields`}>
              <FontAwesomeIcon icon={faSliders} className="text-xs" />
              {t('manager.card.btn_fields')}
            </Link>
          </Button>

          <Button
            variant="outline"
            size="sm"
            asChild
            data-tour={index === 0 ? 'card-template-btn' : undefined}
            className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl gap-1"
          >
            <Link to={`/flashcards/note-types/${item.id}`}>
              <FontAwesomeIcon icon={faCode} className="text-xs" />
              {t('manager.card.btn_templates')}
            </Link>
          </Button>

          {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
            <Button
              variant="ghost"
              size="sm"
              asChild
              data-tour={index === 0 ? 'card-share-btn' : undefined}
              className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10 gap-1"
            >
              <Link to={`/marketplace/note-types/${item.id}`}>
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} className="text-xs" />
                {t('manager.card.btn_view')}
              </Link>
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              asChild
              data-tour={index === 0 ? 'card-share-btn' : undefined}
              className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl text-primary hover:text-primary hover:bg-primary/10 gap-1"
            >
              <Link to={`/marketplace/note-types/publish?id=${item.id}`}>
                <FontAwesomeIcon icon={faShareNodes} className="text-xs" />
                {t('manager.card.btn_share')}
              </Link>
            </Button>
          )}
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl shrink-0"
          onClick={() => onDelete(item)}
          title={t('manager.card.btn_delete_title')}
        >
          <FontAwesomeIcon icon={faTrashCan} className="text-xs" />
        </Button>
      </div>
    </Card>
  )
}
