import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { StudyHeaderToolbar } from '../components/StudyHeaderToolbar'
import { StudyCardRendererFrame } from '../components/StudyCardRendererFrame'
import { StudyBottomBar } from '../components/StudyBottomBar'
import { StudyCompletionCard } from '../components/StudyCompletionCard'
import { useStudySession } from '../hooks/useStudySession'
import { isBackgroundRolloverCommit } from '../session/studySessionEngine'
import type { Rating } from '../types'
import type { SchedulerDecision } from '../scheduler/types'

export function StudyPage() {
  const [searchParams] = useSearchParams()
  const deckIdRaw = searchParams.get('deck_id')
  const study = useStudySession(deckIdRaw)

  const [revealedCardKey, setRevealedCardKey] = useState<string | null>(null)
  const [decisionState, setDecisionState] = useState<{
    cardKey: string
    value: SchedulerDecision
  } | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const startedAtRef = useRef(performance.now())

  const card = study.view?.card ?? null
  const template = study.view?.template ?? null
  const content = study.view?.content ?? null
  const activeCardKey = card?.card_id && study.session?.snapshot.session_id
    ? `${study.session.snapshot.session_id}:${card.card_id}`
    : null
  const revealed = Boolean(
    activeCardKey && revealedCardKey === activeCardKey,
  )
  const decision = decisionState && decisionState.cardKey === activeCardKey
    ? decisionState.value
    : null

  useEffect(() => {
    startedAtRef.current = performance.now()
  }, [activeCardKey])

  const deckName = study.session?.snapshot.scope.name
    || (deckIdRaw ? `Deck #${deckIdRaw}` : null)

  const handleReveal = useCallback(() => {
    if (!card?.card_id || !activeCardKey || study.isBusy) return
    try {
      setDecisionState({
        cardKey: activeCardKey,
        value: study.prepareDecision(card.card_id),
      })
      setRevealedCardKey(activeCardKey)
    } catch {
      // The hook exposes the actionable error after an answer/commit. A reveal
      // can only fail for a malformed snapshot, which the renderer also shows.
    }
  }, [activeCardKey, card?.card_id, study])

  const handleAnswer = useCallback(async (rating: Rating) => {
    if (
      study.isBusy
      || !card?.card_id
      || !activeCardKey
      || !revealed
      || !decision
    ) return
    const answeredCardId = card.card_id
    const answeredCardKey = activeCardKey
    const answerPromise = study.answer(
      answeredCardId,
      rating,
      decision,
      Math.max(0, performance.now() - startedAtRef.current),
    )
    setRevealedCardKey((current) => (
      current === answeredCardKey ? null : current
    ))
    setDecisionState((current) => (
      current?.cardKey === answeredCardKey ? null : current
    ))
    try {
      await answerPromise
    } catch {
      // Restore the answer side if local persistence failed so the learner can
      // retry without having to reveal the card and choose the rating again.
      setRevealedCardKey(answeredCardKey)
      setDecisionState({ cardKey: answeredCardKey, value: decision })
    }
  }, [activeCardKey, card?.card_id, decision, revealed, study])

  const handleCommit = useCallback(() => {
    void study.commit().catch(() => {})
  }, [study])

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

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const activeTag = (document.activeElement?.tagName || '').toLowerCase()
      if (activeTag === 'input' || activeTag === 'textarea') return

      if (event.code === 'Space' || event.code === 'Enter') {
        event.preventDefault()
        if (!card?.card_id) return
        if (!revealed) handleReveal()
        else void handleAnswer('good')
      } else if (event.key === '1' && revealed) {
        event.preventDefault()
        void handleAnswer('again')
      } else if (event.key === '2' && revealed) {
        event.preventDefault()
        void handleAnswer('hard')
      } else if (event.key === '3' && revealed) {
        event.preventDefault()
        void handleAnswer('good')
      } else if (event.key === '4' && revealed) {
        event.preventDefault()
        void handleAnswer('easy')
      } else if (event.key === 'f' || event.key === 'F') {
        event.preventDefault()
        handleToggleFullscreen()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    card?.card_id,
    handleAnswer,
    handleReveal,
    handleToggleFullscreen,
    revealed,
  ])

  if (!deckIdRaw) {
    return (
      <div className="h-screen h-[100dvh] w-full flex flex-col items-center justify-center p-6 text-center space-y-4">
        <h2 className="text-2xl font-bold text-foreground">Phiên học</h2>
        <p className="text-muted-foreground max-w-sm">
          Phiên học cần một deck cụ thể. Chọn deck từ dashboard để bắt đầu.
        </p>
        <Button asChild>
          <Link to="/dashboard">Về dashboard</Link>
        </Button>
      </div>
    )
  }

  if (study.isLoading) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center">
        <PageLoading label="Đang tải snapshot phiên học…" />
      </div>
    )
  }

  if (study.error && !study.session) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center p-6">
        <PageError error={study.error} />
      </div>
    )
  }

  const pendingCommit = study.session?.status === 'pending_commit'
  const blockingCommit = pendingCommit
    && (
      !isBackgroundRolloverCommit(study.session)
      || Boolean(study.error)
    )
  const counts = study.view?.counts ?? { new: 0, learning: 0, due: 0 }

  if (study.receipt) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center p-4 sm:p-6 bg-background text-foreground overflow-y-auto">
        <StudyCompletionCard
          deckName={deckName}
          deckId={deckIdRaw}
          session={study.session}
          receipt={study.receipt}
          counts={counts}
          sessionState={study.view?.session_state}
          nextDueAtMs={study.view?.next_due_at_ms}
          isBusy={study.isBusy}
          onCommit={handleCommit}
        />
      </div>
    )
  }

  return (
    <div className="study-page h-screen h-[100dvh] max-h-screen max-h-[100dvh] w-full flex flex-col m-0 p-0 pb-[calc(5rem+env(safe-area-inset-bottom,0px))] overflow-hidden bg-background text-foreground">
      {!isFullscreen ? (
        <div className="px-3 pt-2 shrink-0">
          <StudyHeaderToolbar
            deckName={deckName}
            deckId={deckIdRaw}
            cardId={card?.card_id}
          />
          <div className="px-2 py-1 text-xs text-muted-foreground">
            {study.session?.events.length || 0} trả lời chưa đồng bộ
          </div>
        </div>
      ) : null}

      {study.error ? (
        <div className="px-4 py-1 shrink-0">
          <PageError error={study.error} />
        </div>
      ) : null}

      {card && template && content && !blockingCommit ? (
        <div className="study-card-shell flex-1 flex flex-col w-full h-full min-h-0 min-w-0 overflow-hidden relative">
          <StudyCardRendererFrame
            cardId={card.card_id}
            noteId={card.note_id}
            revealed={revealed}
            template={template}
            content={content}
            scopeId={deckIdRaw}
          />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 overflow-y-auto min-h-0">
          <StudyCompletionCard
            deckName={deckName}
            deckId={deckIdRaw}
            session={study.session}
            receipt={study.receipt}
            counts={counts}
            sessionState={study.view?.session_state}
            nextDueAtMs={study.view?.next_due_at_ms}
            isBusy={study.isBusy}
            onCommit={handleCommit}
          />
        </div>
      )}

      {card && template && content && !blockingCommit ? (
        <StudyBottomBar
          cardId={card.card_id}
          revealed={revealed}
          canEdit={false}
          newCount={counts.new}
          learnCount={counts.learning}
          dueCount={counts.due}
          intervalsPreview={decision?.previews}
          isFullscreen={isFullscreen}
          submitting={study.isBusy}
          onReveal={handleReveal}
          onAnswer={(rating) => {
            void handleAnswer(rating)
          }}
          onEdit={() => {}}
          onToggleFullscreen={handleToggleFullscreen}
        />
      ) : null}
    </div>
  )
}
