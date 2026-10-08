// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it } from "vitest"
import i18n, { DEFAULT_LOCALE } from "@/shared/config/i18n"
import { LanguageSwitcher } from "./LanguageSwitcher"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("LanguageSwitcher Component — Zero Layout Shift & Dimensions", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(async () => {
    localStorage.clear()
    await act(async () => {
      await i18n.changeLanguage(DEFAULT_LOCALE)
    })
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

  it("renders dropdown trigger with fixed height h-8 and fixed badge width w-5 in Vietnamese", async () => {
    await act(async () => {
      root?.render(<LanguageSwitcher />)
    })

    const button = container?.querySelector("button")
    expect(button).toBeTruthy()
    // Verify fixed height h-8
    expect(button?.className).toContain("h-8")
    expect(button?.className).toContain("rounded-full")

    // Verify language badge
    const badge = button?.querySelector("span")
    expect(badge).toBeTruthy()
    expect(badge?.className).toContain("uppercase")
    expect(badge?.className).toContain("w-5")
    expect(badge?.textContent?.trim()).toBe("VI")
  })

  it("switches to English: maintains identical dimensions and styling (CLS = 0)", async () => {
    await act(async () => {
      root?.render(<LanguageSwitcher />)
    })

    const initialButton = container?.querySelector("button")
    const initialClasses = initialButton?.className
    const initialBadgeClasses = initialButton?.querySelector("span")?.className

    // Switch to English
    await act(async () => {
      await i18n.changeLanguage("en")
    })

    const enButton = container?.querySelector("button")
    const enBadge = enButton?.querySelector("span")

    expect(enBadge?.textContent?.trim()).toBe("EN")
    // Structural invariant: button classes and badge classes are byte-identical
    expect(enButton?.className).toBe(initialClasses)
    expect(enBadge?.className).toBe(initialBadgeClasses)
    expect(enButton?.className).toContain("h-8")
  })

  it("renders compact mode with h-7 and compact gap/padding", async () => {
    await act(async () => {
      root?.render(<LanguageSwitcher compact />)
    })

    const button = container?.querySelector("button")
    expect(button).toBeTruthy()
    expect(button?.className).toContain("h-7")
    expect(button?.className).toContain("px-2")
    expect(button?.className).toContain("gap-1")

    const badge = button?.querySelector("span")
    expect(badge).toBeTruthy()
  })

  it("renders pill variant with fixed height container h-8", async () => {
    await act(async () => {
      root?.render(<LanguageSwitcher variant="pill" />)
    })

    const group = container?.querySelector('div[role="group"]')
    expect(group).toBeTruthy()
    expect(group?.className).toContain("h-8")

    const buttons = container?.querySelectorAll("button")
    expect(buttons?.length).toBe(2)
    buttons?.forEach((btn) => {
      expect(btn.className).toContain("h-6.5")
    })
  })

  it("translates the accessible language picker label in English", async () => {
    await act(async () => {
      await i18n.changeLanguage("en")
      root?.render(<LanguageSwitcher variant="pill" />)
    })

    expect(container?.querySelector('[role="group"]')?.getAttribute("aria-label"))
      .toBe(i18n.getResource("en", "common", "language.switch_aria"))
  })
})
