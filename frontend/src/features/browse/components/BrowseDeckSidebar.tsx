import { useState, useMemo, useCallback, useEffect } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Folder, FolderOpen, RotateCcw, Search, ChevronRight, ChevronDown, AlertTriangle } from 'lucide-react'
import type { useBrowseState, BrowseDeck } from '../hooks/useBrowseState'

interface BrowseDeckSidebarProps {
  browse: ReturnType<typeof useBrowseState>
}

interface BrowseDeckTreeNode {
  deck: BrowseDeck
  children: BrowseDeckTreeNode[]
}

function buildBrowseDeckTree(decks: BrowseDeck[], allowedIds: Set<number>): BrowseDeckTreeNode[] {
  const nodes = new Map<number, BrowseDeckTreeNode>()
  
  decks.forEach((deck) => {
    if (allowedIds.has(deck.id)) {
      nodes.set(deck.id, { deck, children: [] })
    }
  })

  const roots: BrowseDeckTreeNode[] = []
  decks.forEach((deck) => {
    if (!allowedIds.has(deck.id)) return
    const node = nodes.get(deck.id)!
    const parentId = deck.parent_id
    const parent = parentId == null ? null : nodes.get(parentId)
    if (parent) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  })

  const sortNodes = (items: BrowseDeckTreeNode[]) => {
    items.sort((left, right) => left.deck.name.localeCompare(right.deck.name, 'vi'))
    items.forEach((item) => sortNodes(item.children))
  }
  sortNodes(roots)
  return roots
}

export function BrowseDeckSidebar({ browse }: BrowseDeckSidebarProps) {
  const {
    decksQuery,
    selectedDeckId,
    setSelectedDeckId,
    deckSearch,
    setDeckSearch,
    handleResetDeckFilter,
    setPage,
  } = browse

  const [expandedNodes, setExpandedNodes] = useState<Record<number, boolean>>({})

  const toggleExpand = useCallback((deckId: number) => {
    setExpandedNodes((prev) => ({ ...prev, [deckId]: !prev[deckId] }))
  }, [])

  // Auto expand selected deck parent hierarchy on change
  useEffect(() => {
    if (selectedDeckId === null) return
    const decks = decksQuery.data?.decks || []
    const byId = new Map(decks.map((d) => [d.id, d]))
    const toExpand: Record<number, boolean> = {}

    let current = byId.get(selectedDeckId)
    while (current) {
      const parentId = current.parent_id
      if (parentId != null) {
        toExpand[parentId] = true
        current = byId.get(parentId)
      } else {
        break
      }
    }
    setExpandedNodes((prev) => ({ ...prev, ...toExpand }))
  }, [selectedDeckId, decksQuery.data?.decks])

  // Get allowed deck IDs based on filter
  const allowedIds = useMemo(() => {
    const allowed = new Set<number>()
    const decks = decksQuery.data?.decks || []
    if (!deckSearch.trim()) {
      decks.forEach((d) => allowed.add(d.id))
      return allowed
    }

    const byId = new Map(decks.map((d) => [d.id, d]))
    const query = deckSearch.trim().toLowerCase()
    decks.forEach((deck) => {
      if (deck.name.toLowerCase().includes(query)) {
        allowed.add(deck.id)
        let parentId = deck.parent_id
        const seen = new Set<number>()
        while (parentId != null && !seen.has(parentId)) {
          seen.add(parentId)
          allowed.add(parentId)
          parentId = byId.get(parentId)?.parent_id ?? null
        }
      }
    })
    return allowed
  }, [decksQuery.data?.decks, deckSearch])

  // Build recursive tree nodes
  const treeRoots = useMemo(() => {
    const decks = decksQuery.data?.decks || []
    return buildBrowseDeckTree(decks, allowedIds)
  }, [decksQuery.data?.decks, allowedIds])

  if (decksQuery.isPending) {
    return (
      <div className="w-full md:w-64 border-r border-border/60 p-4 space-y-4 shrink-0 bg-sidebar">
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

  const renderTreeNode = (node: BrowseDeckTreeNode, level: number) => {
    const hasChildren = node.children.length > 0
    const isSelected = selectedDeckId === node.deck.id
    const isExpanded = !!deckSearch.trim() || !!expandedNodes[node.deck.id]
    const counts = node.deck.counts || {}
    const totalDue = (counts.new || 0) + (counts.learn || 0) + (counts.due || 0)

    return (
      <div key={node.deck.id} className="space-y-0.5">
        <div
          style={{ paddingLeft: `${level * 0.75 + 0.5}rem` }}
          className={`group flex items-center justify-between py-1.5 px-2.5 rounded-lg cursor-pointer transition-all text-xs ${
            isSelected
              ? 'bg-primary text-primary-foreground font-bold shadow-xs'
              : 'text-foreground hover:bg-muted/40'
          }`}
          onClick={() => {
            setSelectedDeckId(node.deck.id)
            setPage(1)
          }}
        >
          <div className="flex items-center gap-1.5 min-w-0 flex-1">
            {hasChildren ? (
              <button
                type="button"
                className={`p-0.5 rounded hover:bg-muted-foreground/10 shrink-0 transition-colors ${
                  isSelected ? 'text-primary-foreground hover:bg-primary-foreground/15' : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={(e) => {
                  e.stopPropagation()
                  toggleExpand(node.deck.id)
                }}
              >
                {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
              </button>
            ) : (
              <span className="w-4.5 shrink-0" />
            )}

            <div className="flex items-center gap-1.5 min-w-0">
              {hasChildren ? (
                isExpanded ? (
                  <FolderOpen className={`size-3.5 shrink-0 ${isSelected ? 'text-primary-foreground' : 'text-amber-500'}`} />
                ) : (
                  <Folder className={`size-3.5 shrink-0 ${isSelected ? 'text-primary-foreground' : 'text-amber-500'}`} />
                )
              ) : (
                <Folder className={`size-3.5 shrink-0 ${isSelected ? 'text-primary-foreground' : 'text-muted-foreground/60'}`} />
              )}
              <span className="truncate text-xs">{node.deck.name}</span>
              {node.deck.has_mixed_note_types && (
                <span
                  title={`Bộ deck chứa nhiều loại Note Type khác nhau: ${node.deck.note_type_names?.join(', ')}`}
                  className="shrink-0 inline-flex items-center"
                >
                  <AlertTriangle className={`size-3 ${isSelected ? 'text-primary-foreground/90' : 'text-amber-500'}`} />
                </span>
              )}
            </div>
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
        </div>

        {hasChildren && isExpanded && (
          <div className="space-y-0.5">
            {node.children.map((child) => renderTreeNode(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="w-full md:w-64 border-r border-border/60 flex flex-col shrink-0 bg-card h-full overflow-hidden">
      {/* Search Sidebar Input */}
      <div className="p-3 border-b border-border/60 space-y-2 shrink-0 bg-background/50">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            placeholder="Lọc danh sách deck…"
            value={deckSearch}
            onChange={(e) => setDeckSearch(e.target.value)}
            className="pl-8 h-8 rounded-lg text-xs bg-muted/50"
          />
        </div>
        {selectedDeckId !== null && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleResetDeckFilter}
            className="w-full h-7 text-[11px] font-bold text-primary hover:bg-primary/5 hover:text-primary border-primary/20 hover:border-primary/40 bg-background rounded-lg"
          >
            <RotateCcw className="size-3 mr-1" /> Bỏ chọn lọc deck
          </Button>
        )}
      </div>

      {/* Decks List scrollable */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {treeRoots.length === 0 ? (
          <div className="text-center py-6 text-xs text-muted-foreground italic">Không thấy deck phù hợp</div>
        ) : (
          treeRoots.map((root) => renderTreeNode(root, 0))
        )}
      </div>
    </div>
  )
}
