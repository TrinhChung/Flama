import { useState } from 'react'
import { ArrowLeftRight, CheckCircle2, RotateCcw } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Button } from '@/components/ui/button'
import { dashboardQueryKey, useDashboard, useDashboardOverview } from '../api'
import type { DeckNode, SelectedDeckAction } from '../types'

export function findDeck(nodes: DeckNode[], deckId: number | null): DeckNode | null {
  if (deckId === null) return null
  for (const node of nodes) {
    if (node.id === deckId) return node
    const child = findDeck(node.children, deckId)
    if (child) return child
  }
  return null
}

export function useDashboardPage() {
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const dashboardQuery = useDashboard()
  const [year, setYear] = useState(() => new Date().getFullYear())
  const overviewQuery = useDashboardOverview(year)

  const [createOpened, setCreateOpened] = useState(false)
  const [selection, setSelection] = useState<SelectedDeckAction | null>(null)
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(null)

  const moveMutation = useMutation({
    mutationFn: ({ deckId, parentId }: { deckId: number; parentId: number | null }) =>
      appApi.moveDeck(deckId, { parent_id: parentId === null ? '' : String(parentId) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Không thể di chuyển deck.')
    },
  })

  const handleMoveDeck = async (deckId: number, targetParentId: number | null) => {
    if (!dashboardQuery.data) return
    const deckToMove = findDeck(dashboardQuery.data.decks, deckId)
    if (!deckToMove) return

    const previousParentId = deckToMove.parent_id ?? null
    const deckName = deckToMove.name

    try {
      await moveMutation.mutateAsync({ deckId, parentId: targetParentId })
      const targetParent = targetParentId !== null ? findDeck(dashboardQuery.data.decks, targetParentId) : null
      const targetLabel = targetParent ? `deck "${targetParent.name}"` : 'cấp Root'

      toast.custom(
        (t) => (
          <div className="flex items-center gap-3 bg-card border border-orange-200/80 dark:border-orange-900/40 p-2.5 sm:p-3 pr-3 rounded-2xl shadow-xl shadow-orange-950/10 text-foreground text-xs sm:text-sm animate-in slide-in-from-bottom-4 duration-200">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-orange-100 dark:bg-orange-950/70 text-orange-600 dark:text-orange-400">
              <ArrowLeftRight className="size-4" />
            </div>

            <div className="flex flex-col min-w-0 pr-1 space-y-0.5">
              <div className="font-bold text-foreground truncate max-w-[180px] sm:max-w-[220px]">
                Đã di chuyển “{deckName}”
              </div>
              <div className="text-[11px] text-muted-foreground truncate max-w-[180px] sm:max-w-[220px]">
                Vào {targetLabel}
              </div>
            </div>

            <Button
              type="button"
              className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-primary to-orange-500 hover:opacity-95 text-primary-foreground font-bold text-xs shadow-xs hover:shadow transition-all shrink-0 active:scale-95 cursor-pointer h-auto"
              onClick={() => {
                toast.dismiss(t)
                moveMutation.mutate(
                  { deckId, parentId: previousParentId },
                  {
                    onSuccess: () => {
                      toast.custom(
                        () => (
                          <div className="flex items-center gap-2.5 bg-card border border-emerald-200 dark:border-emerald-900/40 p-2.5 px-3.5 rounded-2xl shadow-lg text-xs font-semibold text-emerald-800 dark:text-emerald-300">
                            <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                            <span>Đã khôi phục vị trí ban đầu của “{deckName}”.</span>
                          </div>
                        ),
                        { duration: 3500 },
                      )
                    },
                  },
                )
              }}
            >
              <RotateCcw className="size-3.5" />
              <span>Hoàn tác</span>
            </Button>
          </div>
        ),
        { duration: 7000 },
      )
    } catch {
      // Error is handled in mutation onError
    }
  }

  return {
    bootstrapQuery,
    dashboardQuery,
    overviewQuery,
    year,
    setYear,
    createOpened,
    setCreateOpened,
    selection,
    setSelection,
    selectedDeckId,
    setSelectedDeckId,
    handleMoveDeck,
  }
}
