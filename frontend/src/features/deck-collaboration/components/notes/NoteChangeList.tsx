import { memo, useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronDown, ChevronRight, Folder, LoaderCircle, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import '@/shared/config/i18n'
import { groupNotesByDeck, type DeckGroup, type GroupedContribution } from '../../model/noteChanges'
import type { NoteSelectionControls } from '../../model/selection'
import type { NoteContext, NoteFieldDef } from '../../types'
import { LazyNoteChangeCard } from './LazyNoteChangeCard'
import { SchemaChangeCard } from './SchemaChangeCard'

// About a screenful; the rest mount as they come near the viewport.
const EAGER_NOTES = 8

/** One colour key for the whole list instead of labels on every field. */
function DiffLegend() {
  const { t } = useTranslation('collaboration')
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground" aria-hidden="true">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-3 rounded-sm border border-red-500/40 bg-red-500/15" />
        {t('notes.column_current', 'Bản hiện tại')}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-3 rounded-sm border border-emerald-500/40 bg-emerald-500/20" />
        {t('notes.column_proposed', 'Bản đề xuất')}
      </span>
    </div>
  )
}

const DeckGroupHeader = memo(function DeckGroupHeader({
  group,
  collapsed,
  onToggle,
}: {
  group: DeckGroup
  collapsed: boolean
  onToggle: (key: string) => void
}) {
  const { t } = useTranslation('collaboration')
  // The shared deck's own name would repeat on every folder, so start below it.
  const label = (group.path.length > 1 ? group.path.slice(1) : group.path).join(' › ')
    || t('notes.deck_unknown', 'Deck khác')
  return (
    <button
      type="button"
      className="flex w-full items-center gap-2 rounded-lg px-1 pt-2 text-left text-sm font-semibold hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-expanded={!collapsed}
      onClick={() => onToggle(group.key)}
    >
      {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
      <Folder className="size-4 text-muted-foreground" />
      <span className="min-w-0 truncate">{label}</span>
      <span className="shrink-0 text-xs font-normal text-muted-foreground">
        {t('notes.deck_note_count', {
          count: group.notes.length,
          defaultValue: `${group.notes.length} note`,
        })}
      </span>
    </button>
  )
})

/** Keeps the draft query local, so typing never re-renders the note list. */
const NoteSearchForm = memo(function NoteSearchForm({
  query,
  onQueryChange,
}: {
  query: string
  onQueryChange: (query: string) => void
}) {
  const { t } = useTranslation('collaboration')
  const [searchDraft, setSearchDraft] = useState(query)

  useEffect(() => {
    setSearchDraft(query)
  }, [query])

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const next = searchDraft.trim()
    if (next !== query) onQueryChange(next)
  }

  return (
    <form onSubmit={submitSearch} className="flex w-full gap-2 sm:max-w-sm">
      <div className="relative min-w-0 flex-1">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchDraft}
          onChange={(event) => setSearchDraft(event.target.value)}
          className="pl-9"
          placeholder={t('notes.search_placeholder', 'Tìm theo note hoặc tên trường…')}
          aria-label={t('notes.search_aria_label', 'Tìm trong các note thay đổi')}
        />
      </div>
      <Button type="submit" variant="outline">
        {t('diff.btn_search', 'Tìm')}
      </Button>
    </form>
  )
})

export type NoteChangeListProps = {
  grouped: GroupedContribution
  fieldDefs: NoteFieldDef[]
  noteContexts: Record<string, NoteContext>
  /** Notes in the whole contribution, including pages not loaded yet. */
  totalNotes: number
  selection?: NoteSelectionControls
  query: string
  onQueryChange: (query: string) => void
  isFetching?: boolean
  isFetchingMore?: boolean
  hasMore?: boolean
  onLoadMore?: () => void
}

export function NoteChangeList({
  grouped,
  fieldDefs,
  noteContexts,
  totalNotes,
  selection,
  query,
  onQueryChange,
  isFetching = false,
  isFetchingMore = false,
  hasMore = false,
  onLoadMore,
}: NoteChangeListProps) {
  const { t, i18n } = useTranslation('collaboration')
  const locale = i18n.language === 'en' ? 'en-US' : 'vi-VN'

  const isEmpty = !grouped.notes.length && !grouped.schema.length
  const deckGroups = useMemo(() => groupNotesByDeck(grouped.notes, noteContexts), [grouped.notes, noteContexts])
  // A deck without sub-decks needs no folder headings.
  const showDecks = deckGroups.length > 1 || (deckGroups[0]?.path.length ?? 0) > 1
  const [collapsedDecks, setCollapsedDecks] = useState<ReadonlySet<string>>(() => new Set())
  const toggleDeck = useCallback((key: string) => {
    setCollapsedDecks((current) => {
      const next = new Set(current)
      if (!next.delete(key)) next.add(key)
      return next
    })
  }, [])
  let renderedNotes = 0

  return (
    <section className="space-y-3" aria-label={t('notes.aria_label', 'Các note thay đổi')}>
      <div className="sticky top-0 z-10 space-y-2 rounded-2xl border bg-background/95 p-3 shadow-sm backdrop-blur">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-medium" role="status" aria-live="polite">
              {selection
                ? selection.unit === 'note'
                  ? t('notes.selected_notes', {
                      selected: selection.selectedCount.toLocaleString(locale),
                      total: selection.totalCount.toLocaleString(locale),
                      defaultValue: `Đã chọn ${selection.selectedCount.toLocaleString(locale)}/${selection.totalCount.toLocaleString(locale)} note`,
                    })
                  : t('notes.selected_changes', {
                      selected: selection.selectedCount.toLocaleString(locale),
                      total: selection.totalCount.toLocaleString(locale),
                      defaultValue: `Đã chọn ${selection.selectedCount.toLocaleString(locale)}/${selection.totalCount.toLocaleString(locale)} thay đổi`,
                    })
                : t('notes.total_notes', {
                    count: totalNotes,
                    formatted: totalNotes.toLocaleString(locale),
                    defaultValue: `${totalNotes.toLocaleString(locale)} note thay đổi`,
                  })}
            </p>
            {selection ? (
              <>
                <Button type="button" variant="outline" size="sm" onClick={selection.selectAll}>
                  {t('notes.btn_select_all', 'Chọn tất cả')}
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={selection.selectNone}>
                  {t('notes.btn_select_none', 'Bỏ chọn tất cả')}
                </Button>
              </>
            ) : null}
            {isFetching && !isFetchingMore ? (
              <LoaderCircle className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
            ) : null}
          </div>
          <NoteSearchForm query={query} onQueryChange={onQueryChange} />
        </div>
        <DiffLegend />
      </div>

      {isEmpty && !isFetching ? (
        <div className="rounded-2xl border border-dashed bg-muted/20 px-6 py-14 text-center">
          <h3 className="font-semibold">{t('diff.empty_filter_title', 'Không có thay đổi khớp bộ lọc')}</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('notes.empty_filter_desc', 'Thử từ khóa khác hoặc xóa ô tìm kiếm.')}
          </p>
        </div>
      ) : null}

      {grouped.schema.length ? <SchemaChangeCard changes={grouped.schema} selection={selection} /> : null}

      {deckGroups.map((group) => {
        const collapsed = showDecks && collapsedDecks.has(group.key)
        return (
          <div key={group.key || 'unknown'} className="space-y-3">
            {showDecks ? <DeckGroupHeader group={group} collapsed={collapsed} onToggle={toggleDeck} /> : null}
            {collapsed ? null : group.notes.map((note) => {
              // Plain values and stable callbacks: a tick re-renders only its own card.
              const ticks = selection?.noteTicks(note)
              renderedNotes += 1
              return (
                <LazyNoteChangeCard
                  key={note.noteId}
                  eager={renderedNotes <= EAGER_NOTES}
                  note={note}
                  fieldDefs={fieldDefs}
                  context={noteContexts[note.noteId]}
                  granularity={selection?.granularity}
                  checked={ticks?.checked}
                  fieldMask={ticks?.fieldMask}
                  onToggleNote={selection?.onToggleNote}
                  onToggleField={selection?.onToggleField}
                />
              )
            })}
          </div>
        )
      })}

      {hasMore ? (
        <div className="flex justify-center pt-1">
          <Button type="button" variant="outline" disabled={isFetchingMore} onClick={onLoadMore}>
            {isFetchingMore ? <LoaderCircle className="animate-spin" /> : null}
            {t('notes.btn_load_more', 'Tải thêm note')}
          </Button>
        </div>
      ) : null}
    </section>
  )
}
