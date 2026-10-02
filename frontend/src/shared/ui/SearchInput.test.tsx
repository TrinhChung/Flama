// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { SearchInput } from "./SearchInput"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("SearchInput Primitive", () => {
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

  it("renders with default search icon and placeholder", async () => {
    await act(async () => {
      root?.render(<SearchInput placeholder="Tìm kiếm thẻ học..." />)
    })

    const input = container?.querySelector('input[type="search"]') as HTMLInputElement
    expect(input).toBeDefined()
    expect(input.placeholder).toBe("Tìm kiếm thẻ học...")
    expect(container?.querySelector('[data-slot="search-icon"]')).toBeDefined()
  })

  it("displays clear button only when value is present and clears on click", async () => {
    const onClear = vi.fn()
    const onChange = vi.fn()

    await act(async () => {
      root?.render(
        <SearchInput
          defaultValue="JLPT N2"
          onClear={onClear}
          onChange={onChange}
        />
      )
    })

    const clearBtn = container?.querySelector('[data-slot="search-clear-btn"]') as HTMLButtonElement
    expect(clearBtn).toBeDefined()

    await act(async () => {
      clearBtn.click()
    })

    expect(onClear).toHaveBeenCalledOnce()
    const input = container?.querySelector("input") as HTMLInputElement
    expect(input.value).toBe("")
  })

  it("displays loading spinner when isLoading is true and hides clear button", async () => {
    await act(async () => {
      root?.render(
        <SearchInput
          defaultValue="Testing"
          isLoading={true}
        />
      )
    })

    expect(container?.querySelector('[data-slot="search-spinner"]')).toBeDefined()
    expect(container?.querySelector('[data-slot="search-clear-btn"]')).toBeNull()
  })

  it("renders shortcut badge when empty and triggers global shortcut keydown", async () => {
    await act(async () => {
      root?.render(<SearchInput shortcut="Ctrl+K" />)
    })

    const badge = container?.querySelector('[data-slot="search-shortcut-badge"]')
    expect(badge?.textContent).toBe("Ctrl+K")

    const input = container?.querySelector("input") as HTMLInputElement
    const focusSpy = vi.spyOn(input, "focus")

    // Simulate global Ctrl+K
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))
    })

    expect(focusSpy).toHaveBeenCalled()
  })

  it("guards against Escape key clearing during Japanese IME composition", async () => {
    const onClear = vi.fn()

    await act(async () => {
      root?.render(
        <SearchInput
          defaultValue="にほんご"
          onClear={onClear}
        />
      )
    })

    const input = container?.querySelector("input") as HTMLInputElement

    // 1. Simulate IME composition start
    await act(async () => {
      input.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }))
    })

    // 2. Press Escape during composition -> MUST NOT CLEAR
    await act(async () => {
      const escapeEvent = new KeyboardEvent("keydown", { key: "Escape", bubbles: true })
      Object.defineProperty(escapeEvent, "isComposing", { value: true })
      input.dispatchEvent(escapeEvent)
    })

    expect(onClear).not.toHaveBeenCalled()
    expect(input.value).toBe("にほんご")

    // 3. Simulate IME composition end
    await act(async () => {
      input.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }))
    })

    // 4. Press Escape after composition -> MUST CLEAR
    await act(async () => {
      const escapeEvent = new KeyboardEvent("keydown", { key: "Escape", bubbles: true })
      Object.defineProperty(escapeEvent, "isComposing", { value: false })
      input.dispatchEvent(escapeEvent)
    })

    expect(onClear).toHaveBeenCalledOnce()
  })

  it("guards against Enter key triggering during Japanese IME composition", async () => {
    const onKeyDown = vi.fn()

    await act(async () => {
      root?.render(
        <SearchInput
          defaultValue="漢字"
          onKeyDown={onKeyDown}
        />
      )
    })

    const input = container?.querySelector("input") as HTMLInputElement

    // IME composition start
    await act(async () => {
      input.dispatchEvent(new CompositionEvent("compositionstart", { bubbles: true }))
    })

    // Enter during IME composition
    await act(async () => {
      const enterEvent = new KeyboardEvent("keydown", { key: "Enter", bubbles: true })
      Object.defineProperty(enterEvent, "isComposing", { value: true })
      input.dispatchEvent(enterEvent)
    })

    // onKeyDown handler should not have been called for Enter during composition
    expect(onKeyDown).not.toHaveBeenCalled()

    // IME composition end
    await act(async () => {
      input.dispatchEvent(new CompositionEvent("compositionend", { bubbles: true }))
    })

    // Enter after IME composition ends
    await act(async () => {
      const enterEvent = new KeyboardEvent("keydown", { key: "Enter", bubbles: true })
      Object.defineProperty(enterEvent, "isComposing", { value: false })
      input.dispatchEvent(enterEvent)
    })

    expect(onKeyDown).toHaveBeenCalledOnce()
  })
})
