import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus } from '@fortawesome/free-solid-svg-icons'
import { ChevronDown, ChevronUp, GripVertical, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { FieldDefItem } from '../../hooks/useNoteTypeFields'

interface FieldListCardProps {
  fields: FieldDefItem[]
  selectedFieldId: string | null
  isAddingField: boolean
  onSelectField: (id: string) => void
  onStartAddField: () => void
  onDragStart: (id: string) => void
  onDrop: (targetId: string) => void
  onMoveUp: (index: number) => void
  onMoveDown: (index: number) => void
  isReordering: boolean
}

export function FieldListCard({
  fields,
  selectedFieldId,
  isAddingField,
  onSelectField,
  onStartAddField,
  onDragStart,
  onDrop,
  onMoveUp,
  onMoveDown,
  isReordering,
}: FieldListCardProps) {
  const { t } = useTranslation('note_types')

  return (
    <Card className="border-border/80 shadow-xs rounded-2xl h-full flex flex-col overflow-hidden bg-card">
      <CardHeader className="p-4 sm:p-5 flex flex-row items-center justify-between pb-2 sm:pb-2">
        <CardTitle className="text-sm font-bold text-foreground">
          {t('fields.list.title')}
        </CardTitle>
        <Button
          size="sm"
          variant="outline"
          className="h-8 px-2.5 text-xs font-semibold rounded-xl gap-1.5"
          onClick={onStartAddField}
        >
          <FontAwesomeIcon icon={faPlus} className="text-xs" /> {t('fields.list.add_btn')}
        </Button>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-0 flex-1 space-y-3">
        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
          <Info className="size-3.5 text-primary shrink-0" /> {t('fields.list.reorder_hint')}
        </p>

        <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
          {fields.map((field, index) => (
            <div
              key={field.id}
              draggable
              onDragStart={() => onDragStart(field.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(field.id)}
              onClick={() => onSelectField(field.id)}
              className={`flex items-center gap-2 sm:gap-3 p-3 rounded-xl border transition-all cursor-pointer select-none ${
                selectedFieldId === field.id && !isAddingField
                  ? 'border-primary bg-primary/10 shadow-xs'
                  : 'border-border/60 bg-card hover:bg-muted/40 hover:border-primary/40'
              }`}
            >
              <GripVertical className="size-4 text-muted-foreground/60 shrink-0 hidden sm:block cursor-grab" />

              {/* Touch Reorder Buttons */}
              <div className="flex items-center gap-0.5 shrink-0">
                <button
                  type="button"
                  disabled={index === 0 || isReordering}
                  onClick={(e) => {
                    e.stopPropagation()
                    onMoveUp(index)
                  }}
                  className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-25 disabled:pointer-events-none transition-colors cursor-pointer"
                  title={t('fields.list.move_up')}
                  aria-label={t('fields.list.move_up')}
                >
                  <ChevronUp className="size-3.5" />
                </button>
                <button
                  type="button"
                  disabled={index === fields.length - 1 || isReordering}
                  onClick={(e) => {
                    e.stopPropagation()
                    onMoveDown(index)
                  }}
                  className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-25 disabled:pointer-events-none transition-colors cursor-pointer"
                  title={t('fields.list.move_down')}
                  aria-label={t('fields.list.move_down')}
                >
                  <ChevronDown className="size-3.5" />
                </button>
              </div>

              <span className="flex-1 font-semibold text-sm truncate text-foreground min-w-0">
                {field.name}
              </span>

              <Badge variant="outline" className="text-[10px] sm:text-[11px] font-semibold lowercase px-2 py-0.5 rounded-md shrink-0">
                {field.field_type}
              </Badge>
              {field.identity_role === 'primary' ? (
                <Badge className="text-[10px] shrink-0">{t('fields.list.primary_badge')}</Badge>
              ) : null}
            </div>
          ))}

          {!fields.length ? (
            <div className="p-6 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
              {t('fields.list.empty')}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}
