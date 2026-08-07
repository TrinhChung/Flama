import React, { useState, useMemo, useCallback } from 'react'
import {
  ChevronRight,
  ChevronDown,
  Folder,
  FolderOpen,
  Layers,
} from 'lucide-react'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'

export interface AnkiDeckTreeNode {
  fullName: string
  displayName: string
  level: number
  children: AnkiDeckTreeNode[]
}

export function buildAnkiDeckTree(deckNames: string[]): AnkiDeckTreeNode[] {
  const rootNodes: AnkiDeckTreeNode[] = []
  const nodeMap = new Map<string, AnkiDeckTreeNode>()

  const sortedNames = [...deckNames].sort()

  for (const fullName of sortedNames) {
    const parts = fullName.split('::')
    const displayName = parts[parts.length - 1]
    const level = parts.length - 1

    const node: AnkiDeckTreeNode = {
      fullName,
      displayName,
      level,
      children: [],
    }

    nodeMap.set(fullName, node)

    if (parts.length === 1) {
      rootNodes.push(node)
    } else {
      const parentFullName = parts.slice(0, -1).join('::')
      const parentNode = nodeMap.get(parentFullName)
      if (parentNode) {
        parentNode.children.push(node)
      } else {
        rootNodes.push(node)
      }
    }
  }

  return rootNodes
}

interface TreeNodeItemProps {
  node: AnkiDeckTreeNode
  isSearchActive: boolean
  expandedNodes: Record<string, boolean>
  selectedDecks: string[]
  deckNoteCounts: Record<string, number>
  onToggleExpand: (fullName: string, defaultExpanded: boolean) => void
  onSelectDeck: (deckName: string) => void
}

const TreeNodeItem = React.memo<TreeNodeItemProps>(({
  node,
  isSearchActive,
  expandedNodes,
  selectedDecks,
  deckNoteCounts,
  onToggleExpand,
  onSelectDeck,
}) => {
  const hasChildren = node.children.length > 0
  const defaultExpanded = node.level === 0
  const isExpanded = isSearchActive || (expandedNodes[node.fullName] ?? defaultExpanded)
  const isSelected = selectedDecks.includes(node.fullName)
  const noteCount = deckNoteCounts[node.fullName]

  return (
    <div className="space-y-0.5">
      <div
        className={`flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer transition-colors text-xs hover:bg-muted/50 ${
          isSelected ? 'bg-primary/15 font-semibold text-primary' : 'text-foreground'
        }`}
        style={{ paddingLeft: `${Math.max(node.level * 1.25, 0.5)}rem` }}
        onClick={() => onSelectDeck(node.fullName)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {hasChildren ? (
            <button
              type="button"
              className="p-1 hover:bg-muted/80 rounded text-muted-foreground hover:text-foreground shrink-0 transition-colors"
              onClick={(e) => {
                e.stopPropagation()
                onToggleExpand(node.fullName, defaultExpanded)
              }}
              title={isExpanded ? 'Thu gọn deck' : 'Mở rộng deck'}
            >
              {isExpanded ? <ChevronDown className="size-4 text-primary" /> : <ChevronRight className="size-4" />}
            </button>
          ) : (
            <span className="w-4 shrink-0" />
          )}

          <Checkbox
            checked={isSelected}
            onCheckedChange={() => onSelectDeck(node.fullName)}
            onClick={(e) => e.stopPropagation()}
          />

          <div
            className="flex items-center gap-1.5 min-w-0 cursor-pointer"
            onClick={(e) => {
              if (hasChildren) {
                e.stopPropagation()
                onToggleExpand(node.fullName, defaultExpanded)
              }
            }}
          >
            {hasChildren ? (
              isExpanded ? (
                <FolderOpen className="size-4 text-amber-500 shrink-0" />
              ) : (
                <Folder className="size-4 text-amber-500 shrink-0" />
              )
            ) : (
              <Layers className="size-3.5 text-primary/70 shrink-0" />
            )}
            <span className="truncate">{node.displayName}</span>
            {node.level > 0 && (
              <span className="text-[10px] text-muted-foreground font-mono truncate hidden md:inline">
                ({node.fullName})
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <span className="text-[11px] font-mono text-muted-foreground">
            {noteCount !== undefined ? `${noteCount} thẻ` : '-'}
          </span>
          <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-normal">
            Chưa từng đồng bộ
          </Badge>
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div className="space-y-0.5">
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.fullName}
              node={child}
              isSearchActive={isSearchActive}
              expandedNodes={expandedNodes}
              selectedDecks={selectedDecks}
              deckNoteCounts={deckNoteCounts}
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

interface AnkiDeckTreeViewProps {
  decks: string[]
  searchQuery: string
  selectedDecks: string[]
  deckNoteCounts: Record<string, number>
  onSelectDeck: (deckName: string) => void
}

export const AnkiDeckTreeView: React.FC<AnkiDeckTreeViewProps> = ({
  decks,
  searchQuery,
  selectedDecks,
  deckNoteCounts,
  onSelectDeck,
}) => {
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({})

  const toggleExpand = useCallback((fullName: string, defaultExpanded: boolean) => {
    setExpandedNodes((prev) => {
      const current = prev[fullName] ?? defaultExpanded
      return { ...prev, [fullName]: !current }
    })
  }, [])

  const expandAll = useCallback(() => {
    const next: Record<string, boolean> = {}
    decks.forEach((d) => (next[d] = true))
    setExpandedNodes(next)
  }, [decks])

  const collapseAll = useCallback(() => {
    setExpandedNodes({})
  }, [])

  // Filter decks matching search using useMemo
  const isSearchActive = searchQuery.trim().length > 0
  const filteredDecks = useMemo(() => {
    if (!isSearchActive) return decks
    const q = searchQuery.toLowerCase()
    return decks.filter((d) => d.toLowerCase().includes(q))
  }, [decks, searchQuery, isSearchActive])

  // Memoize tree structure build
  const treeRoots = useMemo(() => buildAnkiDeckTree(filteredDecks), [filteredDecks])

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground px-1 pb-1">
        <span>Cấu trúc cây danh mục ({filteredDecks.length} deck)</span>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={expandAll}
            className="hover:text-foreground text-[11px] underline"
          >
            Mở rộng tất cả
          </button>
          <span>•</span>
          <button
            type="button"
            onClick={collapseAll}
            className="hover:text-foreground text-[11px] underline"
          >
            Thu gọn tất cả
          </button>
        </div>
      </div>

      <div className="border rounded-xl p-2 bg-card/40 max-h-72 overflow-y-auto space-y-0.5">
        {treeRoots.length === 0 ? (
          <div className="text-center text-xs text-muted-foreground py-6">
            Không tìm thấy deck Anki phù hợp.
          </div>
        ) : (
          treeRoots.map((rootNode) => (
            <TreeNodeItem
              key={rootNode.fullName}
              node={rootNode}
              isSearchActive={isSearchActive}
              expandedNodes={expandedNodes}
              selectedDecks={selectedDecks}
              deckNoteCounts={deckNoteCounts}
              onToggleExpand={toggleExpand}
              onSelectDeck={onSelectDeck}
            />
          ))
        )}
      </div>
    </div>
  )
}
