import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useBlocker, useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { StudyHeaderToolbar } from '../components/StudyHeaderToolbar'
import { StudyCardRendererFrame } from '../components/StudyCardRendererFrame'
import { StudyBottomBar } from '../components/StudyBottomBar'
import { StudyCompletionCard } from '../components/StudyCompletionCard'
import { StudySessionConflict } from '../components/StudySessionConflict'
import { StudyWaitingCard } from '../components/StudyWaitingCard'
import { StudyScopeErrorCard } from '../components/StudyScopeErrorCard'
import { StudyQuickEditDialog } from '../components/StudyQuickEditDialog'
import { StudyExitConfirmDialog } from '../components/StudyExitConfirmDialog'
import { useStudySession } from '../hooks/useStudySession'
import { isBackgroundRolloverCommit } from '../session/studySessionEngine'
import type { Rating } from '../types'
import type { SchedulerDecision } from '../scheduler/types'
import { resolveReviewAction, type ReviewRating } from '../interactions/reviewInteraction'

export function StudyPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const deckIdRaw = searchParams.get('deck_id')
  const [selectedCompositionId, setSelectedCompositionId] = useState<string | null>(null)
  const study = useStudySession(deckIdRaw, selectedCompositionId)

  const [revealedCardKey, setRevealedCardKey] = useState<string | null>(null)
  const [decisionState, setDecisionState] = useState<{
    cardKey: string
    value: SchedulerDecision
  } | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isQuickEditOpen, setIsQuickEditOpen] = useState(false)
  const startedAtRef = useRef(performance.now())

  const uncommittedCount = study.session?.events?.length ?? 0
  const isSessionActive = study.session?.status === 'active'
  const hasUncommittedWork = Boolean(isSessionActive && uncommittedCount > 0)
  const [isExiting, setIsExiting] = useState(false)

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      hasUncommittedWork && currentLocation.pathname !== nextLocation.pathname
  )

  useEffect(() => {
    if (!hasUncommittedWork) return
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
    }
  }, [hasUncommittedWork])

  const handleSaveAndExit = useCallback(async () => {
    if (!study.session) {
      blocker.proceed?.()
      return
    }
    setIsExiting(true)
    try {
      await study.commit({ reason: 'manual_exit' })
      blocker.reset?.()
    } catch (err) {
      console.error('Failed to commit study session before exit:', err)
      blocker.proceed?.()
    } finally {
      setIsExiting(false)
    }
  }, [blocker, study])

  const handleDiscardAndExit = useCallback(() => {
    blocker.proceed?.()
  }, [blocker])

  const handleContinueStudy = useCallback(() => {
    blocker.reset?.()
  }, [blocker])

  const compositionsList = useMemo(() => {
    const comps = study.session?.snapshot.compositions
    return comps ? Object.values(comps) : []
  }, [study.session?.snapshot.compositions])

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

  const handleOpenEdit = useCallback(() => {
    if (card?.card_id && card?.can_edit_card !== false && !study.isBusy) {
      setIsQuickEditOpen(true)
    }
  }, [card?.card_id, card?.can_edit_card, study.isBusy])

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

  const handleUndo = useCallback(async () => {
    if (study.isBusy || !study.canUndo) return
    try {
      const undoneCardId = await study.undo()
      if (undoneCardId && study.session?.snapshot.session_id) {
        const restoredCardKey = `${study.session.snapshot.session_id}:${undoneCardId}`
        setDecisionState({
          cardKey: restoredCardKey,
          value: study.prepareDecision(undoneCardId),
        })
        setRevealedCardKey(restoredCardKey)
      }
    } catch {
      // Any error will be exposed via study.error
    }
  }, [study])

  const handleCommit = useCallback(() => {
    void study.commit({ reason: 'manual_exit' }).catch(() => {})
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
    if (study.leaseConflict || isQuickEditOpen) return

    const handleKeyDown = (event: KeyboardEvent) => {
      const activeEl = document.activeElement
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (
        event.defaultPrevented
        || event.isComposing
        || activeTag === 'input'
        || activeTag === 'textarea'
        || activeTag === 'select'
        || (activeEl as HTMLElement)?.isContentEditable
      ) return

      const code = event.code
      const key = event.key

      const isUndo = (
        (event.ctrlKey || event.metaKey) && (key === 'z' || key === 'Z' || code === 'KeyZ')
      ) || (
        !event.ctrlKey && !event.metaKey && !event.altKey && (key === 'z' || key === 'Z' || code === 'KeyZ')
      )

      if (isUndo) {
        event.preventDefault()
        void handleUndo()
        return
      }

      if (
        event.altKey
        || event.ctrlKey
        || event.metaKey
        || activeTag === 'button'
        || activeTag === 'a'
      ) return

      const isEditKey = key === 'e' || key === 'E' || code === 'KeyE'
      if (isEditKey) {
        event.preventDefault()
        handleOpenEdit()
        return
      }

      const isSpaceOrEnter = code === 'Space' || key === ' ' || key === 'Spacebar' || code === 'Enter' || key === 'Enter'
      const isFullscreenKey = key === 'f' || key === 'F' || code === 'KeyF'

      if (isSpaceOrEnter) {
        event.preventDefault()
        if (!card?.card_id) return
        if (!revealed) handleReveal()
        else void handleAnswer('good')
      } else if (revealed) {
        const ratingByKey: Record<string, ReviewRating> = {
          '1': 'again', '2': 'hard', '3': 'good', '4': 'easy',
        }
        const codeMap: Record<string, string> = {
          Digit1: '1', Numpad1: '1',
          Digit2: '2', Numpad2: '2',
          Digit3: '3', Numpad3: '3',
          Digit4: '4', Numpad4: '4',
        }
        const mappedKey = codeMap[code] ?? key
        const rating = ratingByKey[mappedKey]
        if (rating) {
          event.preventDefault()
          resolveReviewAction(rating) // validate action identity
          void handleAnswer(rating)
        } else if (isFullscreenKey) {
          event.preventDefault()
          handleToggleFullscreen()
        }
      } else if (isFullscreenKey) {
        event.preventDefault()
        handleToggleFullscreen()
      }
    }

    const handleFocusBack = () => {
      // Blur buttons or input elements if returning to screen
      const activeEl = document.activeElement as HTMLElement | null
      const activeTag = (activeEl?.tagName || '').toLowerCase()
      if (activeTag === 'button' || activeTag === 'a') {
        activeEl?.blur()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('focus', handleFocusBack)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('focus', handleFocusBack)
    }
  }, [
    card?.card_id,
    handleAnswer,
    handleOpenEdit,
    handleReveal,
    handleToggleFullscreen,
    handleUndo,
    isQuickEditOpen,
    revealed,
    study.leaseConflict,
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
        <PageLoading label="Đang tạo phiên học…" />
      </div>
    )
  }

  if (study.leaseConflict) {
    return (
      <div className="flex h-screen h-[100dvh] w-full items-center justify-center overflow-y-auto bg-background p-4 text-foreground sm:p-6">
        <StudySessionConflict
          deckName={deckName}
          takeoverState={study.takeoverState}
          onTakeover={study.requestTakeover}
          onForceTakeover={study.forceTakeover}
          onLeave={() => navigate('/dashboard', { replace: true })}
        />
      </div>
    )
  }

  if (study.error && !study.session) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-background text-foreground">
        <StudyScopeErrorCard
          error={study.error}
          deckName={deckName}
          deckId={deckIdRaw}
        />
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
          totalSessionStats={study.totalSessionStats}
          counts={counts}
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
            canEdit={Boolean(card?.card_id && card?.can_edit_card !== false)}
            onEdit={handleOpenEdit}
            onReload={study.reloadSession}
            newCount={counts.new}
            learnCount={counts.learning}
            dueCount={counts.due}
            compositions={compositionsList}
            selectedCompositionId={selectedCompositionId}
            onSelectComposition={setSelectedCompositionId}
          />
          {uncommittedCount > 0 ? (
            <div className="px-1 py-0.5 text-[11px] text-muted-foreground">
              {uncommittedCount} trả lời chưa đồng bộ
            </div>
          ) : null}
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
      ) : blockingCommit ? (
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
          <PageLoading label="Đang đồng bộ phiên học…" />
        </div>
      ) : study.view?.session_state === 'waiting' ? (
        <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 overflow-y-auto min-h-0">
          <StudyWaitingCard
            deckName={deckName}
            counts={counts}
            nowMs={study.view.now_ms}
            pendingLearningCount={study.view.pending_learning_count}
            nextEligibleAtMs={study.view.next_eligible_at_ms}
            nextDueAtMs={study.view.next_due_at_ms}
            isBusy={study.isBusy}
            onCommit={handleCommit}
          />
        </div>
      ) : study.view?.session_state === 'active' ? (
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
          <PageError
            error={new Error('Dữ liệu hiển thị thẻ không đầy đủ. Hãy tải lại phiên học.')}
          />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center p-4 sm:p-6 overflow-y-auto min-h-0">
          <StudyCompletionCard
            deckName={deckName}
            deckId={deckIdRaw}
            session={study.session}
            receipt={study.receipt}
            totalSessionStats={study.totalSessionStats}
            counts={counts}
            isBusy={study.isBusy}
            onCommit={handleCommit}
          />
        </div>
      )}

      {card && template && content && !blockingCommit ? (
        <StudyBottomBar
          cardId={card.card_id}
          revealed={revealed}
          canUndo={study.canUndo}
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
          onUndo={() => {
            void handleUndo()
          }}
          onToggleFullscreen={handleToggleFullscreen}
        />
      ) : null}

      <StudyQuickEditDialog
        open={isQuickEditOpen}
        onOpenChange={setIsQuickEditOpen}
        cardId={card?.card_id}
        noteId={card?.note_id}
        deckName={deckName}
        template={template}
        content={content}
        onCardUpdated={study.updateCardContent}
      />

      <StudyExitConfirmDialog
        open={blocker.state === 'blocked'}
        eventsCount={uncommittedCount}
        isCommitting={isExiting}
        onSaveAndExit={handleSaveAndExit}
        onContinueStudy={handleContinueStudy}
        onDiscardAndExit={handleDiscardAndExit}
      />
    </div>
  )
}
