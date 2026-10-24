import type { MappingField, TemplateApplication, TemplateLibraryDetail } from '@/entities/card-template'

export type AttachableNoteType = {
  id: string
  name: string
  field_defs: Array<MappingField & { position: number }>
  is_marketplace_install: boolean
}

export type ApplyTemplateWizardProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  template: TemplateLibraryDetail
  initialNoteTypeId?: string
  initialOccurrenceKey?: string
  onApplied?: (application: TemplateApplication) => void
}

export type ApplyTemplateFormProps = Omit<ApplyTemplateWizardProps, 'open'> & {
  onBack?: () => void
  onPendingChange?: (pending: boolean) => void
  submitLabel?: string
}
