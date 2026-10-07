export type {
  CardTemplateItem,
  CardTemplateWithNoteCount,
  NoteTypeTemplatesResponse,
  CardTypeContextKind,
  DeckCardType,
  DeckCardTypeGroup,
  DeckCardTypesResponse,
  TemplateVersionOrigin,
  TemplateVersionSummary,
  TemplateVersionDetail,
  TemplateVersionList,
} from './model/types'
export {
  fetchNoteTypeTemplates,
  fetchDeckCardTypes,
  createNoteTypeTemplate,
  renameNoteTypeTemplate,
  deleteNoteTypeTemplate,
  fetchTemplateVersions,
  fetchTemplateVersion,
  restoreTemplateVersion,
} from './api/cardTemplateApi'
export { cardTemplateQueryKeys } from './api/queryKeys'
export { TemplateCodeEditor } from './ui/TemplateCodeEditor'
export type { TemplateCodeEditorProps, TemplateEditorTab } from './ui/TemplateCodeEditor'
export { diffLines, summarizeDiff } from './lib/lineDiff'
export type { DiffLine, DiffLineKind } from './lib/lineDiff'
export { TemplateDiffView } from './ui/TemplateDiffView'
export type { TemplateDiffViewProps, TemplateSources } from './ui/TemplateDiffView'
