import { useEffect } from 'react'
import { AlertCircle, LoaderCircle } from 'lucide-react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
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
import { dashboardQueryKey } from '../api'
import {
  createDeckSchema,
  moveDeckSchema,
  renameDeckSchema,
  type CreateDeckForm,
  type MoveDeckForm,
  type RenameDeckForm,
} from '../schemas'
import type { DashboardPayload, DeckNode, SelectedDeckAction } from '../types'

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

export function CreateDeckModal({ opened, onClose, dashboard }: {
  opened: boolean
  onClose: () => void
  dashboard: DashboardPayload
}) {
  const queryClient = useQueryClient()
  const form = useForm<CreateDeckForm>({
    resolver: zodResolver(createDeckSchema),
    defaultValues: { name: '', deck_path: '', parent_id: '' },
  })
  const mutation = useMutation<unknown, Error, CreateDeckForm>({
    mutationFn: (values) => appApi.createDeck(values),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
      toast.success('Deck đã được tạo.')
      form.reset()
      onClose()
    },
  })

  return (
    <Dialog open={opened} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Tạo deck mới</DialogTitle>
          <DialogDescription>Tạo deck ở root hoặc đặt dưới một deck cha hiện có.</DialogDescription>
        </DialogHeader>
        <form className="space-y-4" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <MutationError error={mutation.error} />
          <Field
            id="create-deck-name"
            label="Tên deck"
            placeholder="Ví dụ: N3 Kanji"
            error={form.formState.errors.name?.message}
            {...form.register('name')}
          />
          <Field
            id="create-deck-path"
            label="Đường dẫn nhiều cấp"
            description="Tùy chọn, dùng dấu :: để tạo nhiều cấp."
            placeholder="JLPT::N3::Kanji"
            error={form.formState.errors.deck_path?.message}
            {...form.register('deck_path')}
          />
          <div className="space-y-2">
            <Label htmlFor="create-deck-parent">Deck cha</Label>
            <NativeSelect id="create-deck-parent" className="w-full" {...form.register('parent_id')}>
              <NativeSelectOption value="">Root</NativeSelectOption>
              {flattenDecks(dashboard.decks).map((option) => (
                <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Hủy</Button>
            <SubmitButton pending={mutation.isPending}>Tạo deck</SubmitButton>
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
  const queryClient = useQueryClient()
  const renameForm = useForm<RenameDeckForm>({
    resolver: zodResolver(renameDeckSchema),
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
  }>({
    mutationFn: ({ type, deckId, values }) => {
      if (type === 'rename') return appApi.renameDeck(deckId, { name: values.name || '' })
      if (type === 'move') return appApi.moveDeck(deckId, { parent_id: values.parent_id || '' })
      if (type === 'delete') return appApi.deleteDeck(deckId)
      return appApi.resetDeck(deckId)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
      toast.success('Thao tác deck đã hoàn tất.')
      onClose()
    },
  })

  useEffect(() => {
    renameForm.reset({ name: selection?.deck.name || '' })
    moveForm.reset({
      parent_id: selection?.deck.parent_id === null ? '' : String(selection?.deck.parent_id || ''),
    })
  }, [selection, renameForm, moveForm])

  if (!selection) return null
  const { type, deck } = selection
  const options = flattenDecks(dashboard.decks).filter((option) => option.value !== String(deck.id))
  const destructive = type === 'delete'
  const title =
    type === 'rename' ? `Đổi tên “${deck.name}”`
      : type === 'move' ? `Di chuyển “${deck.name}”`
        : destructive ? 'Xác nhận xóa deck' : 'Đặt lại tiến độ'

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {type === 'delete' || type === 'reset' ? (
            <DialogDescription>
              {destructive
                ? `Xóa “${deck.name}” cùng toàn bộ nội dung thuộc deck? Hành động này có thể không hoàn tác được.`
                : `Đặt lại toàn bộ tiến độ học của tài khoản hiện tại trong “${deck.name}”?`}
            </DialogDescription>
          ) : null}
        </DialogHeader>

        {type === 'rename' ? (
          <form className="space-y-4" onSubmit={renameForm.handleSubmit((values) => mutation.mutate({ type, deckId: deck.id, values }))}>
            <MutationError error={mutation.error} />
            <Field id="rename-deck-name" label="Tên mới" error={renameForm.formState.errors.name?.message} {...renameForm.register('name')} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>Hủy</Button>
              <SubmitButton pending={mutation.isPending}>Lưu</SubmitButton>
            </DialogFooter>
          </form>
        ) : type === 'move' ? (
          <form className="space-y-4" onSubmit={moveForm.handleSubmit((values) => mutation.mutate({ type, deckId: deck.id, values }))}>
            <MutationError error={mutation.error} />
            <div className="space-y-2">
              <Label htmlFor="move-deck-parent">Deck cha mới</Label>
              <NativeSelect id="move-deck-parent" className="w-full" {...moveForm.register('parent_id')}>
                <NativeSelectOption value="">Root</NativeSelectOption>
                {options.map((option) => (
                  <NativeSelectOption key={option.value} value={option.value}>{option.label}</NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>Hủy</Button>
              <SubmitButton pending={mutation.isPending}>Di chuyển</SubmitButton>
            </DialogFooter>
          </form>
        ) : (
          <div className="space-y-4">
            <MutationError error={mutation.error} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={onClose}>Hủy</Button>
              <Button
                variant={destructive ? 'destructive' : 'default'}
                disabled={mutation.isPending}
                onClick={() => mutation.mutate({ type, deckId: deck.id, values: {} })}
              >
                {mutation.isPending ? <LoaderCircle className="animate-spin" /> : null}
                {destructive ? 'Xóa deck' : 'Đặt lại'}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
