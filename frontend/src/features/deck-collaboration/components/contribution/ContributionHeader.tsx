import { ContributionMetaCard } from './ContributionMetaCard'
import { ContributionSendCard } from './ContributionSendCard'
import type { DeckChangeRequest } from '../../types'

export type ContributionHeaderProps = {
  title: string
  onTitleChange: (value: string) => void
  description: string
  onDescriptionChange: (value: string) => void
  activeRequest: DeckChangeRequest | null | undefined
  totalNotes?: number
  selectedNotes?: number
  hasSelection?: boolean
  hasLocalChanges: boolean
  isPendingReview: boolean
  isBusy: boolean
  isSending: boolean
  canSend: boolean
  onSend: () => void
}

export function ContributionHeader({
  title,
  onTitleChange,
  description,
  onDescriptionChange,
  activeRequest,
  totalNotes,
  selectedNotes,
  hasSelection = true,
  hasLocalChanges,
  isPendingReview,
  isBusy,
  isSending,
  canSend,
  onSend,
}: ContributionHeaderProps) {
  return (
    <div className="grid items-stretch gap-4 md:grid-cols-[minmax(0,1fr)_21rem]">
      <ContributionMetaCard
        title={title}
        onTitleChange={onTitleChange}
        description={description}
        onDescriptionChange={onDescriptionChange}
        totalNotes={totalNotes}
        isPendingReview={isPendingReview}
        isBusy={isBusy}
      />

      <ContributionSendCard
        activeRequest={activeRequest}
        totalNotes={totalNotes}
        selectedNotes={selectedNotes}
        hasSelection={hasSelection}
        hasLocalChanges={hasLocalChanges}
        isPendingReview={isPendingReview}
        isBusy={isBusy}
        isSending={isSending}
        canSend={canSend}
        onSend={onSend}
      />
    </div>
  )
}
