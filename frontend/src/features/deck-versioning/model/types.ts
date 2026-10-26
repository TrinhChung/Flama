import type {
  DependencyStatusCode,
  NoteTypeDependency,
  TemplateDependency,
  DeckStructuralDependenciesResponse,
} from '@/entities/deck-version'

export type {
  DependencyStatusCode,
  NoteTypeDependency,
  TemplateDependency,
  DeckStructuralDependenciesResponse,
}

export interface DependencyStatusBadgeProps {
  status: DependencyStatusCode | string
  className?: string
  showIcon?: boolean
  size?: 'sm' | 'default'
  customLabel?: string
}

export interface DeckStructuralDependenciesCardProps {
  deckTitle: string
  currentVersionLabel?: string | null
  noteTypes: NoteTypeDependency[]
  isLoading?: boolean
  onNavigateToNoteType?: (noteTypeId: string) => void
  onNavigateToTemplate?: (templateId: string) => void
  className?: string
}
