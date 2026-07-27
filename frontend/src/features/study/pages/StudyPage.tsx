import { useCallback, useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useBootstrap } from '@/shared/api/bootstrap'
import { useDashboard } from '@/features/dashboard/api'
import type { DeckNode } from '@/features/dashboard/types'
import { StudyHeaderToolbar } from '../components/StudyHeaderToolbar'
import { CardRendererFrame } from '../components/CardRendererFrame'
import { StudyBottomBar } from '../components/StudyBottomBar'
import { EditCardModal } from '../components/EditCardModal'

type Rating = 'again' | 'hard' | 'good' | 'easy'

type FieldDef = {
  name: string
  field_type: string
  required?: boolean
  position?: number
}

type StudyPayload = {
  card_id: string | null
  note_id?: string | null
  template_id?: string | null
  rendered_front_html?: string
  rendered_back_html?: string
  rendered_front_payload?: unknown
  rendered_back_payload?: unknown
  intervals_preview?: Record<Rating, { label?: string }>
  new_count?: number
  learn_count?: number
  due_count?: number
  session_state?: string
  next_due_at?: string | null
  message?: string
  can_edit_card?: boolean
  save_card_url?: string | null
  load_note_url?: string | null
  field_values?: Record<string, string>
  field_defs?: FieldDef[]
}

type AnswerResponse = {
  success: boolean
  next_card_payload: StudyPayload | null
}

function findDeckNode(nodes: DeckNode[], targetId: number | null): DeckNode | null {
  if (targetId === null) return null
  for (const node of nodes) {
    if (node.id === targetId) return node
    const child = findDeckNode(node.children, targetId)
    if (child) return child
  }
  return null
}

export function StudyPage() {
  const [searchParams] = useSearchParams()
  const deckIdRaw = searchParams.get('deck_id')
  const deckIdNum = deckIdRaw ? Number(deckIdRaw) : null
  const queryClient = useQueryClient()

  const bootstrapQuery = useBootstrap()
  const dashboardQuery = useDashboard()

  const [revealed, setRevealed] = useState(false)
  const [editOpened, setEditOpened] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const startedAtRef = useRef(Date.now())
  const queryKey = ['study', 'next', deckIdRaw] as const

  const studyQuery = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<StudyPayload>('/api/study/next', {
        scope: 'deck',
        scope_id: deckIdRaw,
      }),
    enabled: Boolean(deckIdRaw),
  })
  const card = studyQuery.data

  useEffect(() => {
    startedAtRef.current = Date.now()
    setRevealed(false)
  }, [card?.card_id])

  const deckNode = dashboardQuery.data?.decks
    ? findDeckNode(dashboardQuery.data.decks, deckIdNum)
    : null
  const deckName = deckNode?.name || (deckIdRaw ? `Deck #${deckIdRaw}` : null)

  const answerMutation = useMutation({
    mutationFn: (rating: Rating) => {
      if (!card?.card_id) throw new Error('Không có thẻ để chấm.')
      return appApi.mutate<AnswerResponse>(
        `/api/study/${card.card_id}/answer`,
        'POST',
        {
          rating,
          scope: 'deck',
          scope_id: deckIdRaw,
          timezone: bootstrapQuery.data?.user?.timezone,
          duration_ms: Math.max(0, Date.now() - startedAtRef.current),
        },
      )
    },
    onSuccess: (result) => {
      if (result.next_card_payload) {
        queryClient.setQueryData(queryKey, result.next_card_payload)
      } else {
        queryClient.invalidateQueries({ queryKey })
      }
      setRevealed(false)
    },
  })

  const handleAnswer = useCallback(
    (rating: Rating) => {
      if (answerMutation.isPending || !card?.card_id) return
      answerMutation.mutate(rating)
    },
    [answerMutation, card?.card_id],
  )

  const handleToggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().then(() => {
        setIsFullscreen(true)
      }).catch(() => {})
    } else {
      document.exitFullscreen().then(() => {
        setIsFullscreen(false)
      }).catch(() => {})
    }
  }, [])

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement))
    }
    document.addEventListener('fullscreenchange', handleFullscreenChange)
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange)
    }
  }, [])

  // Anki Keyboard Shortcuts (Space/Enter, 1-4, E, F)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName || '').toLowerCase()
      if (activeTag === 'input' || activeTag === 'textarea' || editOpened) {
        return
      }

      if (e.code === 'Space' || e.code === 'Enter') {
        e.preventDefault()
        if (!card?.card_id) return
        if (!revealed) {
          setRevealed(true)
        } else {
          handleAnswer('good')
        }
      } else if (e.key === '1' && revealed) {
        e.preventDefault()
        handleAnswer('again')
      } else if (e.key === '2' && revealed) {
        e.preventDefault()
        handleAnswer('hard')
      } else if (e.key === '3' && revealed) {
        e.preventDefault()
        handleAnswer('good')
      } else if (e.key === '4' && revealed) {
        e.preventDefault()
        handleAnswer('easy')
      } else if ((e.key === 'e' || e.key === 'E') && card?.can_edit_card) {
        e.preventDefault()
        setEditOpened(true)
      } else if (e.key === 'f' || e.key === 'F') {
        e.preventDefault()
        handleToggleFullscreen()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [revealed, card?.card_id, card?.can_edit_card, editOpened, handleAnswer, handleToggleFullscreen])

  if (!deckIdRaw) {
    return (
      <div className="h-screen h-[100dvh] w-full flex flex-col items-center justify-center p-6 text-center space-y-4">
        <h2 className="text-2xl font-bold text-foreground">Phiên học</h2>
        <p className="text-muted-foreground max-w-sm">
          Phiên học cần một deck cụ thể để giữ đúng scope scheduler. Chọn một deck từ dashboard để bắt đầu.
        </p>
        <Button asChild>
          <Link to="/dashboard">Về dashboard</Link>
        </Button>
      </div>
    )
  }

  if (studyQuery.isPending) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center">
        <PageLoading label="Đang chuẩn bị phiên học…" />
      </div>
    )
  }

  if (studyQuery.error) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center p-6">
        <PageError error={studyQuery.error} />
      </div>
    )
  }

  return (
    <div className="study-page h-screen h-[100dvh] max-h-screen max-h-[100dvh] w-full flex flex-col m-0 p-0 pb-[calc(5rem+env(safe-area-inset-bottom,0px))] overflow-hidden bg-background text-foreground">
      {/* Top Header Toolbar & Deck Context Bar */}
      {!isFullscreen ? (
        <div className="px-3 pt-2 shrink-0">
          <StudyHeaderToolbar deckName={deckName} deckId={deckIdRaw} cardId={card?.card_id} />
        </div>
      ) : null}

      {answerMutation.error ? (
        <div className="px-4 py-1 shrink-0">
          <PageError error={answerMutation.error} />
        </div>
      ) : null}

      {/* Full-bleed Study Card Shell */}
      {card?.card_id ? (
        <div className="study-card-shell flex-1 flex flex-col w-full h-full min-h-0 min-w-0 overflow-hidden relative">
          <CardRendererFrame
            cardId={card.card_id}
            noteId={card.note_id}
            revealed={revealed}
            frontPayload={card.rendered_front_payload}
            backPayload={card.rendered_back_payload}
            frontHtml={card.rendered_front_html}
            backHtml={card.rendered_back_html}
            scope="deck"
            scopeId={deckIdRaw}
            fieldDefs={card.field_defs}
            fieldValues={card.field_values}
          />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-card border border-border/80 rounded-2xl m-4 space-y-4 max-w-2xl mx-auto my-auto shadow-sm">
          <div className="study-counters-line text-xs font-semibold text-muted-foreground flex items-center gap-2">
            <span className="text-emerald-600 font-bold">
              Mới <strong>{card?.new_count || 0}</strong>
            </span>
            <span className="text-border">&middot;</span>
            <span className="text-amber-600 font-bold">
              Đang học <strong>{card?.learn_count || 0}</strong>
            </span>
            <span className="text-border">&middot;</span>
            <span className="text-rose-600 font-bold">
              Đến hạn <strong>{card?.due_count || 0}</strong>
            </span>
          </div>

          {card?.session_state === 'waiting' ? (
            <>
              <h3 className="text-xl font-bold text-foreground">
                Buổi học vẫn đang tiếp tục.
              </h3>
              <p className="text-sm text-muted-foreground max-w-md">
                {card?.message ||
                  `Bạn vẫn còn ${card?.learn_count || 0} thẻ đang học trong buổi này.`}
              </p>
              {card?.next_due_at ? (
                <p className="text-xs text-orange-600 font-semibold">
                  Thẻ đang học tiếp theo sẽ sẵn sàng sau ít phút nữa (lúc{' '}
                  {new Date(card.next_due_at).toLocaleTimeString('vi-VN')}).
                </p>
              ) : null}
            </>
          ) : (
            <>
              <h3 className="text-xl font-bold text-foreground">
                Deck này hiện không còn thẻ đến hạn.
              </h3>
              <p className="text-sm text-muted-foreground max-w-md">
                Bạn đã hoàn thành lượt học hiện tại của deck này.
              </p>
            </>
          )}

          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => studyQuery.refetch()}
            >
              Tiếp tục / Kiểm tra lại
            </Button>
            <Button asChild size="sm" className="bg-primary font-bold text-primary-foreground">
              <Link to="/dashboard">Về dashboard</Link>
            </Button>
          </div>
        </div>
      )}

      {/* Fixed Bottom Control Bar */}
      {card?.card_id ? (
        <StudyBottomBar
          cardId={card.card_id}
          revealed={revealed}
          canEdit={Boolean(card.can_edit_card)}
          newCount={card.new_count || 0}
          learnCount={card.learn_count || 0}
          dueCount={card.due_count || 0}
          intervalsPreview={card.intervals_preview}
          isFullscreen={isFullscreen}
          submitting={answerMutation.isPending}
          onReveal={() => setRevealed(true)}
          onAnswer={handleAnswer}
          onEdit={() => setEditOpened(true)}
          onToggleFullscreen={handleToggleFullscreen}
        />
      ) : null}

      {/* Edit Card Modal */}
      {card?.card_id && card.can_edit_card ? (
        <EditCardModal
          opened={editOpened}
          onClose={() => setEditOpened(false)}
          cardId={card.card_id}
          saveUrl={card.save_card_url}
          fieldDefs={card.field_defs}
          initialFieldValues={card.field_values}
          onSaved={() => {
            studyQuery.refetch()
          }}
        />
      ) : null}
    </div>
  )
}
