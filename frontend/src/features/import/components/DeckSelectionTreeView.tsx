import React, { useState, useMemo, useCallback, useEffect } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Layers,
  Search,
} from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'

export type DeckOption = {
  id: number
  name: string
  path: string
  note_type_id?: string | null
  parent_id?: number | null
  notes_count?: number
}

interface TreeNode {
  deck: DeckOption
  children: TreeNode[]
}

const buildDeckTree = (decks: DeckOption[], allowedIds: Set<number>): TreeNode[] => {
  const nodeMap = new Map<number, TreeNode>()
  const roots: TreeNode[] = []

  // Create nodes for all decks that are in the allowedIds filter set
  decks.forEach((deck) => {
    if (allowedIds.has(deck.id)) {
      nodeMap.set(deck.id, { deck, children: [] })
    }
  })

  // Hook up nodes to parents or roots
  decks.forEach((deck) => {
    if (!allowedIds.has(deck.id)) return

    const node = nodeMap.get(deck.id)!
    const parentId = deck.parent_id

    if (parentId === null || parentId === undefined || !nodeMap.has(parentId)) {
      roots.push(node)
    } else {
      const parentNode = nodeMap.get(parentId)!
      parentNode.children.push(node)
    }
  })

  // Sort child nodes by name or position
  const sortTreeNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.deck.name.localeCompare(b.deck.name))
    nodes.forEach((n) => sortTreeNodes(n.children))
  }
  sortTreeNodes(roots)

  return roots
}

const getFilteredDeckIds = (decks: DeckOption[], query: string): Set<number> => {
  const matchSet = new Set<number>()
  if (!query.trim()) {
    decks.forEach((d) => matchSet.add(d.id))
    return matchSet
  }

  const q = query.toLowerCase()
  const matchingDecks = decks.filter(
    (d) => d.name.toLowerCase().includes(q) || d.path.toLowerCase().includes(q)
  )

  const deckMap = new Map<number, DeckOption>()
  decks.forEach((d) => deckMap.set(d.id, d))

  matchingDecks.forEach((d) => {
    matchSet.add(d.id)
    let parentId = d.parent_id
    while (parentId !== null && parentId !== undefined && deckMap.has(parentId)) {
      matchSet.add(parentId)
      parentId = deckMap.get(parentId)!.parent_id
    }
  })

  return matchSet
}

interface TreeNodeItemProps {
  node: TreeNode
  isSearchActive: boolean
  expandedNodes: Record<string, boolean>
  selectedDeckId: string
  onToggleExpand: (path: string) => void
  onSelectDeck: (deckId: string) => void
}

const TreeNodeItem = React.memo<TreeNodeItemProps>(({
  node,
  isSearchActive,
  expandedNodes,
  selectedDeckId,
  onToggleExpand,
  onSelectDeck,
}) => {
  const hasChildren = node.children.length > 0
  const isSelected = String(node.deck.id) === selectedDeckId
  const level = node.deck.path.split('::').length - 1
  const isExpanded = isSearchActive || expandedNodes[node.deck.path] === true
  const notesCount = Number(node.deck.notes_count || 0)

  return (
    <div className="space-y-0.5">
      <div
        className={`flex items-center justify-between py-1.5 px-2.5 rounded-xl cursor-pointer transition-all border text-xs ${
          isSelected
            ? 'bg-primary/10 border-primary/20 text-primary font-semibold shadow-sm'
            : 'border-transparent text-foreground hover:bg-muted/60'
        }`}
        style={{ paddingLeft: `${Math.max(level * 0.85, 0.45)}rem` }}
        onClick={() => onSelectDeck(String(node.deck.id))}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {hasChildren ? (
            <button
              type="button"
              className="p-0.5 hover:bg-muted/80 rounded text-muted-foreground hover:text-foreground shrink-0 transition-colors"
              aria-label={`${isExpanded ? 'Thu gọn' : 'Mở rộng'} deck ${node.deck.name}`}
              onClick={(e) => {
                e.stopPropagation()
                onToggleExpand(node.deck.path)
              }}
            >
              {isExpanded ? <ChevronDown className="size-3.5 text-primary" /> : <ChevronRight className="size-3.5" />}
            </button>
          ) : (
            <span className="w-4 shrink-0" />
          )}

          <div className="flex items-center gap-2 min-w-0">
            {hasChildren ? (
              isExpanded ? (
                <FolderOpen className="size-4 text-amber-500 shrink-0" />
              ) : (
                <Folder className="size-4 text-amber-500 shrink-0" />
              )
            ) : (
              <Layers className="size-3.5 text-primary/70 shrink-0" />
            )}
            <span className="truncate text-xs">{node.deck.name}</span>
          </div>
        </div>

        {notesCount > 0 && (
          <Badge
            variant={isSelected ? 'default' : 'secondary'}
            className="text-[10px] py-0 px-1.5 font-medium select-none shrink-0"
          >
            {notesCount} thẻ
          </Badge>
        )}
      </div>

      {hasChildren && isExpanded && (
        <div className="space-y-0.5">
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.deck.id}
              node={child}
              isSearchActive={isSearchActive}
              expandedNodes={expandedNodes}
              selectedDeckId={selectedDeckId}
              onToggleExpand={onToggleExpand}
              onSelectDeck={onSelectDeck}
            />
          ))}
        </div>
      )}
    </div>
  )
})

TreeNodeItem.displayName = 'TreeNodeItem'

interface DeckSelectionTreeViewProps {
  deckOptions: DeckOption[]
  selectedDeckId: string
  onSelectDeck: (deckId: string) => void
}

export const DeckSelectionTreeView: React.FC<DeckSelectionTreeViewProps> = ({
  deckOptions,
  selectedDeckId,
  onSelectDeck,
}) => {
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({})

  const toggleExpand = useCallback((path: string) => {
    setExpandedNodes((prev) => {
      return { ...prev, [path]: prev[path] !== true }
    })
  }, [])

  // Keep a preselected nested deck visible without expanding every root folder.
  useEffect(() => {
    const selectedId = Number(selectedDeckId)
    if (!Number.isInteger(selectedId)) return

    const deckById = new Map(deckOptions.map((deck) => [deck.id, deck]))
    const ancestorPaths: string[] = []
    const seen = new Set<number>()
    let current = deckById.get(selectedId)

    while (current?.parent_id != null && !seen.has(current.id)) {
      seen.add(current.id)
      const parent = deckById.get(current.parent_id)
      if (!parent) break
      ancestorPaths.push(parent.path)
      current = parent
    }

    if (ancestorPaths.length === 0) return
    setExpandedNodes((prev) => {
      const next = { ...prev }
      ancestorPaths.forEach((path) => {
        next[path] = true
      })
      return next
    })
  }, [deckOptions, selectedDeckId])

  const expandAll = useCallback(() => {
    const next: Record<string, boolean> = {}
    deckOptions.forEach((d) => (next[d.path] = true))
    setExpandedNodes(next)
  }, [deckOptions])

  const collapseAll = useCallback(() => {
    setExpandedNodes({})
  }, [])

  // Filter decks matching search
  const isSearchActive = searchQuery.trim().length > 0
  const allowedIds = useMemo(() => {
    return getFilteredDeckIds(deckOptions, searchQuery)
  }, [deckOptions, searchQuery])

  // Build filtered tree structure
  const treeRoots = useMemo(() => {
    return buildDeckTree(deckOptions, allowedIds)
  }, [deckOptions, allowedIds])

  return (
    <div className="space-y-2.5">
      {/* Search and control bar */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Tìm kiếm deck..."
            className="pl-9 h-8.5 text-xs rounded-xl border-border/80 focus-visible:ring-1"
          />
        </div>
        <div className="flex items-center justify-end gap-1.5 shrink-0 select-none">
          <button
            type="button"
            onClick={expandAll}
            className="hover:text-primary hover:bg-muted text-[10px] font-semibold px-2 py-1 rounded-lg transition-colors border cursor-pointer"
          >
            Mở rộng tất cả
          </button>
          <button
            type="button"
            onClick={collapseAll}
            className="hover:text-primary hover:bg-muted text-[10px] font-semibold px-2 py-1 rounded-lg transition-colors border cursor-pointer"
          >
            Thu gọn tất cả
          </button>
        </div>
      </div>

      {/* Tree view list */}
      <div className="border border-border/80 rounded-2xl p-2.5 bg-muted/20 max-h-72 overflow-y-auto space-y-0.5 shadow-inner">
        {treeRoots.length === 0 ? (
          <div className="text-center text-xs text-muted-foreground py-6">
            Không tìm thấy deck phù hợp.
          </div>
        ) : (
          treeRoots.map((rootNode) => (
            <TreeNodeItem
              key={rootNode.deck.id}
              node={rootNode}
              isSearchActive={isSearchActive}
              expandedNodes={expandedNodes}
              selectedDeckId={selectedDeckId}
              onToggleExpand={toggleExpand}
              onSelectDeck={onSelectDeck}
            />
          ))
        )}
      </div>
    </div>
  )
}
