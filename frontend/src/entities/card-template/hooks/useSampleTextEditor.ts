import { useEffect, useRef, useState } from 'react'
import DOMPurify from 'dompurify'

const clean = (source: string) => DOMPurify.sanitize(source, { ALLOWED_TAGS: ['p', 'div', 'br', 'strong', 'b', 'em', 'i', 'u', 's', 'ul', 'ol', 'li'], ALLOWED_ATTR: [] })

export function useSampleTextEditor(value: string, onChange: (value: string) => void) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const richRef = useRef<HTMLDivElement>(null)
  const [sourceMode, setSourceMode] = useState(false)
  useEffect(() => {
    if (richRef.current && richRef.current.innerHTML !== clean(value)) richRef.current.innerHTML = clean(value)
  }, [value, sourceMode])
  const inputRichText = () => {
    if (!richRef.current) return
    const html = richRef.current.textContent?.trim() ? clean(richRef.current.innerHTML) : ''
    if (html !== richRef.current.innerHTML) richRef.current.innerHTML = html
    onChange(html)
  }
  const formatRich = (tag: 'strong' | 'em' | 'ul') => {
    const root = richRef.current
    if (!root) return
    const selection = window.getSelection()
    const range = selection?.rangeCount && root.contains(selection.anchorNode) && root.contains(selection.focusNode)
      ? selection.getRangeAt(0) : document.createRange()
    if (!range.commonAncestorContainer || !root.contains(range.commonAncestorContainer)) { range.selectNodeContents(root); range.collapse(false) }
    const wrapper = document.createElement(tag)
    const target = tag === 'ul' ? document.createElement('li') : wrapper
    target.append(range.extractContents())
    if (!target.textContent) target.textContent = 'Text'
    if (tag === 'ul') wrapper.append(target)
    range.insertNode(wrapper)
    root.focus()
    range.selectNodeContents(target)
    selection?.removeAllRanges()
    selection?.addRange(range)
    inputRichText()
  }
  const format = (opening: string, closing: string) => {
    const start = ref.current?.selectionStart ?? value.length
    const end = ref.current?.selectionEnd ?? value.length
    onChange(`${value.slice(0, start)}${opening}${value.slice(start, end)}${closing}${value.slice(end)}`)
    ref.current?.focus()
  }
  return { ref, format, richRef, inputRichText, formatRich, sourceMode, toggleSource: () => setSourceMode((old) => !old) }
}
