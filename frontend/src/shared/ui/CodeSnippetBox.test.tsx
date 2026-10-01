// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { CodeSnippetBox } from "./CodeSnippetBox"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

describe("CodeSnippetBox Primitive", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
    vi.useFakeTimers()
  })

  afterEach(async () => {
    vi.useRealTimers()
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

  it("renders code snippet, title, and language badge", async () => {
    const sampleCode = "const x = 42;"

    await act(async () => {
      root?.render(
        <CodeSnippetBox
          code={sampleCode}
          title="config.js"
          language="javascript"
        />
      )
    })

    expect(container?.textContent).toContain("config.js")
    expect(container?.textContent).toContain("javascript")
    expect(container?.querySelector("code")?.textContent).toBe(sampleCode)
  })

  it("copies code to clipboard and shows 2-second confirmation feedback", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, {
      clipboard: { writeText: writeTextMock },
    })

    const onCopy = vi.fn()
    const sampleCode = "git status"

    await act(async () => {
      root?.render(
        <CodeSnippetBox
          code={sampleCode}
          onCopy={onCopy}
        />
      )
    })

    const copyBtn = container?.querySelector("button") as HTMLButtonElement
    expect(copyBtn).toBeDefined()
    expect(copyBtn.textContent).toContain("Sao chép")

    await act(async () => {
      copyBtn.click()
    })

    expect(writeTextMock).toHaveBeenCalledWith(sampleCode)
    expect(onCopy).toHaveBeenCalledWith(sampleCode)
    expect(copyBtn.textContent).toContain("Đã chép")

    // Fast-forward 2000ms
    act(() => {
      vi.advanceTimersByTime(2000)
    })

    expect(copyBtn.textContent).toContain("Sao chép")
  })

  it("renders line numbers when showLineNumbers is true", async () => {
    const multiLineCode = "line 1\nline 2\nline 3"

    await act(async () => {
      root?.render(
        <CodeSnippetBox
          code={multiLineCode}
          showLineNumbers={true}
        />
      )
    })

    expect(container?.textContent).toContain("1")
    expect(container?.textContent).toContain("2")
    expect(container?.textContent).toContain("3")
    expect(container?.querySelector("code")?.textContent).toBe(multiLineCode)
  })
})
