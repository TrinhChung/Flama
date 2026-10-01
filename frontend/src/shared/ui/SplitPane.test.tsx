// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SplitPane } from "./SplitPane"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("SplitPane Primitive", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    localStorage.clear()
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

  it("renders primary and secondary panes with draggable separator handle", async () => {
    await act(async () => {
      root?.render(
        <SplitPane
          primaryPane={<div id="left">Left Content</div>}
          secondaryPane={<div id="right">Right Content</div>}
          defaultSize={300}
        />
      )
    })

    expect(container?.querySelector("#left")?.textContent).toBe("Left Content")
    expect(container?.querySelector("#right")?.textContent).toBe("Right Content")

    const handle = container?.querySelector('[role="separator"]') as HTMLElement
    expect(handle).not.toBeNull()
    expect(handle.getAttribute("aria-orientation")).toBe("horizontal")
    expect(handle.getAttribute("aria-valuenow")).toBe("300")
  })

  it("restores pane size from localStorage when storageKey is provided", async () => {
    localStorage.setItem("test:split:size", "450")

    await act(async () => {
      root?.render(
        <SplitPane
          primaryPane={<div>Left</div>}
          secondaryPane={<div>Right</div>}
          defaultSize={300}
          storageKey="test:split:size"
        />
      )
    })

    const handle = container?.querySelector('[role="separator"]')
    expect(handle?.getAttribute("aria-valuenow")).toBe("450")
  })

  it("resizes via keyboard arrow keys and clamps at boundaries", async () => {
    const onSizeChange = vi.fn()
    await act(async () => {
      root?.render(
        <SplitPane
          primaryPane={<div>Left</div>}
          secondaryPane={<div>Right</div>}
          defaultSize={300}
          minSize={250}
          maxSize={400}
          step={10}
          onSizeChange={onSizeChange}
        />
      )
    })

    const handle = container?.querySelector('[role="separator"]') as HTMLElement
    handle.focus()

    // ArrowRight increases size by step 10 -> 310
    await act(async () => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }))
    })
    expect(handle.getAttribute("aria-valuenow")).toBe("310")
    expect(onSizeChange).toHaveBeenCalledWith(310)

    // Home snaps to minSize (250)
    await act(async () => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }))
    })
    expect(handle.getAttribute("aria-valuenow")).toBe("250")

    // End snaps to maxSize (400)
    await act(async () => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }))
    })
    expect(handle.getAttribute("aria-valuenow")).toBe("400")

    // Enter resets to defaultSize (300)
    await act(async () => {
      handle.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
    })
    expect(handle.getAttribute("aria-valuenow")).toBe("300")
  })

  it("supports vertical orientation layout", async () => {
    await act(async () => {
      root?.render(
        <SplitPane
          orientation="vertical"
          primaryPane={<div>Top</div>}
          secondaryPane={<div>Bottom</div>}
          defaultSize={200}
        />
      )
    })

    const handle = container?.querySelector('[role="separator"]')
    expect(handle?.getAttribute("aria-orientation")).toBe("vertical")
    expect(handle?.classList.contains("cursor-row-resize")).toBe(true)
  })

  it("resizes via pointer drag and persists to localStorage", async () => {
    await act(async () => {
      root?.render(
        <SplitPane
          primaryPane={<div>Left</div>}
          secondaryPane={<div>Right</div>}
          defaultSize={300}
          minSize={200}
          maxSize={500}
          storageKey="test:split:drag"
        />
      )
    })

    const handle = container?.querySelector('[role="separator"]') as HTMLElement

    // MouseDown on handle
    await act(async () => {
      handle.dispatchEvent(
        new MouseEvent("mousedown", { clientX: 300, bubbles: true, cancelable: true })
      )
    })

    // MouseMove on window
    await act(async () => {
      window.dispatchEvent(new MouseEvent("mousemove", { clientX: 350 }))
    })

    expect(handle.getAttribute("aria-valuenow")).toBe("350")

    // MouseUp on window
    await act(async () => {
      window.dispatchEvent(new MouseEvent("mouseup", { clientX: 350 }))
    })

    expect(localStorage.getItem("test:split:drag")).toBe("350")
  })
})
