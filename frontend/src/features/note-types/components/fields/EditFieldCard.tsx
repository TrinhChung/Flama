import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Check, LoaderCircle, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { cn } from '@/lib/utils'
import { FIELD_TYPES, type FieldDefItem } from '../../hooks/useNoteTypeFields'
import { FieldFormColumns } from './FieldFormColumns'

interface EditFieldCardProps {
  selectedField: FieldDefItem
  editName: string
  onEditNameChange: (value: string) => void
  editType: string
  onEditTypeChange: (value: string) => void
  editRequired: boolean
  onEditRequiredChange: (value: boolean) => void
  editIdentity: boolean
  onEditIdentityChange: (value: boolean) => void
  onSubmit: (e: React.FormEvent) => void
  onDelete: () => void
  isUpdating: boolean
  isDeleting: boolean
  isDirty?: boolean
  error?: string | null
  preview?: ReactNode
  usage?: ReactNode
  /** Entry to the array conversion tool, shown under the type selector. */
  typeConversion?: ReactNode
  className?: string
}

export function EditFieldCard({
  selectedField,
  editName,
  onEditNameChange,
  editType,
  onEditTypeChange,
  editRequired,
  onEditRequiredChange,
  editIdentity,
  onEditIdentityChange,
  onSubmit,
  onDelete,
  isUpdating,
  isDeleting,
  isDirty,
  error,
  preview,
  usage,
  typeConversion,
  className,
}: EditFieldCardProps) {
  const { t } = useTranslation('note_types')

  return (
    <Card className={cn('border-border/80 bg-card shadow-xs rounded-2xl h-full flex flex-col overflow-hidden', className)}>
      <CardHeader className="p-3.5 sm:p-5 pb-2.5 sm:pb-3 shrink-0 border-b border-border/40">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm font-bold truncate">
            {selectedField.name}
          </CardTitle>
          <span className="text-xs text-muted-foreground font-normal shrink-0">
            {t(`setup.types.${editType}.label`, { defaultValue: editType })}
          </span>
        </div>
      </CardHeader>
      <CardContent className="@container p-3.5 sm:p-5 flex-1 min-h-0 flex flex-col overflow-hidden">
        <form onSubmit={onSubmit} className="flex-1 min-h-0 flex flex-col" aria-busy={isUpdating || isDeleting}>
          <fieldset disabled={isUpdating || isDeleting} className="flex-1 min-h-0 flex flex-col">
            <div className="flex-1 min-h-0 overflow-y-auto pr-1 sm:pr-1.5 space-y-3.5 sm:space-y-4">
              <FieldFormColumns preview={preview} settings={<>
                <div className="space-y-1.5">
                  <Label htmlFor="edit-field-name">{t('fields.edit_card.field_name')}</Label>
                  <Input
                    id="edit-field-name"
                    value={editName}
                    onChange={(e) => onEditNameChange(e.target.value)}
                    className="h-8 sm:h-9 text-xs sm:text-sm rounded-xl bg-background"
                    aria-invalid={Boolean(error)} aria-describedby={error ? 'edit-field-error' : undefined}
                  />
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="edit-field-type">{t('fields.edit_card.field_type')}</Label>
                  <NativeSelect
                    id="edit-field-type"
                    value={editType}
                    onChange={(e) => onEditTypeChange(e.target.value)}
                    disabled={editIdentity}
                    className="h-8 sm:h-9 text-xs sm:text-sm rounded-xl bg-background"
                  >
                    {FIELD_TYPES.map((type) => (
                      // Existing values must be split first, so switching to
                      // array goes through the conversion tool instead.
                      <NativeSelectOption
                        key={type}
                        value={type}
                        disabled={type === 'array' && selectedField.field_type !== 'array'}
                      >
                        {t(`setup.types.${type}.label`)}
                      </NativeSelectOption>
                    ))}
                  </NativeSelect>
                  {typeConversion}
                </div>

                <div className="flex items-center space-x-2 pt-0.5">
                  <Checkbox
                    id="edit-field-required"
                    checked={editRequired}
                    disabled={editIdentity}
                    onCheckedChange={(checked) => onEditRequiredChange(Boolean(checked))}
                  />
                  <Label htmlFor="edit-field-required" className="text-xs font-semibold cursor-pointer">
                    {t('fields.edit_card.required')}
                  </Label>
                </div>

                <div className="flex items-start space-x-2 rounded-xl border border-border/70 bg-muted/20 p-2.5 sm:p-3">
                  <Checkbox
                    id="edit-field-identity"
                    checked={editIdentity}
                    onCheckedChange={(checked) => {
                      const enabled = Boolean(checked)
                      onEditIdentityChange(enabled)
                      if (enabled) {
                        onEditTypeChange('text')
                        onEditRequiredChange(true)
                      }
                    }}
                  />
                  <div className="space-y-0.5 sm:space-y-1">
                    <Label htmlFor="edit-field-identity" className="text-xs font-semibold cursor-pointer">
                      {t('fields.edit_card.primary_identity')}
                    </Label>
                    <p className="text-xs text-muted-foreground">
                      {t('fields.edit_card.primary_identity_desc')}
                    </p>
                  </div>
                </div>
              </>} />
              {usage}
              {error && <p id="edit-field-error" role="alert" className="text-xs text-destructive">{error}</p>}
            </div>

            <div className="shrink-0 flex flex-wrap gap-2 items-center justify-between pt-3 sm:pt-4 mt-auto border-t border-border/50">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                disabled={isDeleting || editIdentity || selectedField.identity_role === 'primary'}
                onClick={onDelete}
                className="h-8 sm:h-9 px-3 sm:px-4 text-xs sm:text-sm font-semibold rounded-xl"
              >
                {isDeleting ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <>
                    <Trash2 className="size-3.5 sm:size-4 mr-1" />
                    {t('fields.edit_card.delete_btn')}
                  </>
                )}
              </Button>

              <Button
                type="submit"
                size="sm"
                disabled={isUpdating || !isDirty}
                className="h-8 sm:h-9 px-3 sm:px-4 font-semibold text-xs sm:text-sm rounded-xl shadow-xs"
              >
                {isUpdating ? (
                  <LoaderCircle className="size-4 animate-spin mr-1" />
                ) : (
                  <>
                    <Check className="size-3.5 sm:size-4 mr-1" />
                    {t('setup.save_field')}
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
