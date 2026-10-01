// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { FilterPillGroup, type FilterPillOption } from "./FilterPillGroup"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("FilterPillGroup Primitive", () => {
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

  const MOCK_OPTIONS: FilterPillOption<string>[] = [
    { value: "all", label: "Tất cả", count: 42 },
    { value: "learning", label: "Đang học", count: 15, dotColor: "bg-amber-500" },
    { value: "review", label: "Ôn tập", count: 7, dotColor: "bg-emerald-500" },
    { value: "disabled_option", label: "Vô hiệu", disabled: true },
  ]

  it("renders with radiogroup role in single-select mode and applies active styling", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root?.render(
        <FilterPillGroup
          options={MOCK_OPTIONS}
          value="learning"
          onChange={onChange}
        />
      )
    })

    const group = container?.querySelector('[role="radiogroup"]')
    expect(group).not.toBeNull()

    const radios = container?.querySelectorAll('[role="radio"]')
    expect(radios).toHaveLength(4)

    // Verify checked status
    expect(radios?.[1]?.getAttribute("aria-checked")).toBe("true")
    expect(radios?.[0]?.getAttribute("aria-checked")).toBe("false")

    // Verify count badge rendered
    expect(radios?.[0]?.textContent).toContain("42")
    expect(radios?.[1]?.textContent).toContain("15")

    // Clicking unchecked enabled option calls onChange
    await act(async () => {
      ;(radios?.[2] as HTMLButtonElement).click()
    })
    expect(onChange).toHaveBeenCalledWith("review")
  })

  it("handles multi-select mode with group role and checkbox pills", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root?.render(
        <FilterPillGroup
          mode="multiple"
          options={MOCK_OPTIONS}
          value={["all", "review"]}
          onChange={onChange}
        />
      )
    })

    const group = container?.querySelector('[role="group"]')
    expect(group).not.toBeNull()

    const checkboxes = container?.querySelectorAll('[role="checkbox"]')
    expect(checkboxes?.[0]?.getAttribute("aria-checked")).toBe("true")
    expect(checkboxes?.[1]?.getAttribute("aria-checked")).toBe("false")
    expect(checkboxes?.[2]?.getAttribute("aria-checked")).toBe("true")

    // Clicking active checkbox removes it from selection
    await act(async () => {
      ;(checkboxes?.[0] as HTMLButtonElement).click()
    })
    expect(onChange).toHaveBeenCalledWith(["review"])

    // Clicking inactive checkbox adds it to selection
    await act(async () => {
      ;(checkboxes?.[1] as HTMLButtonElement).click()
    })
    expect(onChange).toHaveBeenCalledWith(["all", "review", "learning"])
  })

  it("navigates via arrow keys and skips disabled options", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root?.render(
        <FilterPillGroup
          options={MOCK_OPTIONS}
          value="all"
          onChange={onChange}
        />
      )
    })

    const radios = container?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
    expect(radios).toBeDefined()
    radios?.[0]?.focus()

    // ArrowRight moves from 'all' (index 0) to 'learning' (index 1)
    await act(async () => {
      radios?.[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }))
    })
    expect(onChange).toHaveBeenCalledWith("learning")

    // End key jumps to last enabled item ('review', index 2, skipping disabled at index 3)
    await act(async () => {
      radios?.[1]?.dispatchEvent(new KeyboardEvent("keydown", { key: "End", bubbles: true }))
    })
    expect(onChange).toHaveBeenCalledWith("review")

    // Home key jumps back to first enabled item ('all')
    await act(async () => {
      radios?.[2]?.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true }))
    })
    expect(onChange).toHaveBeenCalledWith("all")

    // ArrowLeft wraps around to last enabled item ('review')
    await act(async () => {
      radios?.[0]?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }))
    })
    expect(onChange).toHaveBeenCalledWith("review")
  })

  it("does not trigger onChange when clicking disabled option", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root?.render(
        <FilterPillGroup
          options={MOCK_OPTIONS}
          value="all"
          onChange={onChange}
        />
      )
    })

    const disabledBtn = container?.querySelectorAll<HTMLButtonElement>('[role="radio"]')?.[3]
    expect(disabledBtn?.disabled).toBe(true)

    await act(async () => {
      disabledBtn?.click()
    })
    expect(onChange).not.toHaveBeenCalled()
  })

  it("renders count badge for 0 and hides when undefined", async () => {
    const options: FilterPillOption<string>[] = [
      { value: "zero", label: "Không có", count: 0 },
      { value: "none", label: "Không đếm" },
    ]

    await act(async () => {
      root?.render(
        <FilterPillGroup
          options={options}
          value="zero"
          onChange={vi.fn()}
        />
      )
    })

    const pills = container?.querySelectorAll('[role="radio"]')
    expect(pills?.[0]?.querySelector('[data-slot="filter-pill-badge"]')?.textContent).toBe("0")
    expect(pills?.[1]?.querySelector('[data-slot="filter-pill-badge"]')).toBeNull()
  })

  it("renders label and dotColor correctly", async () => {
    await act(async () => {
      root?.render(
        <FilterPillGroup
          label="Phân loại:"
          options={MOCK_OPTIONS}
          value="learning"
          onChange={vi.fn()}
        />
      )
    })

    const labelEl = container?.querySelector('[data-slot="filter-pill-label"]')
    expect(labelEl?.textContent).toBe("Phân loại:")

    const dotEl = container?.querySelector('[data-slot="filter-pill-dot"]')
    expect(dotEl).not.toBeNull()
    expect(dotEl?.classList.contains("bg-amber-500")).toBe(true)
  })

  it("returns null when options array is empty", async () => {
    await act(async () => {
      root?.render(
        <FilterPillGroup
          options={[]}
          value=""
          onChange={vi.fn()}
        />
      )
    })

    expect(container?.innerHTML).toBe("")
  })
})
