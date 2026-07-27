import { useEffect, useState } from 'react'
import {
  ArrowUpDown,
  BookOpen,
  Check,
  FileUp,
  LoaderCircle,
  Plus,
  Search,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type BrowseCardRow = {
  card_id: string
  note_id: string
  deck_id: number | null
  deck_name: string
  word: string
  reading: string
  meaning: string
  tags: string[]
  status: string
  due_label: string
}

type BrowseCardsResponse = {
  items: BrowseCardRow[]
  page: number
  total: number
  pages: number
  has_next: boolean
}

type BrowseDeck = {
  id: number
  name: string
}

type CardDetailField = {
  name: string
  position: number
  required?: boolean
}

type CardDetailResponse = {
  card: BrowseCardRow
  note: {
    id: string
    deck_id: number
    deck_name: string
    field_values: Record<string, string>
    tags: string[]
  }
  fields: CardDetailField[]
  decks?: Array<{ id: number; name: string }>
}

function statusLabel(status: string) {
  if (status === 'new') return 'Mới'
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'Đang học'
  }
  if (status === 'due' || status === 'review') return 'Đến hạn'
  return status || 'Khác'
}

function statusVariant(status: string) {
  if (status === 'due' || status === 'review') return 'destructive' as const
  if (status === 'learn' || status === 'learning' || status === 'relearning') {
    return 'outline' as const
  }
  return 'secondary' as const
}

export function BrowsePage() {
  const queryClient = useQueryClient()
  const [queryText, setQueryText] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [deckId, setDeckId] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sortBy, setSortBy] = useState('due')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(1)
  const [selectedCards, setSelectedCards] = useState<string[]>([])

  // Active card for editor sheet
  const [activeCardId, setActiveCardId] = useState<string | null>(null)
  const [editFieldValues, setEditFieldValues] = useState<Record<string, string>>({})
  const [editDeckId, setEditDeckId] = useState<number | null>(null)
  const [editTags, setEditTags] = useState<string[]>([])
  const [newTagInput, setNewTagInput] = useState('')

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(queryText.trim())
      setPage(1)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [queryText])

  const decksQuery = useQuery({
    queryKey: ['browse', 'decks'],
    queryFn: () => appApi.get<{ decks: BrowseDeck[] }>('/vocabulary/api/browse/decks'),
  })

  const cardsQuery = useQuery({
    queryKey: ['browse', 'cards', debouncedQuery, deckId, statusFilter, sortBy, sortDir, page],
    queryFn: () =>
      appApi.get<BrowseCardsResponse>('/vocabulary/api/browse/cards', {
        q: debouncedQuery,
        deck_id: deckId,
        status: statusFilter,
        sort_by: sortBy,
        sort_dir: sortDir,
        page,
        per_page: 50,
      }),
  })

  // Card detail query when editor sheet is opened
  const cardDetailQuery = useQuery({
    queryKey: ['browse', 'card-detail', activeCardId],
    queryFn: () => appApi.get<CardDetailResponse>(`/vocabulary/api/browse/cards/${activeCardId}`),
    enabled: Boolean(activeCardId),
  })

  // Update initial form state when detail query loads
  useEffect(() => {
    if (cardDetailQuery.data) {
      setEditFieldValues(cardDetailQuery.data.note.field_values || {})
      setEditDeckId(cardDetailQuery.data.note.deck_id || null)
      setEditTags(cardDetailQuery.data.note.tags || [])
    }
  }, [cardDetailQuery.data])

  // Update mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { field_values: Record<string, string>; deck_id?: number; tags?: string[] }) =>
      appApi.mutate(`/vocabulary/api/browse/cards/${activeCardId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success('Đã cập nhật thông tin thẻ.')
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
      void queryClient.invalidateQueries({ queryKey: ['browse', 'card-detail', activeCardId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể cập nhật thẻ', { description: error.message })
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (cardId: string) => appApi.mutate(`/vocabulary/api/browse/cards/${cardId}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa thẻ.')
      setActiveCardId(null)
      void queryClient.invalidateQueries({ queryKey: ['browse', 'cards'] })
    },
    onError: (error: Error) => {
      toast.error('Không thể xóa thẻ', { description: error.message })
    },
  })

  const cards = cardsQuery.data?.items || []
  const allSelected =
    cards.length > 0 && cards.every((card) => selectedCards.includes(card.card_id))

  const handleAddTag = () => {
    const tag = newTagInput.trim()
    if (tag && !editTags.includes(tag)) {
      setEditTags([...editTags, tag])
      setNewTagInput('')
    }
  }

  const handleRemoveTag = (tagToRemove: string) => {
    setEditTags(editTags.filter((t) => t !== tagToRemove))
  }

  return (
    <Page className="space-y-6">
      <PageHeader
        title="Duyệt thẻ & Quản lý Collection"
        description="Tìm kiếm, sắp xếp và chỉnh sửa toàn bộ thẻ trong kho học liệu của bạn."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild className="rounded-full">
              <a href="/flashcards/import">
                <FileUp className="size-4 mr-1.5" />
                Nhập CSV
              </a>
            </Button>
            <Button size="sm" asChild className="rounded-full bg-gradient-to-r from-primary to-orange-500 text-primary-foreground font-bold shadow-sm">
              <a href="/flashcards/notes/new">
                <Plus className="size-4 mr-1.5" />
                Tạo ghi chú
              </a>
            </Button>
          </div>
        }
      />

      {/* Filter & Toolbar Card */}
      <Card className="border-border/80 shadow-md rounded-2xl overflow-hidden">
        <CardContent className="p-4 space-y-4">
          <div className="grid gap-4 md:grid-cols-12 md:items-end">
            {/* Search Input */}
            <div className="space-y-1.5 md:col-span-4">
              <Label htmlFor="browse-search" className="text-xs font-semibold">
                Tìm kiếm
              </Label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="browse-search"
                  className="pl-9 pr-8"
                  placeholder="Từ, cách đọc, nghĩa hoặc tag…"
                  value={queryText}
                  onChange={(event) => setQueryText(event.currentTarget.value)}
                />
                {queryText ? (
                  <button
                    type="button"
                    onClick={() => setQueryText('')}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    <X className="size-4" />
                  </button>
                ) : null}
              </div>
            </div>

            {/* Deck Select */}
            <div className="space-y-1.5 md:col-span-3">
              <Label htmlFor="browse-deck" className="text-xs font-semibold">
                Bộ thẻ (Deck)
              </Label>
              <NativeSelect
                id="browse-deck"
                className="w-full"
                value={deckId}
                disabled={decksQuery.isPending}
                onChange={(event) => {
                  setDeckId(event.currentTarget.value)
                  setPage(1)
                  setSelectedCards([])
                }}
              >
                <NativeSelectOption value="">Tất cả deck</NativeSelectOption>
                {(decksQuery.data?.decks || []).map((item) => (
                  <NativeSelectOption key={item.id} value={String(item.id)}>
                    {item.name}
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>

            {/* Status Filter */}
            <div className="space-y-1.5 md:col-span-3">
              <Label htmlFor="browse-status" className="text-xs font-semibold">
                Trạng thái
              </Label>
              <NativeSelect
                id="browse-status"
                className="w-full"
                value={statusFilter}
                onChange={(event) => {
                  setStatusFilter(event.currentTarget.value)
                  setPage(1)
                }}
              >
                <NativeSelectOption value="all">Tất cả trạng thái</NativeSelectOption>
                <NativeSelectOption value="new">Mới (New)</NativeSelectOption>
                <NativeSelectOption value="learn">Đang học (Learn)</NativeSelectOption>
                <NativeSelectOption value="due">Đến hạn (Due)</NativeSelectOption>
              </NativeSelect>
            </div>

            {/* Sort Controls */}
            <div className="space-y-1.5 md:col-span-2 flex items-end gap-2">
              <div className="flex-1 space-y-1.5">
                <Label htmlFor="browse-sort" className="text-xs font-semibold">
                  Sắp xếp
                </Label>
                <NativeSelect
                  id="browse-sort"
                  className="w-full text-xs"
                  value={sortBy}
                  onChange={(event) => setSortBy(event.currentTarget.value)}
                >
                  <NativeSelectOption value="due">Đến hạn</NativeSelectOption>
                  <NativeSelectOption value="deck">Deck</NativeSelectOption>
                  <NativeSelectOption value="word">Từ vựng</NativeSelectOption>
                </NativeSelect>
              </div>

              <Button
                type="button"
                variant="outline"
                size="icon"
                className="shrink-0"
                title={sortDir === 'asc' ? 'Tăng dần' : 'Giảm dần'}
                onClick={() => setSortDir(sortDir === 'asc' ? 'desc' : 'asc')}
              >
                <ArrowUpDown className="size-4" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Table View */}
      {cardsQuery.isPending ? <PageLoading label="Đang tải danh sách thẻ…" /> : null}
      {cardsQuery.error ? <PageError error={cardsQuery.error} /> : null}

      {cardsQuery.data ? (
        <Card className="overflow-hidden border-border/80 shadow-lg rounded-2xl">
          <div className="overflow-x-auto">
            <Table className="min-w-[640px]">
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="w-12">
                    <Checkbox
                      checked={allSelected ? true : selectedCards.length > 0 ? 'indeterminate' : false}
                      onCheckedChange={(checked) =>
                        setSelectedCards(checked ? cards.map((card) => card.card_id) : [])
                      }
                      aria-label="Chọn tất cả thẻ"
                    />
                  </TableHead>
                  <TableHead className="font-bold">Từ vựng</TableHead>
                  <TableHead className="font-bold">Cách đọc</TableHead>
                  <TableHead className="font-bold">Nghĩa</TableHead>
                  <TableHead className="font-bold">Deck</TableHead>
                  <TableHead className="font-bold">Trạng thái</TableHead>
                  <TableHead className="text-right font-bold">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cards.map((card) => (
                  <TableRow key={card.card_id} className="hover:bg-muted/40 transition-colors">
                    <TableCell>
                      <Checkbox
                        checked={selectedCards.includes(card.card_id)}
                        onCheckedChange={(checked) =>
                          setSelectedCards((current) =>
                            checked
                              ? Array.from(new Set([...current, card.card_id]))
                              : current.filter((id) => id !== card.card_id),
                          )
                        }
                        aria-label={`Chọn ${card.word}`}
                      />
                    </TableCell>
                    <TableCell>
                      <button
                        type="button"
                        className="font-bold text-primary hover:underline text-left"
                        onClick={() => setActiveCardId(card.card_id)}
                      >
                        {card.word || '(trống)'}
                      </button>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{card.reading || '—'}</TableCell>
                    <TableCell className="max-w-xs truncate">{card.meaning || '—'}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal text-xs">
                        <BookOpen className="size-3 mr-1 text-primary" />
                        {card.deck_name}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(card.status)} className="font-semibold text-xs">
                        {statusLabel(card.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 text-xs font-semibold"
                        onClick={() => setActiveCardId(card.card_id)}
                      >
                        Sửa
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {!cards.length ? (
                  <TableRow>
                    <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                      Không tìm thấy thẻ nào phù hợp với bộ lọc.
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </div>

          {/* Footer Metrics & Pagination */}
          <div className="flex flex-col items-center justify-between gap-3 border-t p-4 sm:flex-row bg-muted/20">
            <p className="text-xs text-muted-foreground">
              Hiển thị <span className="font-bold text-foreground">{cards.length}</span> / Tổng số{' '}
              <span className="font-bold text-foreground">{cardsQuery.data.total}</span> thẻ
            </p>
            {cardsQuery.data.pages > 1 ? (
              <Pagination className="mx-0 w-auto">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      aria-disabled={page <= 1}
                      onClick={(event) => {
                        event.preventDefault()
                        if (page > 1) setPage((value) => value - 1)
                      }}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationLink href="#" isActive onClick={(event) => event.preventDefault()}>
                      Trang {page} / {cardsQuery.data.pages}
                    </PaginationLink>
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      aria-disabled={!cardsQuery.data.has_next}
                      onClick={(event) => {
                        event.preventDefault()
                        if (cardsQuery.data.has_next) setPage((value) => value + 1)
                      }}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            ) : null}
          </div>
        </Card>
      ) : null}

      {/* Card Details & Editor Sheet */}
      <Sheet open={Boolean(activeCardId)} onOpenChange={(open) => !open && setActiveCardId(null)}>
        <SheetContent className="overflow-y-auto sm:max-w-xl space-y-6">
          <SheetHeader>
            <SheetTitle className="text-xl">Chỉnh sửa chi tiết thẻ</SheetTitle>
            <SheetDescription>
              Thay đổi trường dữ liệu, di chuyển Deck hoặc thêm bớt Tags.
            </SheetDescription>
          </SheetHeader>

          {cardDetailQuery.isPending ? (
            <div className="flex h-48 items-center justify-center">
              <LoaderCircle className="size-6 animate-spin text-primary" />
            </div>
          ) : cardDetailQuery.data ? (
            <div className="space-y-6 px-1">
              {/* Deck Selector */}
              <div className="space-y-2">
                <Label htmlFor="edit-deck">Bộ thẻ (Deck)</Label>
                <NativeSelect
                  id="edit-deck"
                  value={editDeckId || ''}
                  onChange={(e) => setEditDeckId(Number(e.target.value))}
                >
                  {(cardDetailQuery.data.decks || []).map((d) => (
                    <NativeSelectOption key={d.id} value={d.id}>
                      {d.name}
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>

              {/* Dynamic Note Fields */}
              <div className="space-y-4 rounded-2xl border p-4 bg-muted/20">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Trường thông tin (Note Fields)
                </h3>
                {cardDetailQuery.data.fields.map((field) => (
                  <div key={field.name} className="space-y-1.5">
                    <Label htmlFor={`field-${field.name}`} className="text-xs font-semibold">
                      {field.name} {field.required ? <span className="text-destructive">*</span> : null}
                    </Label>
                    <Input
                      id={`field-${field.name}`}
                      value={editFieldValues[field.name] || ''}
                      onChange={(e) =>
                        setEditFieldValues({
                          ...editFieldValues,
                          [field.name]: e.target.value,
                        })
                      }
                    />
                  </div>
                ))}
              </div>

              {/* Tags Section */}
              <div className="space-y-2">
                <Label>Thẻ phân loại (Tags)</Label>
                <div className="flex flex-wrap gap-1.5 mb-2">
                  {editTags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="gap-1 rounded-full px-2.5 py-1">
                      <Tag className="size-3 text-primary" />
                      <span>{tag}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="ml-1 text-muted-foreground hover:text-foreground"
                      >
                        <X className="size-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Input
                    placeholder="Thêm tag mới…"
                    value={newTagInput}
                    onChange={(e) => setNewTagInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        handleAddTag()
                      }
                    }}
                  />
                  <Button type="button" variant="outline" onClick={handleAddTag}>
                    Thêm
                  </Button>
                </div>
              </div>

              {/* Action Sheet Footer */}
              <SheetFooter className="flex-col sm:flex-row gap-2 pt-4 border-t">
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (window.confirm('Bạn có chắc chắn muốn xóa thẻ này?')) {
                      deleteMutation.mutate(activeCardId!)
                    }
                  }}
                >

                  {deleteMutation.isPending ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4 mr-1.5" />}
                  Xóa thẻ
                </Button>

                <Button
                  type="button"
                  size="sm"
                  className="bg-gradient-to-r from-primary to-orange-500 text-primary-foreground font-bold shadow-sm"
                  disabled={updateMutation.isPending}
                  onClick={() =>
                    updateMutation.mutate({
                      field_values: editFieldValues,
                      deck_id: editDeckId || undefined,
                      tags: editTags,
                    })
                  }
                >
                  {updateMutation.isPending ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <>
                      <Check className="size-4 mr-1.5" />
                      Lưu thay đổi
                    </>
                  )}
                </Button>
              </SheetFooter>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </Page>
  )
}
