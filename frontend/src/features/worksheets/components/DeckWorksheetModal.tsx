import type { WizardStepId } from '../config/wizardSteps'
import { WorksheetStudio } from './WorksheetStudio'
import { WorksheetStudioDialog } from './WorksheetStudioDialog'

export interface DeckWorksheetModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  deckId?: number | null
  deckName?: string
  initialCardIds?: (string | number)[]
  initialStep?: WizardStepId
}

/** Eagerly bundled studio modal; app code should prefer `LazyDeckWorksheetModal`. */
export function DeckWorksheetModal(props: DeckWorksheetModalProps) {
  return (
    <WorksheetStudioDialog open={props.open} onOpenChange={props.onOpenChange}>
      <WorksheetStudio {...props} />
    </WorksheetStudioDialog>
  )
}
