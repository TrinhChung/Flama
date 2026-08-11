import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Folder, FolderOpen, RotateCcw, Search } from 'lucide-react'
import type { useBrowseState } from '../hooks/useBrowseState'

interface BrowseDeckSidebarProps {
  browse: ReturnType<typeof useBrowseState>
}

export function BrowseDeckSidebar({ browse }: BrowseDeckSidebarProps) {
  const {
    decksQuery,
    selectedDeckId,
    setSelectedDeckId,
    deckSearch,
    setDeckSearch,
    filteredDecks,
    handleResetDeckFilter,
    setPage,
  } = browse

  if (decksQuery.isPending) {
    return (
      <div className="w-full md:w-64 border-r border-border/60 p-4 space-y-4 shrink-0 bg-muted/10">
        <div className="animate-pulse space-y-3">
          <div className="h-9 bg-muted rounded-xl" />
          <div className="h-4 bg-muted rounded w-3/4" />
          <div className="space-y-2 pt-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="h-8 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full md:w-64 border-r border-border/60 flex flex-col shrink-0 bg-muted/5 h-full overflow-hidden">
      {/* Search Sidebar Input */}
      <div className="p-3 border-b border-border/60 space-y-2 shrink-0 bg-background/50">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            placeholder="Lọc danh sách deck…"
            value={deckSearch}
            onChange={(e) => setDeckSearch(e.target.value)}
            className="pl-8 h-8 rounded-lg text-xs"
          />
        </div>
        {selectedDeckId !== null && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleResetDeckFilter}
            className="w-full h-7 text-[11px] font-semibold text-muted-foreground hover:text-primary rounded-lg border border-dashed border-border hover:border-primary/30"
          >
            <RotateCcw className="size-3 mr-1" /> Bỏ chọn lọc deck
          </Button>
        )}
      </div>

      {/* Decks List scrollable */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {filteredDecks.length === 0 ? (
          <div className="text-center py-6 text-xs text-muted-foreground italic">Không thấy deck phù hợp</div>
        ) : (
          filteredDecks.map((deck) => {
            const isSelected = selectedDeckId === deck.id
            const counts = deck.counts || {}
            const totalDue = (counts.new || 0) + (counts.learn || 0) + (counts.due || 0)

            return (
              <button
                key={deck.id}
                type="button"
                onClick={() => {
                  setSelectedDeckId(deck.id)
                  setPage(1)
                }}
                className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-left transition-all ${
                  isSelected
                    ? 'bg-primary text-primary-foreground font-bold shadow-xs'
                    : 'text-foreground hover:bg-muted/40 hover:text-foreground'
                }`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  {isSelected ? (
                    <FolderOpen className="size-3.5 shrink-0" />
                  ) : (
                    <Folder className="size-3.5 text-muted-foreground shrink-0" />
                  )}
                  <span className="text-xs truncate">{deck.name}</span>
                </div>
                {totalDue > 0 && (
                  <Badge
                    variant="outline"
                    className={`text-[10px] px-1.5 py-0 rounded-full shrink-0 border-0 ${
                      isSelected
                        ? 'bg-primary-foreground/15 text-primary-foreground font-bold'
                        : 'bg-primary/10 text-primary border-primary/20'
                    }`}
                  >
                    {totalDue}
                  </Badge>
                )}
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}
