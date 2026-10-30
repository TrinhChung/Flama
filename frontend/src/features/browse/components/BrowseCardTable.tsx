import '@/shared/config/i18n'
import { memo } from 'react'
import { useTranslation } from 'react-i18next'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AlertTriangle, ArrowUpDown, RefreshCcw, RotateCcw } from 'lucide-react'
import { isValidArrayJson } from '@/entities/flashcard/fields'
import type { BrowseCardRow, BrowseSortBy, BrowseSortDir } from '../types'
import { statusLabel, statusVariant } from '../utils/formatter'
import { BrowsePagination, type BrowsePaginationProps } from './BrowsePagination'
import { useBrowseTableScroll } from '../hooks/useBrowseTableScroll'

export type BrowseArrayViewMode = 'normal' | 'code'

export interface BrowseCardTableProps {
  cards: BrowseCardRow[]
  isPending: boolean
  /** Rows on screen belong to the previous query while the next one loads. */
  isShowingPreviousResult?: boolean
  /** Set only when there is no result to show. */
  error: Error | null
  onRetry: () => void
  total: number
  pages: number
  page: number
  setPage: BrowsePaginationProps['setPage']
  perPage: number
  onPerPageChange: (perPage: number) => void
  selectedCardSet: ReadonlySet<string>
  selectedCount: number
  allSelected: boolean
  onToggleSelectAll: () => void
  onToggleCardSelected: (cardId: string, selected: boolean) => void
  activeCardId: string | null
  onActivateCard: (cardId: string) => void
  sortBy: BrowseSortBy
  sortDir: BrowseSortDir
  onSortChange: (field: BrowseSortBy) => void
  arrayViewMode: BrowseArrayViewMode
}

interface BrowseCardTableRowProps {
  card: BrowseCardRow
  isSelected: boolean
  isActive: boolean
  arrayViewMode: BrowseArrayViewMode
  onActivate: (cardId: string) => void
  onToggleSelected: (cardId: string, selected: boolean) => void
}

const BrowseCardTableRow = memo(function BrowseCardTableRow({
  card,
  isSelected,
  isActive,
  arrayViewMode,
  onActivate,
  onToggleSelected,
}: BrowseCardTableRowProps) {
  const cardId = String(card.card_id)
  const { t } = useTranslation('browse')

  return (
    <TableRow
      className={`hover:bg-muted/40 cursor-pointer transition-all border-b ${
        isActive ? 'bg-primary/5 hover:bg-primary/10 border-l-2 border-l-primary' : ''
      }`}
      onClick={() => onActivate(cardId)}
    >
      <TableCell className="text-center px-2" onClick={(e) => e.stopPropagation()}>
        <Checkbox
          checked={isSelected}
          onCheckedChange={(checked) => onToggleSelected(cardId, checked === true)}
        />
      </TableCell>
      <TableCell className="font-semibold text-foreground truncate max-w-48">
        {card.word}
        {card.base_changed ? <span className="ml-1.5 inline-flex align-middle text-primary"
          title={t('card_table.base_changed', 'Bản gốc đã thay đổi')}>
          <RefreshCcw className="size-3" aria-hidden="true" />
          <span className="sr-only">{t('card_table.base_changed', 'Bản gốc đã thay đổi')}</span>
        </span> : null}
      </TableCell>
      <TableCell className="text-muted-foreground truncate max-w-48">{card.reading}</TableCell>
      <TableCell className="text-muted-foreground truncate max-w-72 leading-relaxed">
        {arrayViewMode === 'code' ? (
          <code className="font-mono text-[11px] text-primary/90 bg-muted/60 px-1.5 py-0.5 rounded border border-border/40 inline-block truncate max-w-full">
            {card.meaning ? (
              isValidArrayJson(card.meaning)
                ? card.meaning
                : JSON.stringify(card.meaning.split(/\s*;\s*|\n+/).filter(Boolean))
            ) : '[]'}
          </code>
        ) : (
          card.meaning
        )}
      </TableCell>
      <TableCell className="text-center">
        <Badge variant={statusVariant(card.status)} className="text-[10px] px-1.5 py-0 font-medium">
          {statusLabel(card.status)}
        </Badge>
      </TableCell>
      <TableCell className="text-muted-foreground">{card.due_label}</TableCell>
    </TableRow>
  )
})

export const BrowseCardTable = memo(function BrowseCardTable({
  cards,
  isPending,
  isShowingPreviousResult = false,
  error,
  onRetry,
  total,
  pages,
  page,
  setPage,
  perPage,
  onPerPageChange,
  selectedCardSet,
  selectedCount,
  allSelected,
  onToggleSelectAll,
  onToggleCardSelected,
  activeCardId,
  onActivateCard,
  sortBy,
  sortDir,
  onSortChange,
  arrayViewMode,
}: BrowseCardTableProps) {
  const { t } = useTranslation('browse')

  const tableContainerRef = useBrowseTableScroll(page)

  if (isPending) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-2">
          <svg className="animate-spin h-8 w-8 text-primary" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-xs text-muted-foreground font-semibold">{t('card_table.searching')}</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div role="alert" className="flex flex-col items-center gap-2 max-w-sm text-center">
          <AlertTriangle className="size-8 text-destructive" />
          <span className="text-xs font-semibold text-foreground">{t('card_table.load_error')}</span>
          <span className="text-xs text-muted-foreground break-words">{error.message}</span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="mt-1 h-8 rounded-lg text-xs gap-1.5"
          >
            <RotateCcw className="size-3.5" />
            {t('card_table.retry')}
          </Button>
        </div>
      </div>
    )
  }

  // Only these columns have a server-side sort (app/services/browse_card_service.py).
  const renderSortableHead = (field: BrowseSortBy, label: string, className: string) => (
    <TableHead className={`${className} cursor-pointer select-none`} onClick={() => onSortChange(field)}>
      <div className="flex items-center gap-1">
        {label}{' '}
        {sortBy === field ? (
          <span className="text-primary font-bold text-xs shrink-0">{sortDir === 'asc' ? '▲' : '▼'}</span>
        ) : (
          <ArrowUpDown className="size-3 opacity-40 shrink-0" />
        )}
      </div>
    </TableHead>
  )

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background overflow-hidden relative">
      {/* Scrollable cards list table */}
      <div ref={tableContainerRef} aria-busy={isShowingPreviousResult} className="flex-1 overflow-auto">
        <Table className="text-xs border-collapse">
          <TableHeader className="sticky top-0 bg-muted/65 z-10 backdrop-blur-sm border-b">
            <TableRow>
              <TableHead className="w-10 text-center px-2">
                <Checkbox checked={allSelected} onCheckedChange={onToggleSelectAll} />
              </TableHead>
              {renderSortableHead('word', t('card_table.columns.word'), 'w-48')}
              <TableHead className="w-48">
                <div className="flex items-center gap-1">{t('card_table.columns.reading')}</div>
              </TableHead>
              <TableHead className="min-w-64">
                <div className="flex items-center gap-1">{t('card_table.columns.meaning')}</div>
              </TableHead>
              <TableHead className="w-24 text-center">
                <div className="flex items-center justify-center gap-1">{t('card_table.columns.status')}</div>
              </TableHead>
              {renderSortableHead('due', t('card_table.columns.due'), 'w-32')}
            </TableRow>
          </TableHeader>
          <TableBody>
            {cards.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10 text-xs text-muted-foreground italic">
                  {t('card_table.no_cards_found')}
                </TableCell>
              </TableRow>
            ) : (
              cards.map((card) => {
                const cardId = String(card.card_id)
                return (
                  <BrowseCardTableRow
                    key={cardId}
                    card={card}
                    isSelected={selectedCardSet.has(cardId)}
                    isActive={activeCardId !== null && String(activeCardId) === cardId}
                    arrayViewMode={arrayViewMode}
                    onActivate={onActivateCard}
                    onToggleSelected={onToggleCardSelected}
                  />
                )
              })
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination Footer */}
      <BrowsePagination
        page={page}
        setPage={setPage}
        perPage={perPage}
        handlePerPageChange={onPerPageChange}
        total={total}
        pages={pages}
        selectedCount={selectedCount}
        isFetchingPage={isShowingPreviousResult}
      />
    </div>
  )
})
