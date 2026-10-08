import { useTranslation } from 'react-i18next'
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus } from '@fortawesome/free-solid-svg-icons'
import { LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface CreateNoteTypeBarProps {
  name: string
  onNameChange: (value: string) => void
  onSubmit: (e: React.FormEvent) => void
  isPending: boolean
}

export function CreateNoteTypeBar({
  name,
  onNameChange,
  onSubmit,
  isPending,
}: CreateNoteTypeBarProps) {
  const { t } = useTranslation('note_types')

  return (
    <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between p-3.5 sm:p-4 rounded-2xl border border-border/80 bg-card shadow-2xs">
      <div className="space-y-0.5 sm:max-w-xs shrink-0">
        <h2 className="text-xs sm:text-sm font-bold text-foreground">{t('manager.create.title')}</h2>
        <p className="text-[11px] text-muted-foreground">{t('manager.create.description')}</p>
      </div>
      <form onSubmit={onSubmit} className="flex-1 flex gap-2 items-center">
        <div className="flex-1">
          <Label htmlFor="note-type-name" className="sr-only">
            {t('manager.create.title')}
          </Label>
          <Input
            id="note-type-name"
            data-tour="create-input"
            placeholder={t('manager.create.placeholder')}
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl bg-background"
          />
        </div>
        <Button
          type="submit"
          data-tour="create-button"
          disabled={isPending}
          className="h-9 sm:h-10 px-4 font-bold text-xs sm:text-sm shadow-xs shrink-0 rounded-xl gap-1.5"
        >
          {isPending ? (
            <LoaderCircle className="animate-spin size-4" />
          ) : (
            <FontAwesomeIcon icon={faPlus} className="text-xs" />
          )}
          {t('manager.create.submit_btn')}
        </Button>
      </form>
    </div>
  )
}
