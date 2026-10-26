/**
 * Domain types for Deck Versioning, Structural Dependencies & Cascading Sync (Triad Architecture)
 * Layer: entities/deck-version (Layer 1 - FSD)
 *
 * Implements data contracts for:
 * - Level 1: Deck Release & Structural Dependencies (R1)
 * - Level 2: Note Type Schema Releases & Coherence Warnings (R2)
 * - Level 3: Card Template Presentations & Releases
 * - 1-Click Cascading Consumer Updates & SRS Progress Immutability (R4)
 */

export type DependencyStatusCode = 'synced' | 'update_available' | 'draft_changes'

export interface ReleaseRef {
  id: string
  version_label: string
  sequence_no?: number
  published_at?: string | null
}

export interface TemplateDependency {
  template_id: string
  template_name: string
  occurrence_key?: string
  pinned_release_id?: string | null
  pinned_version_label?: string | null
  latest_release_id?: string | null
  latest_version_label?: string | null
  status: DependencyStatusCode
  has_newer_release: boolean
  has_uncommitted_draft: boolean
  editor_url?: string
}

export interface NoteTypeDependency {
  note_type_id: string
  note_type_name: string
  note_count: number
  pinned_release_id?: string | null
  pinned_version_label?: string | null
  latest_release_id?: string | null
  latest_version_label?: string | null
  status: DependencyStatusCode
  has_draft_changes: boolean
  editor_url?: string
  templates: TemplateDependency[]
}

export interface DeckContentChangesSummary {
  has_unpublished_changes: boolean
  working_revision: number
  added_notes: number
  modified_notes: number
  removed_notes: number
  total_changed_properties?: number
}

export interface DeckStructuralDependenciesResponse {
  deck_item_id: string
  deck_title: string
  current_release?: ReleaseRef | null
  content_changes?: DeckContentChangesSummary
  note_types: NoteTypeDependency[]
  can_publish_content?: boolean
  blocking_reasons?: string[]
}

export type CoherenceWarningType = 'OUTDATED_PIN' | 'UNCOMMITTED_DRAFT' | 'UNMAPPED_FIELDS'

export interface TemplateCoherenceWarning {
  template_id: string
  template_name: string
  application_id?: string
  pinned_release?: string | null
  latest_release?: string | null
  warning_type: CoherenceWarningType
  message: string
  action_recommendation?: string
}

export interface NoteTypeDependencyCoherence {
  note_type_id: string
  name: string
  is_coherent: boolean
  current_release?: ReleaseRef | null
  suggested_version?: string | null
  warnings: TemplateCoherenceWarning[]
}

export interface CascadingSyncNoteTypeItem {
  id: string
  name: string
  version: string
  fields_added?: string[]
  fields_modified?: string[]
}

export interface CascadingSyncTemplateItem {
  id: string
  name: string
  from_version: string
  to_version: string
}

export interface CascadingSyncSummary {
  deck_id?: string
  deck_install_id?: string
  deck_title: string
  version_label: string
  from_version_label?: string
  cards_updated?: number
  cards_added?: number
  cards_modified?: number
  cards_removed?: number
  note_types_updated: CascadingSyncNoteTypeItem[]
  templates_updated: CascadingSyncTemplateItem[]
  progress_preserved_count: number
  retained_review_events?: number
  srs_safety_attestation?: string
}
