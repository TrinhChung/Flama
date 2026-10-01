// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ImageUploadDropzone } from "./ImageUploadDropzone"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("ImageUploadDropzone Primitive", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    if (root && container) {
      const activeRoot = root
      await act(async () => {
        activeRoot.unmount()
      })
      container.remove()
    }
    document.body.replaceChildren()
    container = null
    root = null
    vi.restoreAllMocks()
  })

  it("renders default dropzone with accessible button role and hidden input", async () => {
    const onFilesSelected = vi.fn()
    await act(async () => {
      root?.render(<ImageUploadDropzone onFilesSelected={onFilesSelected} />)
    })

    const dropzone = container?.querySelector('[role="button"]')
    expect(dropzone).not.toBeNull()

    const fileInput = container?.querySelector('input[type="file"]') as HTMLInputElement
    expect(fileInput).not.toBeNull()
    expect(fileInput.classList.contains("sr-only") || fileInput.classList.contains("hidden")).toBe(true)
  })

  it("handles dragover and dragleave visual feedback states", async () => {
    await act(async () => {
      root?.render(<ImageUploadDropzone onFilesSelected={vi.fn()} />)
    })

    const dropzone = container?.querySelector('[role="button"]') as HTMLElement
    expect(dropzone).not.toBeNull()

    // Trigger dragover
    await act(async () => {
      dropzone.dispatchEvent(new Event("dragover", { bubbles: true, cancelable: true }))
    })
    expect(dropzone.getAttribute("data-dragging")).toBe("true")

    // Trigger dragleave
    await act(async () => {
      dropzone.dispatchEvent(new Event("dragleave", { bubbles: true }))
    })
    expect(dropzone.getAttribute("data-dragging")).toBe("false")
  })

  it("processes dropped valid image files and triggers onFilesSelected", async () => {
    const onFilesSelected = vi.fn()
    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          onFilesSelected={onFilesSelected}
          compress={false}
        />
      )
    })

    const dropzone = container?.querySelector('[role="button"]') as HTMLElement
    const file = new File(["test-image-binary"], "photo.png", { type: "image/png" })

    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as any
    dropEvent.dataTransfer = { files: [file] }

    await act(async () => {
      dropzone.dispatchEvent(dropEvent)
    })

    expect(onFilesSelected).toHaveBeenCalledWith([file])
  })

  it("intercepts Ctrl+V paste event and extracts image", async () => {
    const onFilesSelected = vi.fn()
    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          onFilesSelected={onFilesSelected}
          enablePaste={true}
          compress={false}
        />
      )
    })

    const dropzone = container?.querySelector('[role="button"]') as HTMLElement
    const file = new File(["pasted-content"], "screenshot.png", { type: "image/png" })

    const pasteEvent = new Event("paste", { bubbles: true, cancelable: true }) as any
    pasteEvent.clipboardData = {
      items: [{ type: "image/png", getAsFile: () => file }],
      files: [file],
    }

    await act(async () => {
      dropzone.dispatchEvent(pasteEvent)
    })

    expect(onFilesSelected).toHaveBeenCalledWith([file])
  })

  it("validates file size limit and triggers onError when file is too large", async () => {
    const onFilesSelected = vi.fn()
    const onError = vi.fn()
    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          onFilesSelected={onFilesSelected}
          onError={onError}
          maxSizeBytes={1024} // 1 KB
          compress={false}
        />
      )
    })

    const dropzone = container?.querySelector('[role="button"]') as HTMLElement
    const largeFile = new File([new ArrayBuffer(2048)], "large.png", { type: "image/png" })

    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as any
    dropEvent.dataTransfer = { files: [largeFile] }

    await act(async () => {
      dropzone.dispatchEvent(dropEvent)
    })

    expect(onFilesSelected).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalled()
  })

  it("renders preview thumbnail and handles onRemovePreview", async () => {
    const onRemovePreview = vi.fn()
    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          onFilesSelected={vi.fn()}
          previewUrl="https://example.com/avatar.jpg"
          onRemovePreview={onRemovePreview}
        />
      )
    })

    const img = container?.querySelector("img")
    expect(img).not.toBeNull()
    expect(img?.src).toBe("https://example.com/avatar.jpg")

    const removeBtn = container?.querySelector('button[aria-label="Xóa ảnh"]') as HTMLButtonElement
    expect(removeBtn).not.toBeNull()

    await act(async () => {
      removeBtn.click()
    })
    expect(onRemovePreview).toHaveBeenCalledOnce()
  })

  it("displays progress indicator when isUploading is true", async () => {
    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          onFilesSelected={vi.fn()}
          isUploading={true}
          uploadProgress={65}
        />
      )
    })

    expect(container?.textContent).toContain("Đang tải lên...")
    const progress = container?.querySelector('[data-slot="progress"]')
    expect(progress).not.toBeNull()
  })

  it("rejects non-matching MIME types and calls onError", async () => {
    const onError = vi.fn()
    const onFilesSelected = vi.fn()

    await act(async () => {
      root?.render(
        <ImageUploadDropzone
          accept={["image/png"]}
          onFilesSelected={onFilesSelected}
          onError={onError}
          compress={false}
        />
      )
    })

    const dropzone = container?.querySelector('[role="button"]') as HTMLElement
    const invalidFile = new File(["pdf"], "doc.pdf", { type: "application/pdf" })

    const dropEvent = new Event("drop", { bubbles: true, cancelable: true }) as any
    dropEvent.dataTransfer = { files: [invalidFile] }

    await act(async () => {
      dropzone.dispatchEvent(dropEvent)
    })

    expect(onFilesSelected).not.toHaveBeenCalled()
    expect(onError).toHaveBeenCalledWith("Định dạng tệp không được hỗ trợ.")
  })
})
