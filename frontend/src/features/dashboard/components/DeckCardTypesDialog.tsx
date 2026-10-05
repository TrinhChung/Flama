import { AlertCircle, Layers, LoaderCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
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
  cardTemplateQueryKeys,
  fetchDeckCardTypes,
  type CardTypeContextKind,
  type DeckCardType,
} from '@/entities/card-template'

export type DeckCardTypesDialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId: number
  deckName: string
}

function contextLabel(kind?: CardTypeContextKind): string {
  if (kind === 'installed_source') return 'Thẻ gốc từ bộ đã cài'
  if (kind === 'installed_local') return 'Thẻ riêng trong bộ đã cài'
  return 'Thẻ trong bộ của bạn'
}

function editAction(item: DeckCardType) {
  if (item.context_kind === 'installed_source') {
    return (
      <Button
        size="sm"
        variant="outline"
        className="h-7 px-2.5 text-xs rounded-lg"
        disabled
        title="Sắp có: tạo bản riêng cho thẻ gốc của bộ đã cài."
      >
        Sửa giao diện
      </Button>
    )
  }

  return (
    <Button asChild size="sm" variant="outline" className="h-7 px-2.5 text-xs rounded-lg">
      <Link to={`/note-types/${encodeURIComponent(item.note_type_id)}`}>Sửa giao diện</Link>
    </Button>
  )
}

export function DeckCardTypesDialog({
  open,
  onOpenChange,
  deckId,
  deckName,
}: DeckCardTypesDialogProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: cardTemplateQueryKeys.deckCardTypes(deckId),
    queryFn: ({ signal }) => fetchDeckCardTypes(deckId, signal),
    enabled: open,
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{`Kiểu thẻ của “${deckName}”`}</DialogTitle>
          <DialogDescription>
            Mỗi kiểu thẻ là một template hiển thị cùng dữ liệu note. Khi học, bạn chọn một kiểu cho cả phiên.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
            Đang tải kiểu thẻ…
          </div>
        ) : error ? (
          <Alert variant="destructive">
            <AlertCircle aria-hidden="true" />
            <AlertDescription>
              {error.message || 'Có lỗi xảy ra khi tải kiểu thẻ.'}
            </AlertDescription>
          </Alert>
        ) : data && (data.compositions?.length ?? 0) === 0 ? (
          <p className="py-6 text-sm text-muted-foreground">Deck này chưa có thẻ để học.</p>
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
                  {(group.compositions ?? []).map((item) => (
                    <li
                      key={item.composition_id}
                      className="flex flex-wrap items-center gap-2 rounded-xl border border-border/80 bg-background px-3 py-2.5"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">{item.template_name}</p>
                        <p className="text-xs text-muted-foreground">{contextLabel(item.context_kind)}</p>
                      </div>
                      {item.is_default ? <Badge variant="secondary">Mặc định</Badge> : null}
                      <Badge variant="outline">{`${data.note_counts?.[item.composition_id] ?? 0} note`}</Badge>
                      {editAction(item)}
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Đóng
          </Button>
          {(data?.compositions?.length ?? 0) > 0 ? (
            <Button asChild>
              <Link to={`/study?deck_id=${deckId}`}>Học deck này</Link>
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
