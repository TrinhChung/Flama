import { useState } from 'react'
import { ArrowLeftRight, CheckCircle2, RotateCcw } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { toast } from 'sonner'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Button } from '@/components/ui/button'
import { useStudyOverviewQuery } from '@/entities/study-overview'
import { dashboardApi, dashboardQueryKey, useDashboard } from '../api'
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
  const { t } = useTranslation('dashboard')
  const queryClient = useQueryClient()
  const bootstrapQuery = useBootstrap()
  const dashboardQuery = useDashboard()
  const [year, setYear] = useState(() => new Date().getFullYear())
  // Fetched in parallel with the deck tree; the page only blocks on the tree and
  // the heatmap keeps its own skeleton. A deck-first gate (2026-10-04) measured
  // ~0.1 s faster for the tree but held the heatmap back by a whole deck request
  // (~1 s then, 3-5 s in the 2026-10-13 production audit).
  const overviewQuery = useStudyOverviewQuery(year, { keepPreviousYear: true })

  const [createOpened, setCreateOpened] = useState(false)
  const [selection, setSelection] = useState<SelectedDeckAction | null>(null)
  const [selectedDeckId, setSelectedDeckId] = useState<number | null>(null)

  const moveMutation = useMutation({
    mutationFn: ({ deckId, parentId }: { deckId: number; parentId: number | null }) =>
      dashboardApi.moveDeck(deckId, { parent_id: parentId === null ? '' : String(parentId) }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: dashboardQueryKey })
    },
    onError: (error: Error) => {
      toast.error(error.message || t('tree.toasts.move_error'))
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
      const targetLabel = targetParent
        ? t('tree.toasts.target_deck', { name: targetParent.name })
        : t('tree.toasts.target_root')

      toast.custom(
        (toastId) => (
          <div className="flex items-center gap-3 bg-card border border-orange-200/80 dark:border-orange-900/40 p-2.5 sm:p-3 pr-3 rounded-2xl shadow-xl shadow-orange-950/10 text-foreground text-xs sm:text-sm animate-in slide-in-from-bottom-4 duration-200">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-orange-100 dark:bg-orange-950/70 text-orange-600 dark:text-orange-400">
              <ArrowLeftRight className="size-4" />
            </div>

            <div className="flex flex-col min-w-0 pr-1 space-y-0.5">
              <div className="font-bold text-foreground truncate max-w-[180px] sm:max-w-[220px]">
                {t('tree.toasts.moved_title', { name: deckName })}
              </div>
              <div className="text-[11px] text-muted-foreground truncate max-w-[180px] sm:max-w-[220px]">
                {t('tree.toasts.moved_target_prefix')}{targetLabel}
              </div>
            </div>

            <Button
              type="button"
              className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-gradient-to-r from-primary to-orange-500 hover:opacity-95 text-primary-foreground font-bold text-xs shadow-xs hover:shadow transition-all shrink-0 active:scale-95 cursor-pointer h-auto"
              onClick={() => {
                toast.dismiss(toastId)
                moveMutation.mutate(
                  { deckId, parentId: previousParentId },
                  {
                    onSuccess: () => {
                      toast.custom(
                        () => (
                          <div className="flex items-center gap-2.5 bg-card border border-emerald-200 dark:border-emerald-900/40 p-2.5 px-3.5 rounded-2xl shadow-lg text-xs font-semibold text-emerald-800 dark:text-emerald-300">
                            <CheckCircle2 className="size-4 text-emerald-600 shrink-0" />
                            <span>{t('tree.toasts.restored_toast', { name: deckName })}</span>
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
              <span>{t('tree.toasts.btn_undo')}</span>
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
