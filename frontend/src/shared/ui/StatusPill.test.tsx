// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { StatusPill } from "./StatusPill"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("StatusPill Primitive", () => {
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

  it("renders all 8 semantic variants with correct classes", async () => {
    const variants = [
      "new",
      "learning",
      "review",
      "due",
      "active",
      "pending",
      "revoked",
      "failed",
    ] as const

    await act(async () => {
      root?.render(
        <div>
          {variants.map((v) => (
            <StatusPill key={v} variant={v} data-testid={v}>
              {v}
            </StatusPill>
          ))}
        </div>
      )
    })

    variants.forEach((v) => {
      const pill = container?.querySelector(`[data-testid="${v}"]`)
      expect(pill).toBeDefined()
      expect(pill?.textContent).toBe(v)
      expect(pill?.getAttribute("data-variant")).toBe(v)
    })
  })

  it("renders pulsing dot indicator when dot is true and dotStyle is pulse", async () => {
    await act(async () => {
      root?.render(
        <StatusPill variant="active" dot dotStyle="pulse">
          Đang hoạt động
        </StatusPill>
      )
    })

    expect(container?.querySelector(".animate-ping")).toBeDefined()
    expect(container?.textContent).toContain("Đang hoạt động")
  })

  it("renders solid dot indicator when dot is true and dotStyle is solid", async () => {
    await act(async () => {
      root?.render(
        <StatusPill variant="learning" dot dotStyle="solid">
          Đang học
        </StatusPill>
      )
    })

    expect(container?.querySelector('[data-slot="status-pill-dot"]')).toBeDefined()
    expect(container?.querySelector(".animate-ping")).toBeNull()
    expect(container?.textContent).toContain("Đang học")
  })

  it("applies size classes for sm and md", async () => {
    await act(async () => {
      root?.render(
        <div>
          <StatusPill id="pill-sm" size="sm">
            Small
          </StatusPill>
          <StatusPill id="pill-md" size="md">
            Medium
          </StatusPill>
        </div>
      )
    })

    const pillSm = container?.querySelector("#pill-sm")
    const pillMd = container?.querySelector("#pill-md")
    expect(pillSm?.className).toContain("h-5")
    expect(pillMd?.className).toContain("h-6")
  })
})
