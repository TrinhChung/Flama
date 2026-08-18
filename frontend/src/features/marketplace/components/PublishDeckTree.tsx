import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Layers,
  LockKeyhole,
  Search,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import type { PublishDeckOption } from '../publishApi'

type PublishDeckTreeNode = {
  deck: PublishDeckOption
  children: PublishDeckTreeNode[]
}

function buildPublishDeckTree(decks: PublishDeckOption[]): PublishDeckTreeNode[] {
  const nodes = new Map<number, PublishDeckTreeNode>()
  decks.forEach((deck) => nodes.set(deck.id, { deck, children: [] }))

  const roots: PublishDeckTreeNode[] = []
  decks.forEach((deck) => {
    const node = nodes.get(deck.id)!
    const parent = deck.parent_id == null ? null : nodes.get(deck.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  })

  const sortNodes = (items: PublishDeckTreeNode[]) => {
    items.sort((left, right) => left.deck.name.localeCompare(right.deck.name, 'vi'))
    items.forEach((item) => sortNodes(item.children))
  }
  sortNodes(roots)
  return roots
}

function filteredDeckIds(decks: PublishDeckOption[], search: string): Set<number> {
  const allowed = new Set<number>()
  if (!search.trim()) {
    decks.forEach((deck) => allowed.add(deck.id))
    return allowed
  }

  const byId = new Map(decks.map((deck) => [deck.id, deck]))
  const query = search.trim().toLocaleLowerCase('vi')
  decks.forEach((deck) => {
    const haystack = `${deck.name} ${deck.block_reason || ''}`.toLocaleLowerCase('vi')
    if (!haystack.includes(query)) return
    allowed.add(deck.id)
    let parentId = deck.parent_id
    const seen = new Set<number>()
    while (parentId != null && !seen.has(parentId)) {
      seen.add(parentId)
      allowed.add(parentId)
      parentId = byId.get(parentId)?.parent_id ?? null
    }
  })
  return allowed
}

function blockLabel(code: PublishDeckOption['block_code']): string | null {
  if (code === 'marketplace_clone') return 'Từ Marketplace'
  if (code === 'marketplace_note_type') return 'Dùng Note Type Marketplace'
  if (code === 'already_shared') return 'Đã chia sẻ'
  if (code === 'ancestor_shared') return 'Bộ cha đã chia sẻ'
  if (code === 'descendant_shared') return 'Bộ con đã chia sẻ'
  if (code === 'not_owned') return 'Không thuộc sở hữu'
  return null
}

type TreeItemProps = {
  node: PublishDeckTreeNode
  depth: number
  searchActive: boolean
  expandedIds: Set<number>
  selectedDeckId: string
  onToggle: (deckId: number) => void
  onSelect: (deck: PublishDeckOption) => void
}

function TreeItem({
  node,
  depth,
  searchActive,
  expandedIds,
  selectedDeckId,
  onToggle,
  onSelect,
}: TreeItemProps) {
  const deck = node.deck
  const hasChildren = node.children.length > 0
  const expanded = searchActive || expandedIds.has(deck.id)
  const selected = String(deck.id) === selectedDeckId
  const statusLabel = blockLabel(deck.block_code)

  const selectDeck = () => {
    if (deck.is_selectable) onSelect(deck)
  }

  return (
    <div className="space-y-0.5">
      <div
        role="treeitem"
        aria-selected={selected}
        aria-disabled={!deck.is_selectable}
        aria-expanded={hasChildren ? expanded : undefined}
        tabIndex={0}
        title={deck.block_reason || undefined}
        className={`flex items-center justify-between gap-3 rounded-xl border px-2.5 py-2 text-xs transition-colors ${
          selected
            ? 'border-primary/30 bg-primary/10 text-primary shadow-sm'
            : deck.is_selectable
              ? 'cursor-pointer border-transparent hover:bg-muted/60'
              : 'cursor-not-allowed border-transparent bg-muted/20 text-muted-foreground opacity-75'
        }`}
        style={{ paddingLeft: `calc(0.5rem + ${depth} * clamp(0.45rem, 1.8vw, 0.85rem))` }}
        onClick={selectDeck}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            selectDeck()
          }
        }}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2">
          {hasChildren ? (
            <button
              type="button"
              aria-label={`${expanded ? 'Thu gọn' : 'Mở rộng'} bộ ${deck.name}`}
              className="shrink-0 rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground touch-manipulation min-w-[26px] min-h-[26px] flex items-center justify-center cursor-pointer"
              onClick={(event) => {
                event.stopPropagation()
                onToggle(deck.id)
              }}
            >
              {expanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
            </button>
          ) : (
            <span className="w-3 sm:w-4 shrink-0" />
          )}

          {hasChildren ? (
            expanded ? <FolderOpen className="size-4 shrink-0 text-amber-500" /> : <Folder className="size-4 shrink-0 text-amber-500" />
          ) : (
            <Layers className="size-3.5 shrink-0 text-primary/70" />
          )}
          <span className="truncate font-medium">{deck.name}</span>
        </div>

        <div className="flex shrink-0 items-center gap-1.5 ml-1">
          {deck.card_count > 0 && (
            <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-medium shrink-0">
              {deck.card_count} thẻ
            </Badge>
          )}
          {statusLabel && (
            <Badge variant="outline" className="gap-1 px-1.5 py-0 text-[10px] font-medium shrink-0 max-w-[110px] truncate">
              <LockKeyhole className="size-2.5 shrink-0" />
              <span className="truncate">{statusLabel}</span>
            </Badge>
          )}
        </div>
      </div>

      {hasChildren && expanded && (
        <div>
          {node.children.map((child) => (
            <TreeItem
              key={child.deck.id}
              node={child}
              depth={depth + 1}
              searchActive={searchActive}
              expandedIds={expandedIds}
              selectedDeckId={selectedDeckId}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  )
}

type PublishDeckTreeProps = {
  decks: PublishDeckOption[]
  selectedDeckId: string
  onSelectDeck: (deck: PublishDeckOption) => void
}

export function PublishDeckTree({ decks, selectedDeckId, onSelectDeck }: PublishDeckTreeProps) {
  const [search, setSearch] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<number>>(() => new Set())
  const searchActive = search.trim().length > 0
  const allowedIds = useMemo(() => filteredDeckIds(decks, search), [decks, search])
  const visibleDecks = useMemo(
    () => decks.filter((deck) => allowedIds.has(deck.id)),
    [allowedIds, decks],
  )
  const tree = useMemo(() => buildPublishDeckTree(visibleDecks), [visibleDecks])

  useEffect(() => {
    const selectedId = Number(selectedDeckId)
    if (!Number.isInteger(selectedId)) return
    const byId = new Map(decks.map((deck) => [deck.id, deck]))
    const ancestors: number[] = []
    let parentId = byId.get(selectedId)?.parent_id ?? null
    const seen = new Set<number>()
    while (parentId != null && !seen.has(parentId)) {
      seen.add(parentId)
      ancestors.push(parentId)
      parentId = byId.get(parentId)?.parent_id ?? null
    }
    if (ancestors.length === 0) return
    setExpandedIds((current) => new Set([...current, ...ancestors]))
  }, [decks, selectedDeckId])

  const toggle = useCallback((deckId: number) => {
    setExpandedIds((current) => {
      const next = new Set(current)
      if (next.has(deckId)) next.delete(deckId)
      else next.add(deckId)
      return next
    })
  }, [])

  return (
    <div className="space-y-2.5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm bộ thẻ..."
            className="h-9 rounded-xl pl-9 text-xs"
          />
        </div>
        <div className="flex items-center justify-end gap-1.5 shrink-0">
          <button
            type="button"
            className="rounded-lg border border-border/80 px-2.5 py-1.5 text-xs font-semibold hover:bg-muted transition-colors cursor-pointer"
            onClick={() => setExpandedIds(new Set(decks.map((deck) => deck.id)))}
          >
            Mở rộng
          </button>
          <button
            type="button"
            className="rounded-lg border border-border/80 px-2.5 py-1.5 text-xs font-semibold hover:bg-muted transition-colors cursor-pointer"
            onClick={() => setExpandedIds(new Set())}
          >
            Thu gọn
          </button>
        </div>
      </div>

      <div role="tree" className="max-h-80 space-y-0.5 overflow-y-auto rounded-2xl border bg-muted/15 p-2.5 shadow-inner">
        {tree.length > 0 ? (
          tree.map((node) => (
            <TreeItem
              key={node.deck.id}
              node={node}
              depth={0}
              searchActive={searchActive}
              expandedIds={expandedIds}
              selectedDeckId={selectedDeckId}
              onToggle={toggle}
              onSelect={onSelectDeck}
            />
          ))
        ) : (
          <div className="py-6 text-center text-xs text-muted-foreground">
            Không tìm thấy bộ thẻ phù hợp.
          </div>
        )}
      </div>
    </div>
  )
}
