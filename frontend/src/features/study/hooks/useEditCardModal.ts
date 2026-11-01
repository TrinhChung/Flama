import { useEffect, useRef, useState } from 'react'
import { apiJson } from '@/shared/api/client'
import { stageNoteMedia } from '@/entities/flashcard'
import { updateCardFieldValuesInSessions } from '../session/sessionStore'
import type { StudyCardEditResponse } from '../types'

type FieldDef = {
  name: string
  field_type: string
  required?: boolean
}

type DeckOption = {
  id: number
  name: string
}

export type EditCardModalProps = {
  opened: boolean
  onClose: () => void
  cardId?: string | null
  noteId?: string | null
  saveUrl?: string | null
  fieldDefs?: FieldDef[]
  initialFieldValues?: Record<string, string>
  initialDeckId?: number | null
  initialTags?: string[]
  decks?: DeckOption[]
  onSaved?: (result: StudyCardEditResponse) => void
  onDeleted?: () => void
}

const EMPTY_FIELDS: FieldDef[] = []
const EMPTY_VALUES: Record<string, string> = {}
const EMPTY_TAGS: string[] = []

export function useEditCardModal({
  opened, onClose, cardId, noteId, saveUrl, fieldDefs = EMPTY_FIELDS, initialFieldValues = EMPTY_VALUES,
  initialDeckId, initialTags = EMPTY_TAGS, onSaved, onDeleted,
}: EditCardModalProps) {
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [deckId, setDeckId] = useState<number | null>(null)
  const [tagsStr, setTagsStr] = useState<string>('')
  const [saving, setSaving] = useState(false)
  const [uploadingField, setUploadingField] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeFieldName, setActiveFieldName] = useState<string | null>(null)
  const [fieldModes, setFieldModes] = useState<Record<string, 'edit' | 'preview'>>({})
  const [globalPreview, setGlobalPreview] = useState(false)
  const uploadRef = useRef<AbortController | null>(null)
  const focusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    setUploadingField(null)
    return () => {
      uploadRef.current?.abort()
      uploadRef.current = null
      if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
    }
  }, [opened, noteId])

  useEffect(() => {
    if (opened) {
      setFieldValues({ ...initialFieldValues })
      setDeckId(initialDeckId ?? null)
      setTagsStr(initialTags.join(', '))
      setError(null)
      setFieldModes({})
      setGlobalPreview(false)
      const firstField = fieldDefs[0]?.name || null
      setActiveFieldName(firstField)
    }
  }, [opened, initialFieldValues, initialDeckId, initialTags, fieldDefs])

  const targetFieldName = activeFieldName || fieldDefs[0]?.name || ''

  const insertMarkdownSyntax = (prefix: string, suffix = '') => {
    if (!targetFieldName) return
    const textarea = document.querySelector<HTMLTextAreaElement>(
      `textarea[data-field-name="${CSS.escape(targetFieldName)}"]`
    )
    if (textarea) {
      const start = textarea.selectionStart || 0
      const end = textarea.selectionEnd || start
      const current = textarea.value || ''
      const selected = current.slice(start, end) || ''
      const nextValue = `${current.slice(0, start)}${prefix}${selected}${suffix}${current.slice(
        end
      )}`
      setFieldValues((prev) => ({ ...prev, [targetFieldName]: nextValue }))
      if (focusTimerRef.current) clearTimeout(focusTimerRef.current)
      focusTimerRef.current = setTimeout(() => {
        textarea.focus()
        textarea.setSelectionRange(start + prefix.length, start + prefix.length + selected.length)
      }, 0)
    } else {
      setFieldValues((prev) => {
        const current = prev[targetFieldName] || ''
        return { ...prev, [targetFieldName]: `${current}${prefix}${suffix}` }
      })
    }
  }

  const handleMediaUpload = async (fieldName: string, file: File) => {
    if (!noteId) {
      setError('Không tìm thấy ID note để tải media lên.')
      return
    }
    uploadRef.current?.abort()
    const controller = new AbortController()
    uploadRef.current = controller
    setUploadingField(fieldName)
    setError(null)
    try {
      const isMarkdown = (fieldDefs.find((f) => f.name === fieldName)?.field_type || '').toLowerCase() === 'markdown'
      const staged = await stageNoteMedia(file, file.name, { noteId, fieldName }, controller.signal)
      if (controller.signal.aborted) return
      const url = staged.url
      if (isMarkdown) {
        const markdownSnippet = `\n![${file.name}](${url})\n`
        setFieldValues((prev) => ({ ...prev, [fieldName]: `${prev[fieldName] || ''}${markdownSnippet}` }))
      } else {
        setFieldValues((prev) => ({ ...prev, [fieldName]: url }))
      }
    } catch (err) {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Upload media thất bại.')
    } finally {
      if (uploadRef.current === controller) {
        uploadRef.current = null
        setUploadingField(null)
      }
    }
  }

  const handleSave = async () => {
    if (!cardId || uploadingField) return
    setSaving(true)
    setError(null)
    try {
      const endpoint = saveUrl || `/api/study/cards/${cardId}/edit`
      const tags = tagsStr.split(',').map((t) => t.trim()).filter(Boolean)
      const result = await apiJson<StudyCardEditResponse>(endpoint, 'PATCH', {
        field_values: fieldValues,
        deck_id: deckId,
        tags,
        render_contract: 'client_v1',
      })
      if (cardId) {
        void updateCardFieldValuesInSessions(cardId, result.field_values, { noteId })
      }
      onSaved?.(result)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu thay đổi.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!noteId) return
    if (!window.confirm('Xóa note này và tất cả cards liên quan? Không thể hoàn tác.')) return
    setSaving(true)
    setError(null)
    try {
      await apiJson(`/api/notes/${noteId}`, 'DELETE')
      onDeleted?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể xóa note.')
    } finally {
      setSaving(false)
    }
  }

  const toggleFieldMode = (name: string, mode: 'edit' | 'preview') => {
    setFieldModes((prev) => ({ ...prev, [name]: mode }))
  }

  return {
    fieldValues, setFieldValues, deckId, setDeckId, tagsStr, setTagsStr, saving,
    uploadingField, error, activeFieldName, setActiveFieldName, fieldModes,
    globalPreview, setGlobalPreview, targetFieldName, insertMarkdownSyntax,
    handleMediaUpload, handleSave, handleDelete, toggleFieldMode,
  }
}
