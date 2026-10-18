// @vitest-environment jsdom
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { CardFieldsForm, type CardFieldDef } from "./CardFieldsForm"

;(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function setNativeValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype =
    element instanceof HTMLTextAreaElement
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value")
  descriptor?.set?.call(element, value)
  element.dispatchEvent(new Event("input", { bubbles: true }))
  element.dispatchEvent(new Event("change", { bubbles: true }))
}

describe("CardFieldsForm Primitive", () => {
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

  const MOCK_FIELDS: CardFieldDef[] = [
    { name: "Expression", required: true, field_type: "text", placeholder: "Ví dụ: 食べる" },
    { name: "Reading", required: false, field_type: "text" },
    { name: "Meaning", required: true, field_type: "textarea" },
    { name: "Audio", required: false, field_type: "audio" },
  ]

  it("renders single-line inputs and multiline textareas according to field definitions", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{ Expression: "猫", Reading: "ねこ", Meaning: "Con mèo" }}
          onChange={onChange}
        />
      )
    })

    const expressionInput = container?.querySelector('input[name="Expression"]') as HTMLInputElement
    expect(expressionInput).not.toBeNull()
    expect(expressionInput.value).toBe("猫")
    expect(expressionInput.required).toBe(true)

    const meaningTextarea = container?.querySelector('textarea[name="Meaning"]') as HTMLTextAreaElement
    expect(meaningTextarea).not.toBeNull()
    expect(meaningTextarea.value).toBe("Con mèo")

    // Editing input calls onChange with updated values object
    await act(async () => {
      setNativeValue(expressionInput, "犬")
    })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ Expression: "犬" })
    )
  })

  it("displays validation error styling and message when error map contains field", async () => {
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{ Expression: "", Reading: "", Meaning: "" }}
          onChange={vi.fn()}
          errors={{ Expression: "Từ vựng là trường bắt buộc." }}
        />
      )
    })

    const input = container?.querySelector('input[name="Expression"]') as HTMLInputElement
    expect(input.getAttribute("aria-invalid")).toBe("true")
    expect(input.classList.contains("border-destructive")).toBe(true)

    const errorMsg = container?.querySelector("#field-Expression-error")
    expect(errorMsg?.textContent).toBe("Từ vựng là trường bắt buộc.")
  })

  it("triggers onSubmit callback when pressing Ctrl+Enter inside input", async () => {
    const onSubmit = vi.fn()
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{ Expression: "猫", Reading: "ねこ", Meaning: "Con mèo" }}
          onChange={vi.fn()}
          onSubmit={onSubmit}
        />
      )
    })

    const input = container?.querySelector('input[name="Expression"]') as HTMLInputElement
    await act(async () => {
      input.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "Enter",
          ctrlKey: true,
          bubbles: true,
        })
      )
    })

    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it("manages tag addition and removal", async () => {
    const onTagsChange = vi.fn()
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{}}
          onChange={vi.fn()}
          tags={["N5", "Động từ"]}
          onTagsChange={onTagsChange}
        />
      )
    })

    // Verify existing tags rendered
    expect(container?.textContent).toContain("N5")
    expect(container?.textContent).toContain("Động từ")

    // Add new tag
    const tagInput = container?.querySelector('input[placeholder="Tag mới…"]') as HTMLInputElement
    await act(async () => {
      setNativeValue(tagInput, "JLPT")
    })

    await act(async () => {
      tagInput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
    })
    expect(onTagsChange).toHaveBeenCalledWith(["N5", "Động từ", "JLPT"])

    // Remove tag button
    const removeBtn = container?.querySelector('button[aria-label="Xóa tag N5"]') as HTMLButtonElement
    expect(removeBtn).not.toBeNull()
    await act(async () => {
      removeBtn.click()
    })
    expect(onTagsChange).toHaveBeenCalledWith(["Động từ"])
  })

  it("renders audio trigger button when field is audio type with sound value", async () => {
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{ Audio: "[sound:neko.mp3]" }}
          onChange={vi.fn()}
          resolveMediaUrl={(raw) => `https://cdn.example.com/${raw}`}
        />
      )
    })

    const playBtn = container?.querySelector('button[aria-label="Phát âm thanh Audio"]')
    expect(playBtn).not.toBeNull()
  })

  it("toggles markdown preview on multiline textarea", async () => {
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{ Meaning: "### Ý nghĩa\n- Nghĩa 1" }}
          onChange={vi.fn()}
          enableMarkdownPreview={true}
        />
      )
    })

    const previewToggleBtn = container?.querySelector(
      'button[aria-label="Xem trước Meaning"]'
    ) as HTMLButtonElement
    expect(previewToggleBtn).not.toBeNull()

    // Toggle preview on
    await act(async () => {
      previewToggleBtn.click()
    })

    const previewBlock = container?.querySelector('[data-slot="markdown-preview"]')
    expect(previewBlock).not.toBeNull()
    expect(previewBlock?.textContent).toContain("### Ý nghĩa")

    // Toggle back to edit
    const editToggleBtn = container?.querySelector(
      'button[aria-label="Chỉnh sửa Meaning"]'
    ) as HTMLButtonElement
    expect(editToggleBtn).not.toBeNull()

    await act(async () => {
      editToggleBtn.click()
    })

    const textarea = container?.querySelector('textarea[name="Meaning"]')
    expect(textarea).not.toBeNull()
  })

  it("handles array and non-string values safely without crashing", async () => {
    await act(async () => {
      root?.render(
        <CardFieldsForm
          fieldDefs={MOCK_FIELDS}
          values={{
            Expression: 123 as any,
            Meaning: ["Nghĩa 1", "Nghĩa 2"] as any,
            Audio: ["sound.mp3"] as any,
          }}
          onChange={vi.fn()}
        />
      )
    })

    const expressionInput = container?.querySelector('input[name="Expression"]') as HTMLInputElement
    expect(expressionInput).not.toBeNull()
    expect(expressionInput.value).toBe("123")

    const meaningTextarea = container?.querySelector('textarea[name="Meaning"]') as HTMLTextAreaElement
    expect(meaningTextarea).not.toBeNull()
    expect(meaningTextarea.value).toBe("Nghĩa 1\nNghĩa 2")
  })
})
