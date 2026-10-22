import { AlertCircle, Layers, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  type CardTypeContextKind,
  type DeckCardType,
} from '@/entities/card-template'
import { useDeckCardTypes } from '../hooks/useDeckCardTypes'

export type DeckCardTypesDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId: number
  deckName: string
}

function getContextLabel(kind: CardTypeContextKind | undefined, t: (key: any) => string): string {
  if (kind === 'installed_source') return t('modals.card_types.context.installed_source')
  if (kind === 'installed_local') return t('modals.card_types.context.installed_local')
  return t('modals.card_types.context.user_deck')
}

function renderEditAction(item: DeckCardType, t: (key: any) => string) {
  if (item.context_kind === 'installed_source') {
    if (item.install_id) {
      return (
        <Button asChild size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg">
          <Link to={`/installed-decks/${encodeURIComponent(item.install_id)}/templates?template=${encodeURIComponent(item.template_id)}`}>
            {t('modals.card_types.btn_edit')}
          </Link>
        </Button>
      )
    }
    return (
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2.5 text-xs rounded-lg"
        disabled
        title={t('modals.card_types.btn_edit_disabled_title')}
      >
        {t('modals.card_types.btn_edit')}
      </Button>
    )
  }

  const applicationId = item.application_id || item.study_application_id
  const templatesPath = `/flashcards/note-types/${encodeURIComponent(item.note_type_id)}/templates`
  return (
    <Button asChild size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg">
      <Link to={applicationId ? `${templatesPath}/${encodeURIComponent(applicationId)}` : templatesPath}>
        {t('modals.card_types.btn_edit')}
      </Link>
    </Button>
  )
}

export function DeckCardTypesDialog({
  open,
  onOpenChange,
  deckId,
  deckName,
}: DeckCardTypesDialogProps) {
  const { t, i18n } = useTranslation('dashboard')
  const numberLocale = i18n.language === 'en' ? 'en-US' : 'vi-VN'
  const { data, isLoading, error } = useDeckCardTypes(deckId, open)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('modals.card_types.title', { name: deckName })}</DialogTitle>
          <DialogDescription>
            {t('modals.card_types.description')}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
            {t('modals.card_types.loading')}
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <AlertCircle aria-hidden="true" />
            <AlertDescription>
              {error.message || t('modals.card_types.error_fallback')}
            </AlertDescription>
          </Alert>
        ) : data && (data.compositions?.length ?? 0) === 0 ? (
          <p className="py-6 text-sm text-muted-foreground">{t('modals.card_types.empty')}</p>
        ) : data ? (
          <div className="space-y-5">
            {(data.groups ?? []).map((group) => (
              <section key={group.note_type_id} className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <span className="flex size-7 items-center justify-center rounded-lg bg-orange-500/10 text-orange-600 dark:text-orange-400">
                    <Layers className="size-4" aria-hidden="true" />
                  </span>
                  <span>{group.note_type_name}</span>
                </div>
                <ul className="space-y-2">
                  {(group.compositions ?? []).map((item) => {
                    const count = data.note_counts?.[item.composition_id] ?? 0
                    return (
                      <li
                        key={item.composition_id}
                        className="flex flex-wrap items-center gap-2 rounded-xl border border-border/80 bg-background px-3 py-2.5"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-semibold">{item.template_name}</p>
                          <p className="text-xs text-muted-foreground">{getContextLabel(item.context_kind, t)}</p>
                        </div>
                        {item.is_default ? <Badge variant="secondary">{t('modals.card_types.badge_default')}</Badge> : null}
                        <Badge variant="outline">
                          {t('modals.card_types.badge_note_count', {
                            count,
                            formattedCount: count.toLocaleString(numberLocale),
                          })}
                        </Badge>
                        {renderEditAction(item, t)}
                      </li>
                    )
                  })}
                </ul>
              </section>
            ))}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('modals.card_types.btn_close')}
          </Button>
          {(data?.compositions?.length ?? 0) > 0 ? (
            <Button asChild>
              <Link to={`/study?deck_id=${deckId}`}>{t('modals.card_types.btn_study')}</Link>
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
