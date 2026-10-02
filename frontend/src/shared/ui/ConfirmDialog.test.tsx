// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { ConfirmDialog } from "./ConfirmDialog"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("ConfirmDialog Primitive", () => {
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
  })

  it("renders title, description and handles confirm & cancel in controlled mode", async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    const onOpenChange = vi.fn()

    await act(async () => {
      root?.render(
        <ConfirmDialog
          open={true}
          onOpenChange={onOpenChange}
          title="Xóa bộ thẻ?"
          description="Hành động này không thể hoàn tác."
          confirmText="Xóa vĩnh viễn"
          cancelText="Giữ lại"
          variant="destructive"
          onConfirm={onConfirm}
          onCancel={onCancel}
        />
      )
    })

    expect(document.body.textContent).toContain("Xóa bộ thẻ?")
    expect(document.body.textContent).toContain("Hành động này không thể hoàn tác.")

    const confirmBtn = Array.from(document.body.querySelectorAll("button")).find(
      (b) => b.textContent?.includes("Xóa vĩnh viễn")
    )
    expect(confirmBtn).toBeDefined()

    await act(async () => {
      confirmBtn?.click()
    })
    expect(onConfirm).toHaveBeenCalledOnce()

    const cancelBtn = Array.from(document.body.querySelectorAll("button")).find(
      (b) => b.textContent?.includes("Giữ lại")
    )
    expect(cancelBtn).toBeDefined()

    await act(async () => {
      cancelBtn?.click()
    })
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it("locks action buttons and shows spinner when isLoading is true", async () => {
    const onConfirm = vi.fn()

    await act(async () => {
      root?.render(
        <ConfirmDialog
          open={true}
          title="Đang đồng bộ dữ liệu"
          isLoading={true}
          onConfirm={onConfirm}
        />
      )
    })

    const buttons = Array.from(document.body.querySelectorAll("button"))
    buttons.forEach((btn) => {
      expect(btn.disabled).toBe(true)
    })
    expect(document.body.querySelector(".animate-spin")).toBeDefined()
  })

  it("renders uncontrolled with trigger button and opens on trigger click", async () => {
    const onConfirm = vi.fn()

    await act(async () => {
      root?.render(
        <ConfirmDialog
          trigger={<button id="trigger-btn">Open Dialog</button>}
          title="Xác nhận tiếp tục"
          description="Bạn có muốn tiếp tục?"
          onConfirm={onConfirm}
        />
      )
    })

    const triggerBtn = document.getElementById("trigger-btn") as HTMLButtonElement
    expect(triggerBtn).toBeDefined()

    // Click trigger to open modal
    await act(async () => {
      triggerBtn.click()
    })

    expect(document.body.textContent).toContain("Xác nhận tiếp tục")
    expect(document.body.textContent).toContain("Bạn có muốn tiếp tục?")
  })
})
