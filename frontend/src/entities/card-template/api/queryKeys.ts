export const cardTemplateQueryKeys = {
  noteTypeTemplates: (noteTypeId: string) => ['card-template', 'note-type-templates', noteTypeId] as const,
  deckCardTypes: (deckId: number | string) => ['card-template', 'deck-card-types', String(deckId)] as const,
  templateVersions: (templateId: string) => ['card-template', 'versions', templateId] as const,
  templateVersion: (templateId: string, versionId: string) =>
    ['card-template', 'versions', templateId, versionId] as const,
}
