import { describe, expect, it } from "vitest"
import * as SharedUI from "./index"

describe("Shared UI Public API Barrel", () => {
  it("exports all 8 standardized UI primitives without missing members", () => {
    // 1. SearchInput
    expect(SharedUI.SearchInput).toBeDefined()
    expect(SharedUI.searchInputVariants).toBeDefined()
    expect(SharedUI.searchIconVariants).toBeDefined()

    // 2. ConfirmDialog
    expect(SharedUI.ConfirmDialog).toBeDefined()
    expect(SharedUI.confirmDialogVariants).toBeDefined()

    // 3. StatusPill
    expect(SharedUI.StatusPill).toBeDefined()
    expect(SharedUI.statusPillVariants).toBeDefined()

    // 4. CodeSnippetBox
    expect(SharedUI.CodeSnippetBox).toBeDefined()
    expect(SharedUI.codeSnippetVariants).toBeDefined()

    // 5. FilterPillGroup
    expect(SharedUI.FilterPillGroup).toBeDefined()
    expect(SharedUI.filterPillGroupVariants).toBeDefined()
    expect(SharedUI.filterPillItemVariants).toBeDefined()
    expect(SharedUI.filterPillBadgeVariants).toBeDefined()

    // 6. ImageUploadDropzone
    expect(SharedUI.ImageUploadDropzone).toBeDefined()
    expect(SharedUI.dropzoneVariants).toBeDefined()

    // 7. SplitPane
    expect(SharedUI.SplitPane).toBeDefined()
    expect(SharedUI.splitPaneHandleVariants).toBeDefined()

    // 8. CardFieldsForm
    expect(SharedUI.CardFieldsForm).toBeDefined()
    expect(SharedUI.cardFieldLabelVariants).toBeDefined()
    expect(SharedUI.cardFieldInputVariants).toBeDefined()
  })
})
