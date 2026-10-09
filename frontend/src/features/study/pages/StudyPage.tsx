import '@/shared/config/i18n'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useImmersiveLayout } from '@/shared/hooks/useImmersiveLayout'
import { StudyHeaderToolbar } from '../components/StudyHeaderToolbar'
import { StudyCardRendererFrame } from '../components/StudyCardRendererFrame'
import { StudyBottomBar } from '../components/StudyBottomBar'
import { StudyCompletionCard } from '../components/StudyCompletionCard'
import { StudyCompositionPickerView } from '../components/StudyCompositionPickerView'
import { StudyTemplatePreparation } from '../components/StudyTemplatePreparation'
import { StudySessionConflict } from '../components/StudySessionConflict'
import { StudyWaitingCard } from '../components/StudyWaitingCard'
import { StudyScopeErrorCard } from '../components/StudyScopeErrorCard'
import { StudyQuickEditDialog } from '../components/StudyQuickEditDialog'
import { StudyExitConfirmDialog } from '../components/StudyExitConfirmDialog'
import { useStudySession } from '../hooks/useStudySession'
import { useStudyKeyboardShortcuts } from '../hooks/useStudyKeyboardShortcuts'
import { useStudyNavigationBlocker } from '../hooks/useStudyNavigationBlocker'
import { isBackgroundRolloverCommit } from '../session/studySessionEngine'
import type { SchedulerDecision } from '../scheduler/types'
import {
  reviewActionToLegacyRating,
  type ReviewAction,
} from '../interactions/reviewInteraction'

export function StudyPage() {
  const { t } = useTranslation('study')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const deckIdRaw = searchParams.get('deck_id')
  const study = useStudySession(deckIdRaw)
  useImmersiveLayout(!study.awaitingCompositionSelection)

  const [revealedCardKey, setRevealedCardKey] = useState<string | null>(null)
  const [decisionState, setDecisionState] = useState<{
    cardKey: string
    value: SchedulerDecision
  } | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isQuickEditOpen, setIsQuickEditOpen] = useState(false)
  const startedAtRef = useRef(performance.now())

  const {
    blocker,
    uncommittedCount,
    isExiting,
    handleSaveAndExit,
    handleDiscardAndExit,
    handleContinueStudy,
  } = useStudyNavigationBlocker({
    session: study.session,
    commit: study.commit,
  })

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
    || study.scopeName
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

  const handleReviewAction = useCallback(async (action: ReviewAction) => {
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
      reviewActionToLegacyRating(action),
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
    const isComplete = study.view?.session_state === 'complete_today'
    void study.commit({ reason: isComplete ? 'auto_finish' : 'manual_exit' }).catch(() => {})
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

  useStudyKeyboardShortcuts({
    cardId: card?.card_id,
    revealed,
    isQuickEditOpen,
    leaseConflict: Boolean(study.leaseConflict),
    hasReceipt: Boolean(study.receipt),
    onReveal: handleReveal,
    onReviewAction: handleReviewAction,
    onUndo: handleUndo,
    onOpenEdit: handleOpenEdit,
    onToggleFullscreen: handleToggleFullscreen,
  })

  if (!deckIdRaw) {
    return (
      <div className="h-screen h-[100dvh] w-full flex flex-col items-center justify-center p-6 text-center space-y-4">
        <h2 className="text-2xl font-bold text-foreground">{t('page.session_title')}</h2>
        <p className="text-muted-foreground max-w-sm">
          {t('page.deck_required')}
        </p>
        <Button asChild>
          <Link to="/dashboard">{t('page.back_to_dashboard')}</Link>
        </Button>
      </div>
    )
  }

  if (study.isLoading) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center">
        <PageLoading label={t('page.creating_session')} />
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

  if (study.awaitingCompositionSelection) {
    if (study.templatePreparation?.availability) {
      return <StudyTemplatePreparation preparation={study.templatePreparation} deckName={study.scopeName} error={study.error}
        disabled={study.isBusy} onStart={() => { void study.startPreparedSession() }} />
    }
    return (
      <StudyCompositionPickerView
        deckName={deckName}
        error={study.error}
        compositionGroups={study.compositionGroups}
        selectedCompositionId={study.selectedCompositionId}
        onSelectComposition={(compositionId) => { void study.selectComposition(compositionId) }}
        disabled={study.isBusy}
      />
    )
  }

  if (study.error && !study.session) {
    return (
      <div className="h-screen h-[100dvh] w-full flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-background text-foreground">
        <StudyScopeErrorCard
          error={study.error}
          deckName={deckName}
          deckId={deckIdRaw}
          onRetry={() => { void study.reloadSession(true) }}
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
  const isLeaving = isExiting || blocker.state === 'proceeding'

  // A final receipt closes this lease even when the deck still has due cards
  // (manual/page exit, including an empty final batch after rollover). Queue
  // exhaustion is not a prerequisite for acknowledging a completed session.
  if (study.receipt && !isLeaving) {
    return (
      <div className="min-h-[100dvh] w-full flex flex-col items-center justify-start sm:justify-center p-3 sm:p-6 bg-background text-foreground overflow-y-auto pb-[calc(1.5rem+env(safe-area-inset-bottom,0px))]">
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
            onReload={() => { void study.reloadSession() }}
            newCount={counts.new}
            learnCount={counts.learning}
            dueCount={counts.due}
          />
          {uncommittedCount > 0 ? (
            <div className="px-1 py-0.5 text-[11px] text-muted-foreground">
              {t('page.uncommitted_events', { count: uncommittedCount })}
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
          <PageLoading label={t('page.syncing_session')} />
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
            error={new Error(t('page.incomplete_card_data'))}
          />
        </div>
      ) : isLeaving ? (
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6">
          <PageLoading label={t('page.saving_progress_redirecting')} />
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-start sm:justify-center p-3 sm:p-6 overflow-y-auto min-h-0 pb-[calc(1.5rem+env(safe-area-inset-bottom,0px))]">
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
          onReviewAction={(action) => {
            void handleReviewAction(action)
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
