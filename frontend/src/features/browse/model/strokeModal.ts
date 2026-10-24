import type { useBrowseState } from '../hooks/useBrowseState'

export interface BrowseStrokeModalProps {
  browse?: ReturnType<typeof useBrowseState>
  isOpen: boolean
  onClose: () => void
  mode?: 'single' | 'batch'
  cardId?: string | null
  fields?: Array<{ name: string; field_type?: string }>
  fieldValues?: Record<string, unknown>
  deckName?: string | null
  onApply?: (targetField: string, value: string) => void
}
