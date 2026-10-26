import type {
  CascadingSyncSummary,
  CascadingSyncNoteTypeItem,
  CascadingSyncTemplateItem,
} from '@/entities/deck-version'

export type {
  CascadingSyncSummary,
  CascadingSyncNoteTypeItem,
  CascadingSyncTemplateItem,
}

export interface CascadingSyncSummaryModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  summary: CascadingSyncSummary | null
  onStartStudy?: () => void
  onClose?: () => void
}
