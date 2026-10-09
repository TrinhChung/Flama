import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus } from '@fortawesome/free-solid-svg-icons'
import { ChevronDown, ChevronUp, GripVertical, Info, Save } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
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
  isOrderDirty = false,
  onSaveOrder,
  onDiscardOrder,
}: FieldListCardProps) {
  const { t } = useTranslation('note_types')
  const [search] = useState('')
  const visibleFields = fields.filter((field) => field.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))

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
          disabled={isReordering}
        >
          <FontAwesomeIcon icon={faPlus} className="text-xs" /> {t('fields.list.add_btn')}
        </Button>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-0 flex-1 space-y-3">
        {isOrderDirty && (
          <div className="flex items-center justify-between gap-2 p-2.5 rounded-xl border border-primary/30 bg-primary/5 text-xs animate-in fade-in duration-150">
            <span className="font-medium text-foreground truncate">
              {t('fields.list.order_changed')}
            </span>
            <div className="flex items-center gap-1.5 shrink-0">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                onClick={onDiscardOrder}
                disabled={isReordering}
              >
                {t('fields.list.discard_order')}
              </Button>
              <Button
                type="button"
                size="sm"
                className="h-7 px-2.5 text-xs font-semibold gap-1.5"
                onClick={onSaveOrder}
                disabled={isReordering}
              >
                <Save className="size-3" />
                {t('fields.list.save_order')}
              </Button>
            </div>
          </div>
        )}
        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
          <Info className="size-3.5 text-primary shrink-0" /> {t('fields.list.reorder_hint')}
        </p>
        <Input value={search} onChange={(event) => setSearch(event.target.value)}
          aria-label={t('setup.search_fields')} placeholder={t('setup.search_fields')}
          className="rounded-xl" />

        <div className="space-y-2 max-h-[560px] overflow-y-auto pr-1">
          {visibleFields.map((field) => {
            const index = fields.findIndex((item) => item.id === field.id)
            return (
            <div
              key={field.id}
              draggable={!isReordering}
              onDragStart={() => onDragStart(field.id)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => onDrop(field.id)}
              className={`flex items-center gap-1.5 p-2 rounded-xl border transition-colors select-none ${
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
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-25 disabled:pointer-events-none transition-colors cursor-pointer"
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
                  className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted disabled:opacity-25 disabled:pointer-events-none transition-colors cursor-pointer"
                  title={t('fields.list.move_down')}
                  aria-label={t('fields.list.move_down')}
                >
                  <ChevronDown className="size-3.5" />
                </button>
              </div>

              <button type="button" disabled={isReordering} onClick={() => onSelectField(field.id)}
                aria-pressed={selectedFieldId === field.id && !isAddingField}
                className="min-w-0 flex-1 rounded-lg p-1.5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60">
                <span className="block truncate font-semibold text-sm text-foreground">{field.name}</span>
                <span className="mt-1 flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">{t(`setup.types.${field.field_type}.label`, { defaultValue: field.field_type })}</span>
                  {field.required && <Badge variant="outline" className="text-[10px]">{t('setup.required_badge')}</Badge>}
                  {field.identity_role === 'primary' && <Badge className="text-[10px]">{t('fields.list.primary_badge')}</Badge>}
                </span>
              </button>
            </div>
          )})}

          {!fields.length ? (
            <div className="p-6 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
              {t('fields.list.empty')}
            </div>
          ) : null}
          {fields.length > 0 && !visibleFields.length && <p className="p-6 text-center text-xs text-muted-foreground">{t('setup.no_field_results')}</p>}
        </div>
      </CardContent>
    </Card>
  )
}
