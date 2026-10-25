import { useState } from 'react'
import { isTextArray } from '../lib/previewSamples'
import type { TemplatePreviewArray } from '../model/types'
import type { TemplateSampleValue } from '../model/previewSamples'

export function useSampleArrayEditor(value: TemplateSampleValue, onChange: (value: TemplateSampleValue) => void) {
  const [advanced, setAdvanced] = useState(false)
  const [draft, setDraft] = useState<{ source: TemplateSampleValue; text: string; invalid: boolean } | null>(null)
  const items: TemplatePreviewArray = Array.isArray(value) ? value : value ? value.split(/\r?\n/) : []
  const nested = items.some(Array.isArray)
  const currentDraft = draft?.source === value ? draft : null
  const code = currentDraft?.text ?? JSON.stringify(items, null, 2)
  const updateCode = (text: string) => {
    try {
      const parsed: unknown = JSON.parse(text)
      if (!isTextArray(parsed)) throw new Error('Invalid array')
      setDraft({ source: parsed, text, invalid: false })
      onChange(parsed)
    } catch {
      setDraft({ source: value, text, invalid: true })
    }
  }
  const updateItems = (next: TemplatePreviewArray) => { setDraft(null); onChange(next) }
  return {
    items, nested, code, invalid: currentDraft?.invalid ?? false, advanced: advanced || nested,
    toggleAdvanced: () => { if (!currentDraft?.invalid && !nested) { setDraft(null); setAdvanced((old) => !old) } },
    updateCode,
    changeItem: (index: number, text: string) => updateItems(items.map((item, position) => position === index ? text : item)),
    add: () => updateItems([...items, '']),
    remove: (index: number) => updateItems(items.filter((_, position) => position !== index)),
    move: (index: number, offset: number) => {
      const next = [...items]
      const target = index + offset
      if (target < 0 || target >= next.length) return
      ;[next[index], next[target]] = [next[target], next[index]]
      updateItems(next)
    },
  }
}
