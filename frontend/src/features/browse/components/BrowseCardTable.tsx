import { useRef, useEffect } from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { ArrowUpDown } from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'
import { statusLabel, statusVariant } from '../utils/formatter'
import { BrowsePagination } from './BrowsePagination'

interface BrowseCardTableProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseCardTable({ browse }: BrowseCardTableProps) {
  const {
    cardsQuery,
    cards,
    selectedCards,
    setSelectedCards,
    activeCardId,
    setActiveCardId,
    setIsCreatingCard,
    page,
    setPage,
    perPage,
    handlePerPageChange,
    allSelected,
    handleToggleSelectAllCards,
    setMobileTab,
    sortBy,
    setSortBy,
    sortDir,
    setSortDir,
  } = browse

  const tableContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (typeof tableContainerRef.current?.scrollTo === 'function') {
      tableContainerRef.current.scrollTo({ top: 0, behavior: 'instant' })
    } else if (tableContainerRef.current) {
      tableContainerRef.current.scrollTop = 0
    }
  }, [page])

  if (cardsQuery.isPending) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="flex flex-col items-center gap-2">
          <svg className="animate-spin h-8 w-8 text-primary" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-xs text-muted-foreground font-semibold">Đang tìm thẻ...</span>
        </div>
      </div>
    )
  }

  const toggleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortBy(field)
      setSortDir('asc')
    }
    setPage(1)
  }

  const renderSortIcon = (field: string) => {
    if (sortBy !== field) return <ArrowUpDown className="size-3 opacity-40 shrink-0" />
    return (
      <span className="text-primary font-bold text-xs shrink-0">
        {sortDir === 'asc' ? '▲' : '▼'}
      </span>
    )
  }

  const total = cardsQuery.data?.total || 0
  const pages = cardsQuery.data?.pages || 1

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-background overflow-hidden relative">
      {/* Scrollable cards list table */}
      <div ref={tableContainerRef} className="flex-1 overflow-auto">
        <Table className="text-xs border-collapse">
          <TableHeader className="sticky top-0 bg-muted/65 z-10 backdrop-blur-sm border-b">
            <TableRow>
              <TableHead className="w-10 text-center px-2">
                <Checkbox checked={allSelected} onCheckedChange={handleToggleSelectAllCards} />
              </TableHead>
              <TableHead className="w-48 cursor-pointer select-none" onClick={() => toggleSort('word')}>
                <div className="flex items-center gap-1">Từ vựng {renderSortIcon('word')}</div>
              </TableHead>
              <TableHead className="w-48 cursor-pointer select-none" onClick={() => toggleSort('reading')}>
                <div className="flex items-center gap-1">Đọc {renderSortIcon('reading')}</div>
              </TableHead>
              <TableHead className="min-w-64 cursor-pointer select-none" onClick={() => toggleSort('meaning')}>
                <div className="flex items-center gap-1">Ý nghĩa {renderSortIcon('meaning')}</div>
              </TableHead>
              <TableHead className="w-24 text-center cursor-pointer select-none" onClick={() => toggleSort('status')}>
                <div className="flex items-center justify-center gap-1">Trạng thái {renderSortIcon('status')}</div>
              </TableHead>
              <TableHead className="w-32 cursor-pointer select-none" onClick={() => toggleSort('due')}>
                <div className="flex items-center gap-1">Đến hạn {renderSortIcon('due')}</div>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {cards.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="text-center py-10 text-xs text-muted-foreground italic">
                  Không tìm thấy thẻ nào
                </TableCell>
              </TableRow>
            ) : (
              cards.map((card) => {
                const isSelected = selectedCards.some((id) => String(id) === String(card.card_id))
                const isActive = activeCardId !== null && String(activeCardId) === String(card.card_id)

                return (
                  <TableRow
                    key={card.card_id}
                    className={`hover:bg-muted/40 cursor-pointer transition-all border-b ${
                      isActive ? 'bg-primary/5 hover:bg-primary/10 border-l-2 border-l-primary' : ''
                    }`}
                    onClick={() => {
                      setIsCreatingCard(false)
                      setActiveCardId(String(card.card_id))
                      setMobileTab('editor')
                    }}
                  >
                    <TableCell className="text-center px-2" onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={(checked) => {
                          if (checked) {
                            setSelectedCards((prev) => [...prev, String(card.card_id)])
                          } else {
                            setSelectedCards((prev) => prev.filter((id) => String(id) !== String(card.card_id)))
                          }
                        }}
                      />
                    </TableCell>
                    <TableCell className="font-semibold text-foreground truncate max-w-48">{card.word}</TableCell>
                    <TableCell className="text-muted-foreground truncate max-w-48">{card.reading}</TableCell>
                    <TableCell className="text-muted-foreground truncate max-w-72 leading-relaxed">{card.meaning}</TableCell>
                    <TableCell className="text-center">
                      <Badge variant={statusVariant(card.status)} className="text-[10px] px-1.5 py-0 font-medium">
                        {statusLabel(card.status)}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{card.due_label}</TableCell>
                  </TableRow>
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
        handlePerPageChange={handlePerPageChange}
        total={total}
        pages={pages}
        selectedCount={selectedCards.length}
      />
    </div>
  )
}
