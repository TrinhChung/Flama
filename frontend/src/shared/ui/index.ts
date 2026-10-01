/**
 * Flama Shared UI Primitives (Layer 0 - FSD v2.1)
 * Standardized, accessible, CVA-governed UI primitives built with TailwindCSS v4 OKLCH tokens.
 *
 * Public API Contract: All consumers must import from '@/shared/ui'.
 * Deep imports into internal files are strictly forbidden.
 */

// ---------------------------------------------------------------------------
// 1. SearchInput (Interactive Primitive 1)
// ---------------------------------------------------------------------------
export { SearchInput, searchInputVariants, searchIconVariants } from "./SearchInput"
export type { SearchInputProps } from "./SearchInput"

// ---------------------------------------------------------------------------
// 2. ConfirmDialog (Interactive Primitive 2)
// ---------------------------------------------------------------------------
export { ConfirmDialog, confirmDialogVariants } from "./ConfirmDialog"
export type { ConfirmDialogProps } from "./ConfirmDialog"

// ---------------------------------------------------------------------------
// 3. StatusPill (Interactive Primitive 3)
// ---------------------------------------------------------------------------
export { StatusPill, statusPillVariants } from "./StatusPill"
export type { StatusPillProps, StatusPillVariant } from "./StatusPill"

// ---------------------------------------------------------------------------
// 4. CodeSnippetBox (Interactive Primitive 4)
// ---------------------------------------------------------------------------
export { CodeSnippetBox, codeSnippetVariants } from "./CodeSnippetBox"
export type { CodeSnippetBoxProps } from "./CodeSnippetBox"

// ---------------------------------------------------------------------------
// 5. FilterPillGroup (Layout Primitive 5)
// ---------------------------------------------------------------------------
export {
  FilterPillGroup,
  filterPillGroupVariants,
  filterPillItemVariants,
  filterPillBadgeVariants,
} from "./FilterPillGroup"
export type {
  FilterPillOption,
  FilterPillGroupProps,
  FilterPillGroupSingleProps,
  FilterPillGroupMultiProps,
} from "./FilterPillGroup"

// ---------------------------------------------------------------------------
// 6. ImageUploadDropzone (Media Primitive 6)
// ---------------------------------------------------------------------------
export { ImageUploadDropzone, dropzoneVariants } from "./ImageUploadDropzone"
export type { ImageUploadDropzoneProps } from "./ImageUploadDropzone"

// ---------------------------------------------------------------------------
// 7. SplitPane (Layout Primitive 7)
// ---------------------------------------------------------------------------
export { SplitPane, splitPaneHandleVariants } from "./SplitPane"
export type { SplitPaneProps } from "./SplitPane"

// ---------------------------------------------------------------------------
// 8. CardFieldsForm (Domain UI Primitive 8)
// ---------------------------------------------------------------------------
export {
  CardFieldsForm,
  cardFieldLabelVariants,
  cardFieldInputVariants,
} from "./CardFieldsForm"
export type {
  CardFieldDef,
  CardFieldsFormProps,
} from "./CardFieldsForm"
