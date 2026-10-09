import type { TemplateLibraryParams } from '../model/types'

export const cardTemplateQueryKeys = {
  noteTypeTemplates: (noteTypeId: string) => ['card-template', 'note-type-templates', noteTypeId] as const,
  deckCardTypes: (deckId: number | string) => ['card-template', 'deck-card-types', String(deckId)] as const,
  templateVersions: (templateId: string) => ['card-template', 'versions', templateId] as const,
  templateVersion: (templateId: string, versionId: string) =>
    ['card-template', 'versions', templateId, versionId] as const,
  library: (p: TemplateLibraryParams = {}) =>
    [
      'card-template',
      'library',
      p.q ?? '',
      p.group ?? 'all',
      p.category ?? '',
      p.include_archived ?? false,
    ] as const,
  libraryDetail: (id: string) => ['card-template', 'library-detail', id] as const,
  applications: (nt: string, includeRetired = false) =>
    ['card-template', 'applications', nt, includeRetired] as const,
  installTemplates: (id: string) => ['card-template', 'install-templates', id] as const,
  subscription: (id: string) => ['card-template', 'subscription', id] as const,
  releases: (id: string) => ['card-template', 'releases', id] as const,
  release: (id: string, rid: string) => ['card-template', 'releases', id, rid] as const,
  publication: (id: string) => ['card-template', 'publication', id] as const,
  studyTemplateInputs: (id: string | number) => ['card-template', 'study-inputs', String(id)] as const,
  studyTemplatePreset: (id: string | number) => ['card-template', 'study-preset', String(id)] as const,
}
