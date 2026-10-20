import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, LoaderCircle } from 'lucide-react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { LazyDeckWorksheetModal } from '@/features/worksheets'
import { DeckCardTypesDialog } from './DeckCardTypesDialog'
import { dashboardQueryKey } from '../api'
import {
  getCreateDeckSchema,
  getRenameDeckSchema,
  moveDeckSchema,
  type CreateDeckForm,
  type MoveDeckForm,
  type RenameDeckForm,
} from '../schemas'
import type { DashboardPayload, DeckNode, SelectedDeckAction } from '../types'
import { suggestNextDeckPath } from '../utils/deckNaming'

type DeckOption = { value: string; label: string }

function flattenDecks(nodes: DeckNode[], prefix = ''): DeckOption[] {
  return nodes.flatMap((node) => [
    { value: String(node.id), label: `${prefix}${node.name}` },
    ...flattenDecks(node.children, `${prefix}— `),
  ])
}

function MutationError({ error }: { error: Error | null }) {
  if (!error) return null
  return (
    <Alert variant="destructive">
      <AlertCircle />
      <AlertDescription>{error.message}</AlertDescription>
    </Alert>
  )
}

function Field({
  id,
  label,
  description,
  error,
  ...props
}: React.ComponentProps<typeof Input> & {
  id: string
  label: string
  description?: string
  error?: string
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={Boolean(error)} {...props} />
      {description ? <p className="text-xs text-muted-foreground">{description}</p> : null}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  )
}

function SubmitButton({ pending, children, variant }: {
  pending: boolean
  children: React.ReactNode
  variant?: React.ComponentProps<typeof Button>['variant']
}) {
  return (
    <Button type="submit" disabled={pending} variant={variant}>
      {pending ? <LoaderCircle className="animate-spin" /> : null}
      {children}
    </Button>
  )
}

export function CreateDeckModal({
  opened,
  onClose,
  dashboard,
  selectedDeck = null,
}: {
  opened: boolean
  onClose: () => void
  dashboard: DashboardPayload
  selectedDeck?: DeckNode | null
}) {
  const { t } = useTranslation('dashboard')
  const queryClient = useQueryClient()
  const createSchema = useMemo(() => getCreateDeckSchema((k: any) => t(k)), [t])
  const form = useForm<CreateDeckForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { name: '', deck_path: '', parent_id: '', note_type_id: '' },
  })

  const noteTypesQuery = useQuery({
    queryKey: ['note-types'],
    queryFn: () =>
      appApi.get<{ items: Array<{ id: string; name: string; title?: string }> }>(
        '/note-types',
      ),
    enabled: opened,
  })

  const noteTypesData = noteTypesQuery.data?.items
  const noteTypes = noteTypesData || []

  useEffect(() => {
    if (!opened) return

    const items = noteTypesData || []
    const suggestedPath = suggestNextDeckPath(selectedDeck, dashboard.decks)
    const inheritedNoteTypeId = selectedDeck?.note_type_id || ''
    const defaultFallbackNoteTypeId =
      items.find(
        (nt) =>
          nt.name?.toLowerCase().includes('từ vựng') ||
          nt.name?.toLowerCase().includes('vocab') ||
          nt.name?.toLowerCase().includes('word'),
      )?.id ||
      items[0]?.id ||
      ''

    form.reset({
      name: suggestedPath,
      deck_path: suggestedPath,
      parent_id: '',
      note_type_id: inheritedNoteTypeId || defaultFallbackNoteTypeId,
    })
  }, [opened, selectedDeck, dashboard.decks, form, noteTypesData])

  const mutation = useMutation<unknown, Error, CreateDeckForm>({
    mutationFn: (values) =>
      appApi.createDeck({
        ...values,
        deck_path: values.name,
        parent_id: values.parent_id || '',
        note_type_id: values.note_type_id || undefined,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
      toast.success(t('modals.create_deck.toast_success'))
      form.reset()
      onClose()
    },
  })

  const descriptionText = selectedDeck
    ? t('modals.create_deck.desc_nested')
    : t('modals.create_deck.desc_root')

  return (
    <Dialog open={opened} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('modals.create_deck.title')}</DialogTitle>
          <DialogDescription>{descriptionText}</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <MutationError error={mutation.error} />
          <Field
            id="create-deck-name"
            label={t('modals.create_deck.name_label')}
            placeholder={t('modals.create_deck.name_placeholder')}
            description={t('modals.create_deck.name_description')}
            autoFocus
            onFocus={(e) => e.target.select()}
            error={form.formState.errors.name?.message}
            {...form.register('name')}
          />
          <div className="space-y-2">
            <Label htmlFor="create-deck-notetype">{t('modals.create_deck.notetype_label')}</Label>
            <NativeSelect
              id="create-deck-notetype"
              className="w-full"
              disabled={noteTypesQuery.isPending}
              {...form.register('note_type_id')}
            >
              {noteTypes.length === 0 ? (
                <NativeSelectOption value="">
                  {noteTypesQuery.isPending ? t('modals.create_deck.notetype_loading') : t('modals.create_deck.notetype_default')}
                </NativeSelectOption>
              ) : (
                noteTypes.map((nt) => (
                  <NativeSelectOption key={nt.id} value={nt.id}>
                    {nt.name || nt.title || nt.id}
                  </NativeSelectOption>
                ))
              )}
            </NativeSelect>
            <p className="text-xs text-muted-foreground">
              {selectedDeck?.note_type_id
                ? t('modals.create_deck.notetype_help_inherited')
                : t('modals.create_deck.notetype_help_default')}
            </p>
          </div>
          <input type="hidden" {...form.register('parent_id')} />
          <input type="hidden" {...form.register('deck_path')} />
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>{t('modals.create_deck.btn_cancel')}</Button>
            <SubmitButton pending={mutation.isPending}>{t('modals.create_deck.btn_submit')}</SubmitButton>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

export function DeckActionModal({ selection, onClose, dashboard }: {
  selection: SelectedDeckAction | null
  onClose: () => void
  dashboard: DashboardPayload
}) {
  const { t } = useTranslation('dashboard')
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)
  const [purge, setPurge] = useState(false)

  const renameSchema = useMemo(() => getRenameDeckSchema((k: any) => t(k)), [t])
  const renameForm = useForm<RenameDeckForm>({
    resolver: zodResolver(renameSchema),
    defaultValues: { name: '' },
  })
  const moveForm = useForm<MoveDeckForm>({
    resolver: zodResolver(moveDeckSchema),
    defaultValues: { parent_id: '' },
  })
  const mutation = useMutation<unknown, Error, {
    type: SelectedDeckAction['type']
    deckId: number
    values: Record<string, string>
    purge?: boolean
  }>({
    mutationFn: ({ type, deckId, values, purge }) => {
      if (type === 'rename') return appApi.renameDeck(deckId, { name: values.name || '' })
      if (type === 'move') return appApi.moveDeck(deckId, { parent_id: values.parent_id || '' })
      if (type === 'delete') return appApi.deleteDeck(deckId, { purge })
      return appApi.resetDeck(deckId)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
      toast.success(t('modals.actions.toast_success'))
      onClose()
    },
  })

  useEffect(() => {
    renameForm.reset({ name: selection?.deck.name || '' })
    moveForm.reset({
      parent_id: selection?.deck.parent_id === null ? '' : String(selection?.deck.parent_id || ''),
    })
    setPurge(false)
  }, [selection, renameForm, moveForm])

  if (!selection) return null
  const { type, deck } = selection

  if (type === 'worksheet') {
    return (
      <LazyDeckWorksheetModal
        open
        onOpenChange={(open) => !open && onClose()}
        deckId={deck.id}
        deckName={deck.name}
      />
    )
  }

  if (type === 'card-types') {
    return (
      <DeckCardTypesDialog
        open
        onOpenChange={(open) => !open && onClose()}
        deckId={deck.id}
        deckName={deck.name}
      />
    )
  }

  const options = flattenDecks(dashboard.decks).filter((option) => option.value !== String(deck.id))
  const destructive = type === 'delete'
  const title =
    type === 'rename' ? t('modals.actions.titles.rename', { name: deck.name })
      : type === 'move' ? t('modals.actions.titles.move', { name: deck.name })
        : destructive ? t('modals.actions.titles.delete') : t('modals.actions.titles.reset')

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {type === 'delete' || type === 'reset' ? (
            <DialogDescription>
              {destructive
                ? t('modals.actions.descriptions.delete', { name: deck.name })
                : t('modals.actions.descriptions.reset', { name: deck.name })}
            </DialogDescription>
          ) : null}
        </DialogHeader>

        {type === 'rename' ? (
          <form className="space-y-4" onSubmit={renameForm.handleSubmit((values) => mutation.mutate({ type, deckId: deck.id, values }))}>
            <MutationError error={mutation.error} />
            <Field id="rename-deck-name" label={t('modals.actions.rename_form.name_label')} error={renameForm.formState.errors.name?.message} {...renameForm.register('name')} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>{t('modals.actions.buttons.cancel')}</Button>
              <SubmitButton pending={mutation.isPending}>{t('modals.actions.rename_form.btn_save')}</SubmitButton>
            </DialogFooter>
          </form>
        ) : type === 'move' ? (
          <form className="space-y-4" onSubmit={moveForm.handleSubmit((values) => mutation.mutate({ type, deckId: deck.id, values }))}>
            <MutationError error={mutation.error} />
            <div className="space-y-2">
              <Label htmlFor="move-deck-parent">{t('modals.actions.move_form.parent_label')}</Label>
              <NativeSelect id="move-deck-parent" className="w-full" {...moveForm.register('parent_id')}>
                <NativeSelectOption value="">{t('modals.actions.move_form.root_option')}</NativeSelectOption>
                {options.map((option) => (
                  <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>{t('modals.actions.buttons.cancel')}</Button>
              <SubmitButton pending={mutation.isPending}>{t('modals.actions.move_form.btn_move')}</SubmitButton>
            </DialogFooter>
          </form>
        ) : (
          <div className="space-y-4">
            <MutationError error={mutation.error} />
            {destructive && isAdmin && (
              <div className="space-y-3 p-3 rounded-lg border border-destructive/20 bg-destructive/5 dark:bg-destructive/10">
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="purge-deck-checkbox"
                    checked={purge}
                    onCheckedChange={(checked) => setPurge(Boolean(checked))}
                    className="border-destructive/60 data-checked:bg-destructive data-checked:border-destructive data-checked:text-destructive-foreground cursor-pointer"
                  />
                  <Label htmlFor="purge-deck-checkbox" className="font-bold text-destructive cursor-pointer select-none">
                    {t('modals.actions.purge.checkbox_label')}
                  </Label>
                </div>
                {purge && (
                  <Alert variant="destructive" className="border-none bg-transparent p-0 flex items-start">
                    <AlertCircle className="size-4 mt-0.5 text-destructive shrink-0" />
                    <AlertDescription className="text-xs text-destructive/90 font-medium ml-2 leading-relaxed">
                      {t('modals.actions.purge.alert_warning')}
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>{t('modals.actions.buttons.cancel')}</Button>
              <Button
                variant={destructive ? 'destructive' : 'default'}
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ type, deckId: deck.id, values: {}, purge })}
              >
                {mutation.isPending ? <LoaderCircle className="animate-spin" /> : null}
                {destructive ? (purge ? t('modals.actions.buttons.delete_purge') : t('modals.actions.buttons.delete_deck')) : t('modals.actions.buttons.reset')}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
