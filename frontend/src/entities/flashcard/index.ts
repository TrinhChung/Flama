/** Public UI entry. Headless updates and rendering have separate entry points. */
export { CardRendererFrame } from './ui/CardRendererFrame'
export { CardDisplay } from './ui/CardDisplay'
export { CardPreviewPanel } from './ui/CardPreviewPanel'
export type { CardPreviewPanelProps, CardPreviewTemplateOption } from './ui/CardPreviewPanel'
export { CardSideToggle } from './ui/CardSideToggle'
export type { CardSide, CardSideToggleProps } from './ui/CardSideToggle'
export { MediaFieldPreview, resolveDisplayUrl } from './ui/MediaFieldPreview'
export type { MediaFieldPreviewProps } from './ui/MediaFieldPreview'
export { ArrayFieldInput } from './ui/ArrayFieldInput'
export type { ArrayFieldInputProps, ArrayViewMode } from './ui/ArrayFieldInput'
export { NoteFieldEditor } from './ui/NoteFieldEditor'
export { prefersMultilineEditor } from './lib/noteFieldLayout'
export { NOTE_TAG_MAX_COUNT, NOTE_TAG_MAX_LENGTH, tagDedupeKey } from './lib/noteTags'
export type { NoteFieldEditorDensity, NoteFieldEditorField, NoteFieldEditorProps } from './ui/NoteFieldEditor'
export type {
  CardRendererFrameProps,
  CardDisplayProps,
  CardRendererSlots,
  CardRendererSlotContext,
  SlotRenderer,
  FieldDef,
  CardMediaArtifact,
  CardRenderTemplate,
  CardRenderContent,
  CardRenderPayload,
  RendererSidePayload,
} from './model/types'
