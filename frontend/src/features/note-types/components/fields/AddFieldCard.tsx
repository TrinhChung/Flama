import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle, Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { FIELD_TYPES } from '../../hooks/useNoteTypeFields'
import { FieldFormColumns } from './FieldFormColumns'

interface AddFieldCardProps {
  newName: string
  onNewNameChange: (value: string) => void
  newType: string
  onNewTypeChange: (value: string) => void
  onSubmit: (e: React.FormEvent) => void
  onCancel: () => void
  isPending: boolean
  required: boolean
  onRequiredChange: (value: boolean) => void
  identity: boolean
  onIdentityChange: (value: boolean) => void
  preview?: ReactNode
  error?: string | null
}

export function AddFieldCard({
  newName,
  onNewNameChange,
  newType,
  onNewTypeChange,
  onSubmit,
  onCancel,
  isPending,
  required,
  onRequiredChange,
  identity,
  onIdentityChange,
  preview,
  error,
}: AddFieldCardProps) {
  const { t } = useTranslation('note_types')

  return (
    <Card className="border-primary/30 bg-card shadow-md rounded-2xl">
      <CardHeader className="p-4 sm:p-5 pb-2">
        <CardTitle className="text-sm font-bold text-primary">
          {t('fields.add_card.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="@container p-4 sm:p-5 pt-0">
        <form onSubmit={onSubmit} className="space-y-4" aria-busy={isPending}>
          <fieldset disabled={isPending} className="space-y-4">
          <FieldFormColumns preview={preview} settings={<>
          <div className="space-y-1.5">
            <Label htmlFor="new-field-name">{t('fields.add_card.field_name')}</Label>
            <Input
              id="new-field-name"
              placeholder={t('fields.add_card.placeholder')}
              value={newName}
              onChange={(e) => onNewNameChange(e.target.value)}
              className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
              autoFocus
              aria-invalid={Boolean(error)} aria-describedby={error ? 'new-field-error' : undefined}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="new-field-type">{t('fields.add_card.field_type')}</Label>
            <NativeSelect
              id="new-field-type"
              value={newType}
              disabled={identity}
              onChange={(e) => onNewTypeChange(e.target.value)}
              className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
            >
              {FIELD_TYPES.map((type) => (
                <NativeSelectOption key={type} value={type}>
                  {t(`setup.types.${type}.label`)}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="flex items-center gap-2">
            <Checkbox id="new-field-required" checked={required} disabled={identity} onCheckedChange={(checked) => onRequiredChange(Boolean(checked))} />
            <Label htmlFor="new-field-required">{t('fields.edit_card.required')}</Label>
          </div>
          <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/20 p-3">
            <Checkbox id="new-field-identity" checked={identity} onCheckedChange={(checked) => {
              const enabled = Boolean(checked)
              onIdentityChange(enabled)
              if (enabled) { onNewTypeChange('text'); onRequiredChange(true) }
            }} />
            <div className="space-y-1"><Label htmlFor="new-field-identity">{t('fields.edit_card.primary_identity')}</Label><p className="text-xs text-muted-foreground">{t('fields.edit_card.primary_identity_desc')}</p></div>
          </div>
          </>} />
          {error && <p id="new-field-error" role="alert" className="text-xs text-destructive">{error}</p>}

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
          </fieldset>
        </form>
      </CardContent>
    </Card>
  )
}
