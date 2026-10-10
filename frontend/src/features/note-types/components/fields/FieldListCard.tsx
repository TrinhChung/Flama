import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus } from '@fortawesome/free-solid-svg-icons'
import { ChevronDown, ChevronUp, GripVertical, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
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
  isOrderDirty?: boolean
  onSaveOrder?: () => void
  onDiscardOrder?: () => void
  className?: string
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
  className,
}: FieldListCardProps) {
  const { t } = useTranslation('note_types')
  const [search, setSearch] = useState('')
  const visibleFields = fields.filter((field) => field.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))

  return (
    <Card className={cn('border-border/80 shadow-xs rounded-2xl h-full flex flex-col overflow-hidden bg-card', className)}>
      <CardHeader className="p-4 sm:p-5 pb-3 flex flex-row items-center justify-between shrink-0 border-b border-border/40">
        <CardTitle className="text-sm font-bold text-foreground">
          {t('fields.list.title')}
        </CardTitle>
        <Button
          size="sm"
          variant="outline"
          className="h-8 px-2.5 text-xs font-semibold rounded-xl gap-1.5"
          onClick={onStartAddField}
          disabled={isReordering}
        >
          <FontAwesomeIcon icon={faPlus} className="text-xs" /> {t('fields.list.add_btn')}
        </Button>
      </CardHeader>
      <CardContent className="p-3.5 sm:p-4 flex-1 min-h-0 flex flex-col gap-2.5 overflow-hidden">
        <div className="shrink-0 space-y-1.5">
          <p className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <Info className="size-3 text-primary shrink-0" /> {t('fields.list.reorder_hint')}
          </p>
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            aria-label={t('setup.search_fields')}
            placeholder={t('setup.search_fields')}
            className="h-8 text-xs rounded-xl"
          />
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-1">
          {visibleFields.map((field) => {
            const index = fields.findIndex((item) => item.id === field.id)
            const isSelected = selectedFieldId === field.id && !isAddingField
            return (
              <div
                key={field.id}
                draggable={!isReordering}
                onDragStart={() => onDragStart(field.id)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => onDrop(field.id)}
                className={cn(
                  'group flex items-center gap-1 px-2 py-1 rounded-xl border transition-all select-none',
                  isSelected
                    ? 'border-primary/50 bg-primary/10 shadow-2xs font-medium'
                    : 'border-transparent hover:border-border/40 hover:bg-muted/50'
                )}
              >
                <GripVertical className="size-3.5 text-muted-foreground/30 group-hover:text-muted-foreground/70 shrink-0 hidden sm:block cursor-grab" />

                {/* Touch / Quick Reorder Buttons */}
                <div className="flex items-center gap-0.5 shrink-0 opacity-80 sm:opacity-60 sm:group-hover:opacity-100 transition-opacity">
                  <button
                    type="button"
                    disabled={index === 0 || isReordering}
                    onClick={(e) => {
                      e.stopPropagation()
                      onMoveUp(index)
                    }}
                    className="p-1.5 sm:p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-20 disabled:pointer-events-none transition-colors cursor-pointer"
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
                    className="p-1.5 sm:p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-20 disabled:pointer-events-none transition-colors cursor-pointer"
                    title={t('fields.list.move_down')}
                    aria-label={t('fields.list.move_down')}
                  >
                    <ChevronDown className="size-3.5" />
                  </button>
                </div>

                <button
                  type="button"
                  disabled={isReordering}
                  onClick={() => onSelectField(field.id)}
                  aria-pressed={isSelected}
                  className="min-w-0 flex-1 flex items-center justify-between gap-2 rounded-lg px-1.5 py-1 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60"
                >
                  <span className="truncate text-xs sm:text-sm font-medium text-foreground">
                    {field.name}
                  </span>
                  <div className="flex items-center gap-1 shrink-0">
                    {field.identity_role === 'primary' && (
                      <Badge className="text-[9px] px-1.5 py-0 h-4 font-normal">
                        {t('fields.list.primary_badge')}
                      </Badge>
                    )}
                    {field.required && field.identity_role !== 'primary' && (
                      <Badge variant="outline" className="text-[9px] px-1.5 py-0 h-4 text-muted-foreground font-normal">
                        {t('setup.required_badge')}
                      </Badge>
                    )}
                  </div>
                </button>
              </div>
            )
          })}

          {!fields.length ? (
            <div className="p-6 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
              {t('fields.list.empty')}
            </div>
          ) : null}
          {fields.length > 0 && !visibleFields.length && (
            <p className="p-6 text-center text-xs text-muted-foreground">
              {t('setup.no_field_results')}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
