// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { WorkspaceLayout } from "./WorkspaceLayout"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("WorkspaceLayout", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    localStorage.clear()
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(async () => root.unmount())
    document.body.replaceChildren()
  })

  const tab = (label: string) => [...container.querySelectorAll<HTMLButtonElement>('[role="tab"]')].find((item) => item.textContent === label)!
  const pane = (slot: "primary" | "secondary") => container.querySelector<HTMLElement>(`[data-slot="split-pane-${slot}"]`)!
  const props = {
    primary: <textarea aria-label="Editor" />,
    secondary: <div>Preview</div>,
    primaryLabel: "Editor",
    secondaryLabel: "Preview",
    tabsLabel: "Workspace",
  }

  it("shows one pane at a time below lg and both panes from lg", async () => {
    await act(async () => root.render(<WorkspaceLayout {...props} />))
    expect(container.querySelector('[role="tablist"]')?.getAttribute("aria-label")).toBe("Workspace")
    expect(tab("Editor").getAttribute("aria-selected")).toBe("true")
    expect(pane("primary").className).not.toContain("hidden")
    expect(pane("secondary").className).toContain("hidden lg:block")

    await act(async () => tab("Preview").click())
    expect(tab("Preview").getAttribute("aria-selected")).toBe("true")
    expect(pane("primary").className).toContain("hidden lg:block")
    expect(pane("secondary").className).not.toMatch(/(^|\s)hidden(\s|$)/)
  })

  it("supports a controlled pane and a persisted split ratio", async () => {
    localStorage.setItem("test:workspace", "64")
    const onActivePaneChange = vi.fn()
    await act(async () => root.render(<WorkspaceLayout {...props} activePane="secondary" onActivePaneChange={onActivePaneChange}
      storageKey="test:workspace" defaultRatio={50} minRatio={30} maxRatio={70} />))
    expect(tab("Preview").getAttribute("aria-selected")).toBe("true")
    await act(async () => tab("Editor").click())
    expect(onActivePaneChange).toHaveBeenCalledWith("primary")
    // Controlled: the parent decides, so the pane does not switch on its own.
    expect(tab("Preview").getAttribute("aria-selected")).toBe("true")
    const separator = container.querySelector('[role="separator"]')!
    expect(separator.getAttribute("aria-valuenow")).toBe("64")
    expect(separator.getAttribute("aria-label")).toBe("Kéo để thay đổi kích thước")
  })
})
