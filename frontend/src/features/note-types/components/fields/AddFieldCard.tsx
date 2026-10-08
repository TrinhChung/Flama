import { useTranslation } from 'react-i18next'
import { LoaderCircle, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { FIELD_TYPES } from '../../hooks/useNoteTypeFields'

interface AddFieldCardProps {
  newName: string
  onNewNameChange: (value: string) => void
  newType: string
  onNewTypeChange: (value: string) => void
  onSubmit: (e: React.FormEvent) => void
  onCancel: () => void
  isPending: boolean
}

export function AddFieldCard({
  newName,
  onNewNameChange,
  newType,
  onNewTypeChange,
  onSubmit,
  onCancel,
  isPending,
}: AddFieldCardProps) {
  const { t } = useTranslation('note_types')

  return (
    <Card className="border-primary/30 bg-card shadow-md rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-2">
        <CardTitle className="text-sm font-bold text-primary">
          {t('fields.add_card.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-0">
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="new-field-name">{t('fields.add_card.field_name')}</Label>
            <Input
              id="new-field-name"
              placeholder={t('fields.add_card.placeholder')}
              value={newName}
              onChange={(e) => onNewNameChange(e.target.value)}
              className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="new-field-type">{t('fields.add_card.field_type')}</Label>
            <NativeSelect
              id="new-field-type"
              value={newType}
              onChange={(e) => onNewTypeChange(e.target.value)}
              className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
            >
              {FIELD_TYPES.map((type) => (
                <NativeSelectOption key={type} value={type}>
                  {type}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>

          <div className="flex justify-end gap-2.5 pt-3 border-t">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
              className="h-9 sm:h-10 px-4 text-xs sm:text-sm font-bold rounded-xl"
            >
              {t('fields.add_card.cancel')}
            </Button>
            <Button
              type="submit"
              size="sm"
              disabled={isPending}
              className="h-9 sm:h-10 px-4 font-bold text-xs sm:text-sm rounded-xl shadow-xs"
            >
              {isPending ? (
                <LoaderCircle className="size-4 animate-spin mr-1" />
              ) : (
                <>
                  <Plus className="size-4 mr-1" />
                  {t('fields.add_card.submit')}
                </>
              )}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  )
}
