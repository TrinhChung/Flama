import { AmbientBackground } from '@/components/ambient-background'
import { Page } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { DeckAccessKeysManager } from '../components/keys/DeckAccessKeysManager'
import { RedeemDeckKeyModal } from '../components/keys/RedeemDeckKeyModal'
import { DeckDetailHeader } from '../components/deck-detail/DeckDetailHeader'
import { DeckDetailOwnerBar } from '../components/deck-detail/DeckDetailOwnerBar'
import { DeckCardPreviewSection } from '../components/deck-detail/DeckCardPreviewSection'
import { DeckLessonsSection } from '../components/deck-detail/DeckLessonsSection'
import { DeckReviewsSection } from '../components/deck-detail/DeckReviewsSection'
import { DeckRelatedSection } from '../components/deck-detail/DeckRelatedSection'

import { useSharedDeckDetail } from '../hooks/useSharedDeckDetail'

export function SharedDeckDetailView() {
  const { id, t, urlCode, isRedeemModalOpen, setIsRedeemModalOpen, showKeyManager, setShowKeyManager, activeSampleIndex, setActiveSampleIndex, selectedTemplateId, setSelectedTemplateId, previewSide, setPreviewSide, lessonSearch, setLessonSearch, ratingScore, setRatingScore, hoverScore, setHoverScore, ratingComment, setRatingComment, submitError, submitSuccess, deckQuery, deck, samples, currentSample, sourceNoteType, templates, displayLessons, autoPublishQuery, autoPublishMutation, previewQuery, installMutation, saveMutation, rateMutation, publishStatusMutation, handlePrevSample, handleNextSample } = useSharedDeckDetail()

  if (deckQuery.isLoading) {
    return (
      <Page>
        <PageLoading label={t('detail.loading', 'Đang tải thông tin bộ thẻ…')} />
      </Page>
    )
  }

  if (deckQuery.isError || !deck) {
    return (
      <Page>
        <PageError
          error={deckQuery.error || new Error(t('detail.error_load', 'Không thể tải thông tin bộ thẻ này.'))}
        />
      </Page>
    )
  }

  const effectiveStar = hoverScore ?? ratingScore
  const deckTitle = deck.title || t('card.no_title', 'Bộ thẻ không tên')
  const authorName =
    deck.author?.username ||
    deck.author_profile?.account_name ||
    deck.author_profile?.username ||
    t('card.community_author', 'Cộng đồng Flama')
  const tagsList = deck.display_tags || deck.tags || []

  return (
    <Page className="max-w-6xl mx-auto space-y-6 px-3 sm:px-6 py-4 sm:py-6">
      <AmbientBackground intensity="subtle" />

      {/* Main Hero Header Card */}
      <DeckDetailHeader
        id={id!}
        deck={deck}
        authorName={authorName}
        deckTitle={deckTitle}
        tagsList={tagsList}
        sampleLength={samples.length}
        onSave={() => saveMutation.mutate(deck.is_saved)}
        isSavePending={saveMutation.isPending}
        onInstall={() => installMutation.mutate()}
        isInstallPending={installMutation.isPending}
        onOpenRedeemModal={() => setIsRedeemModalOpen(true)}
        ownerBarNode={
          <DeckDetailOwnerBar
            id={id!}
            deckSourceDeckId={deck.source_deck_id}
            version={deck.version}
            publishStatus={deck.publish_status}
            showKeyManager={showKeyManager}
            setShowKeyManager={setShowKeyManager}
            onUpdatePublishStatus={(st) => publishStatusMutation.mutate(st)}
            isPublishStatusPending={publishStatusMutation.isPending}
            autoPublishData={autoPublishQuery.data}
            autoPublishMutation={autoPublishMutation}
          />
        }
      />

      {/* Creator Access Keys Management Section */}
      {deck.is_owner && showKeyManager && (
        <div className="animate-in fade-in slide-in-from-top-4 duration-300">
          <DeckAccessKeysManager deckItemId={id!} deckTitle={deck.title || ''} />
        </div>
      )}

      {/* Section 1: Interactive Sample & Live Previewer */}
      <DeckCardPreviewSection
        id={id!}
        sourceNoteType={sourceNoteType}
        templates={templates}
        selectedTemplateId={selectedTemplateId}
        setSelectedTemplateId={setSelectedTemplateId}
        previewSide={previewSide}
        setPreviewSide={setPreviewSide}
        samples={samples}
        activeSampleIndex={activeSampleIndex}
        setActiveSampleIndex={setActiveSampleIndex}
        handlePrevSample={handlePrevSample}
        handleNextSample={handleNextSample}
        currentSample={currentSample}
        previewQuery={previewQuery}
      />

      {/* Section 2: Deck Lessons & Word Counts Breakdown */}
      <DeckLessonsSection
        lessons={deck.lessons}
        lessonCount={deck.lesson_count}
        noteCount={deck.note_count}
        sampleLength={samples.length}
        lessonSearch={lessonSearch}
        setLessonSearch={setLessonSearch}
        displayLessons={displayLessons}
      />

      {/* Section 3: Community Reviews */}
      <DeckReviewsSection
        canRate={deck.can_rate}
        ratingScore={ratingScore}
        setRatingScore={setRatingScore}
        hoverScore={hoverScore}
        setHoverScore={setHoverScore}
        effectiveStar={effectiveStar}
        ratingComment={ratingComment}
        setRatingComment={setRatingComment}
        submitError={submitError}
        submitSuccess={submitSuccess}
        rateMutation={rateMutation}
        myReview={deck.my_review}
        recentReviews={deck.recent_reviews}
      />

      {/* Section 4: Related Items */}
      <DeckRelatedSection relatedItems={deck.related_items} />

      {/* Redeem Deck Key Modal */}
      <RedeemDeckKeyModal
        isOpen={isRedeemModalOpen}
        onClose={() => setIsRedeemModalOpen(false)}
        initialKey={urlCode}
        deckItemId={id}
      />
    </Page>
  )
}
