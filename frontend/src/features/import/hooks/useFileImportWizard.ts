import { useState, useEffect, useRef, useId, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { apiRequest } from '@/shared/api/client'

export type DeckOption = {
  id: number
  name: string
  path: string
  note_type_id?: string | null
  parent_id?: number | null
  notes_count?: number
}

export type NoteField = {
  id: string
  name: string
  position: number
  required: boolean
  field_type: string
}

export type NoteTypeOption = {
  id: string
  name: string
  fields: NoteField[]
}

export type ImportOptionsResponse = {
  deck_options: DeckOption[]
  note_type_options: NoteTypeOption[]
  initial_deck_id: number | null
  initial_note_type_id: string | null
  uniqueness_defaults: Record<string, string[]>
}

export type ParsedColumn = {
  index: number
  name: string
  display: string
}

export type ParseResponse = {
  token: string
  delimiter: string
  has_header: boolean
  columns: ParsedColumn[]
  column_count: number
  total_rows: number
  preview_rows: string[][]
  warnings: Array<{ code: string; severity: string; message: string }>
  suggested_mapping: Record<
    string,
    { source_type: 'column' | 'ignore' | 'constant'; column_index: number | null; constant_value: string }
  >
}

export type FieldMapping = {
  source_type: 'column' | 'ignore' | 'constant'
  column_index: number | null
  constant_value: string
}

export type ReportSummary = {
  total_rows: number
  valid_rows: number
  inserted: number
  updated: number
  skipped: number
  unchanged: number
  errors: number
}

export type IssueItem = {
  kind: string
  row: number
  reason: string
  message: string
}

export type ImportReport = {
  summary: ReportSummary
  issues: IssueItem[]
}

export function useFileImportWizard() {
  const [searchParams] = useSearchParams()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [selectedDeckId, setSelectedDeckId] = useState<string>('')
  const [selectedNoteTypeId, setSelectedNoteTypeId] = useState<string>('')
  const [autoSelectBadge, setAutoSelectBadge] = useState<boolean>(false)

  // Step A: Parse State
  const [file, setFile] = useState<File | null>(null)
  const [isDragOver, setIsDragOver] = useState<boolean>(false)
  const [delimiterMode, setDelimiterMode] = useState<'csv' | 'tsv' | 'custom'>('csv')
  const [customDelimiter, setCustomDelimiter] = useState<string>('')
  const [hasHeader, setHasHeader] = useState<boolean>(true)

  // Parse result state
  const [token, setToken] = useState<string | null>(null)
  const [columns, setColumns] = useState<ParsedColumn[]>([])
  const [previewRows, setPreviewRows] = useState<string[][]>([])
  const [parseWarnings, setParseWarnings] = useState<Array<{ code: string; severity: string; message: string }>>([])
  const [parseMeta, setParseMeta] = useState<{ filename: string; totalRows: number; columnCount: number; delimiterLabel: string } | null>(null)

  // Step B: Mapping State
  const [mapping, setMapping] = useState<Record<string, FieldMapping>>({})

  // Step C: Options State
  const [importMode, setImportMode] = useState<'insert_only' | 'update_only' | 'upsert'>('upsert')
  const [dontOverwriteEmpty, setDontOverwriteEmpty] = useState<boolean>(true)
  const [uniquenessFields, setUniquenessFields] = useState<string[]>([])
  const [confirmColumnMismatch, setConfirmColumnMismatch] = useState<boolean>(false)

  // Step D: Report & Execution State
  const [report, setReport] = useState<ImportReport | null>(null)
  const [hasEstimated, setHasEstimated] = useState<boolean>(false)
  const [executionDone, setExecutionDone] = useState<boolean>(false)

  const [warnOnNonEmptyDeck, setWarnOnNonEmptyDeck] = useState<boolean>(() => {
    return localStorage.getItem('flama_import_warn_non_empty_deck') !== 'false'
  })

  const handleWarnOnNonEmptyDeckChange = (checked: boolean) => {
    setWarnOnNonEmptyDeck(checked)
    localStorage.setItem('flama_import_warn_non_empty_deck', String(checked))
  }

  // Generate unique form control IDs
  const noteTypeSelectId = useId()
  const delimiterModeSelectId = useId()
  const customDelimiterInputId = useId()
  const columnMismatchConfirmId = useId()
  const dontOverwriteEmptyId = useId()

  const deckIdQueryParam = searchParams.get('deck_id')

  // Load import initial options
  const optionsQuery = useQuery({
    queryKey: ['flashcard-import-options', deckIdQueryParam],
    queryFn: () => appApi.get<ImportOptionsResponse>('/flashcards/import/options', { deck_id: deckIdQueryParam }),
  })

  useEffect(() => {
    if (optionsQuery.data) {
      const data = optionsQuery.data
      if (data.initial_deck_id) setSelectedDeckId(String(data.initial_deck_id))
      if (data.initial_note_type_id) setSelectedNoteTypeId(data.initial_note_type_id)
    }
  }, [optionsQuery.data])

  const deckOptions = optionsQuery.data?.deck_options || []
  const noteTypeOptions = optionsQuery.data?.note_type_options || []
  const currentNoteType = noteTypeOptions.find((nt) => nt.id === selectedNoteTypeId) || null
  const fields = useMemo(() => currentNoteType?.fields || [], [currentNoteType?.fields])

  // Initialize uniqueness fields defaults when note type changes
  useEffect(() => {
    if (!selectedNoteTypeId || !optionsQuery.data) return
    const defaults = optionsQuery.data.uniqueness_defaults[selectedNoteTypeId] || []
    if (defaults.length > 0) {
      setUniquenessFields(defaults)
    } else if (fields.length > 0) {
      setUniquenessFields([fields[0].name])
    } else {
      setUniquenessFields([])
    }
  }, [selectedNoteTypeId, optionsQuery.data, fields])

  // Infer note type from sibling decks
  const handleDeckChange = (newDeckId: string) => {
    setSelectedDeckId(newDeckId)
    if (!newDeckId) return

    const selectedDeck = deckOptions.find((d) => String(d.id) === newDeckId)
    if (!selectedDeck) return

    const parentId = selectedDeck.parent_id != null ? String(selectedDeck.parent_id) : null
    const siblings = deckOptions.filter(
      (d) => String(d.id) !== newDeckId && (d.parent_id != null ? String(d.parent_id) : null) === parentId
    )

    if (siblings.length) {
      const siblingTypes = siblings.map((s) => s.note_type_id ? String(s.note_type_id) : null).filter(Boolean)
      const uniqueTypes = new Set(siblingTypes)
      if (uniqueTypes.size === 1) {
        const suggested = siblingTypes[0]
        if (suggested && noteTypeOptions.some((nt) => nt.id === suggested)) {
          setSelectedNoteTypeId(suggested)
          setAutoSelectBadge(true)
          return
        }
      }
    }
    setAutoSelectBadge(false)
  }

  // Parse mutation
  const parseMutation = useMutation({
    mutationFn: async (uploadedFile: File) => {
      const formData = new FormData()
      formData.append('file', uploadedFile)
      formData.append('note_type_id', selectedNoteTypeId)
      formData.append('delimiter_mode', delimiterMode)
      formData.append('custom_delimiter', customDelimiter)
      formData.append('has_header', hasHeader ? '1' : '0')

      return apiRequest<ParseResponse>('/api/flashcards/import/parse', {
        method: 'POST',
        body: formData,
      })
    },
    onSuccess: (data, uploadedFile) => {
      setToken(data.token)
      setColumns(data.columns)
      setPreviewRows(data.preview_rows)
      setParseWarnings(data.warnings)
      setReport(null)
      setHasEstimated(false)
      setExecutionDone(false)

      if (data.suggested_mapping) {
        setMapping(data.suggested_mapping)
      }

      setParseMeta({
        filename: uploadedFile.name,
        totalRows: data.total_rows,
        columnCount: data.column_count,
        delimiterLabel: data.delimiter === '\t' ? 'tab' : data.delimiter,
      })

      toast.success('Parse file thành công')
    },
    onError: (err: Error) => {
      toast.error('Lỗi parse file', { description: err.message })
    },
  })

  // Estimate mutation
  const estimateMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        token,
        note_type_id: selectedNoteTypeId,
        target_deck_id: selectedDeckId ? Number(selectedDeckId) : null,
        import_mode: importMode,
        uniqueness_fields: uniquenessFields,
        mapping,
        dont_overwrite_empty: dontOverwriteEmpty,
        confirm_column_mismatch: confirmColumnMismatch || parseWarnings.length > 0,
      }
      return appApi.mutate<ImportReport>('/flashcards/import/estimate', 'POST', payload)
    },
    onSuccess: (data) => {
      setReport(data)
      setHasEstimated(true)
      setExecutionDone(false)
      const summary = data.summary
      if (summary.errors > 0) {
        toast.warning(`Ước lượng hoàn tất: ${summary.errors} dòng lỗi.`)
      } else {
        toast.success('Ước lượng thành công. Đã sẵn sàng thực thi import.')
      }
    },
    onError: (err: Error) => {
      toast.error('Ước lượng thất bại', { description: err.message })
    },
  })

  // Execute mutation
  const executeMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        token,
        note_type_id: selectedNoteTypeId,
        target_deck_id: selectedDeckId ? Number(selectedDeckId) : null,
        import_mode: importMode,
        uniqueness_fields: uniquenessFields,
        mapping,
        dont_overwrite_empty: dontOverwriteEmpty,
        confirm_column_mismatch: confirmColumnMismatch || parseWarnings.length > 0,
      }
      return appApi.mutate<ImportReport>('/flashcards/import/execute', 'POST', payload)
    },
    onSuccess: (data) => {
      setReport(data)
      setExecutionDone(true)
      const s = data.summary
      toast.success(`Import hoàn tất! Thêm mới: ${s.inserted}, Cập nhật: ${s.updated}, Bỏ qua: ${s.skipped}.`)
    },
    onError: (err: Error) => {
      toast.error('Thực thi import thất bại', { description: err.message })
    },
  })

  const checkDeckEmptyAndConfirm = () => {
    if (!warnOnNonEmptyDeck || !selectedDeckId) return true

    const targetDeck = deckOptions.find((d) => String(d.id) === selectedDeckId)
    const notesCount = targetDeck ? Number(targetDeck.notes_count || 0) : 0
    if (notesCount > 0) {
      const deckName = targetDeck ? targetDeck.path || targetDeck.name : 'Deck được chọn'
      return window.confirm(
        `Cảnh báo: Deck "${deckName}" hiện đang chứa ${notesCount} thẻ.\n\n` +
        `Bạn có chắc chắn muốn nạp thẻ mới vào deck này thay vì tạo một deck mới không?\n` +
        `Điều này có thể làm ghi đè hoặc thay đổi dữ liệu thẻ hiện có.`
      )
    }
    return true
  }

  const handleEstimate = () => {
    if (checkDeckEmptyAndConfirm()) {
      estimateMutation.mutate()
    }
  }

  const handleExecute = () => {
    if (checkDeckEmptyAndConfirm()) {
      executeMutation.mutate()
    }
  }

  const handleFileSelect = (selectedFile: File) => {
    setFile(selectedFile)
    const ext = selectedFile.name.split('.').pop()?.toLowerCase()
    if (ext === 'tsv') {
      setDelimiterMode('tsv')
    } else if (ext === 'csv') {
      setDelimiterMode('csv')
    }
    parseMutation.mutate(selectedFile)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0])
    }
  }

  let currentStep = 1
  if (token) currentStep = 2
  if (token && fields.length > 0) currentStep = 3
  if (hasEstimated || executionDone) currentStep = 4

  return {
    selectedDeckId,
    setSelectedDeckId,
    handleDeckChange,
    selectedNoteTypeId,
    setSelectedNoteTypeId,
    autoSelectBadge,
    file,
    setFile,
    isDragOver,
    setIsDragOver,
    delimiterMode,
    setDelimiterMode,
    customDelimiter,
    setCustomDelimiter,
    hasHeader,
    setHasHeader,
    token,
    setToken,
    columns,
    setColumns,
    previewRows,
    setPreviewRows,
    parseWarnings,
    setParseWarnings,
    parseMeta,
    setParseMeta,
    mapping,
    setMapping,
    importMode,
    setImportMode,
    dontOverwriteEmpty,
    setDontOverwriteEmpty,
    uniquenessFields,
    setUniquenessFields,
    confirmColumnMismatch,
    setConfirmColumnMismatch,
    report,
    setReport,
    hasEstimated,
    setHasEstimated,
    executionDone,
    setExecutionDone,
    warnOnNonEmptyDeck,
    handleWarnOnNonEmptyDeckChange,
    optionsQuery,
    parseMutation,
    estimateMutation,
    executeMutation,
    handleEstimate,
    handleExecute,
    handleFileSelect,
    handleDrop,
    currentStep,
    deckOptions,
    noteTypeOptions,
    currentNoteType,
    fields,
    fileInputRef,
    noteTypeSelectId,
    delimiterModeSelectId,
    customDelimiterInputId,
    columnMismatchConfirmId,
    dontOverwriteEmptyId,
  }
}
