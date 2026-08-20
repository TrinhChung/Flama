import { useState, useEffect, useRef, useId, useMemo } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { apiRequest } from '@/shared/api/client'
import type {
  BatchFileMeta,
  BatchFileConfig,
  BatchParseResponse,
  BatchImportReport,
} from '../api'

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

  const deckIdQueryParam = searchParams.get('deck_id')

  const [selectedDeckId, setSelectedDeckId] = useState<string>(() => deckIdQueryParam || '')
  const [selectedNoteTypeId, setSelectedNoteTypeId] = useState<string>('')
  const [autoSelectBadge, setAutoSelectBadge] = useState<boolean>(false)

  // Files State (Single & Batch)
  const [files, setFiles] = useState<File[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [isDragOver, setIsDragOver] = useState<boolean>(false)
  const [delimiterMode, setDelimiterMode] = useState<'csv' | 'tsv' | 'custom'>('csv')
  const [customDelimiter, setCustomDelimiter] = useState<string>('')
  const [hasHeader, setHasHeader] = useState<boolean>(true)

  // Batch Naming State
  const [namingMode, setNamingMode] = useState<'auto' | 'filename' | 'custom'>('auto')
  const [customPattern, setCustomPattern] = useState<string>('Bài {n}')
  const [batchFiles, setBatchFiles] = useState<BatchFileMeta[]>([])
  const [batchFileConfigs, setBatchFileConfigs] = useState<Record<string, BatchFileConfig>>({})

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
  const [batchReport, setBatchReport] = useState<BatchImportReport | null>(null)
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

  const isBatchMode = files.length > 1

  // Load import initial options
  const optionsQuery = useQuery({
    queryKey: ['flashcard-import-options', deckIdQueryParam],
    queryFn: () => appApi.get<ImportOptionsResponse>('/flashcards/import/options', { deck_id: deckIdQueryParam }),
  })

  useEffect(() => {
    if (optionsQuery.data) {
      const data = optionsQuery.data
      if (deckIdQueryParam && data.deck_options?.some((d) => String(d.id) === deckIdQueryParam)) {
        setSelectedDeckId(deckIdQueryParam)
      } else if (data.initial_deck_id) {
        setSelectedDeckId(String(data.initial_deck_id))
      }
      if (data.initial_note_type_id) {
        setSelectedNoteTypeId(data.initial_note_type_id)
      }
    }
  }, [optionsQuery.data, deckIdQueryParam])

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

  // Single file parse mutation
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
      setBatchReport(null)
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

  // Batch parse mutation
  const batchParseMutation = useMutation({
    mutationFn: async (uploadedFiles: File[]) => {
      const formData = new FormData()
      uploadedFiles.forEach((f) => formData.append('files', f))
      formData.append('parent_deck_id', selectedDeckId || '')
      formData.append('note_type_id', selectedNoteTypeId)
      formData.append('delimiter_mode', delimiterMode)
      formData.append('custom_delimiter', customDelimiter)
      formData.append('has_header', hasHeader ? '1' : '0')
      formData.append('naming_mode', namingMode)
      if (namingMode === 'custom' && customPattern) {
        formData.append('custom_pattern', customPattern)
      }

      return apiRequest<BatchParseResponse>('/api/flashcards/import/batch/parse', {
        method: 'POST',
        body: formData,
      })
    },
    onSuccess: (data, uploadedFiles) => {
      setToken(data.token)
      setBatchFiles(data.files)
      setColumns(data.sample_columns)
      setReport(null)
      setBatchReport(null)
      setHasEstimated(false)
      setExecutionDone(false)

      const initialConfigs: Record<string, BatchFileConfig> = {}
      data.files.forEach((f) => {
        initialConfigs[f.file_id] = {
          file_id: f.file_id,
          target_deck_name: f.suggested_deck_name,
          action: f.collision.suggested_action || 'create_new',
          target_deck_id: f.collision.existing_deck_id,
        }
      })
      setBatchFileConfigs(initialConfigs)

      if (data.suggested_mapping) {
        setMapping(data.suggested_mapping)
      }

      const totalRows = data.files.reduce((acc, f) => acc + f.total_rows, 0)
      setParseMeta({
        filename: `${uploadedFiles.length} tệp (${uploadedFiles[0]?.name}...)`,
        totalRows,
        columnCount: data.sample_columns.length,
        delimiterLabel: delimiterMode,
      })

      toast.success(`Đã phân tích ${uploadedFiles.length} tệp bài học thành công!`)
    },
    onError: (err: Error) => {
      toast.error('Lỗi phân tích nhiều file', { description: err.message })
    },
  })

  // Single Estimate mutation
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

  // Batch Estimate mutation
  const batchEstimateMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        token,
        parent_deck_id: selectedDeckId ? Number(selectedDeckId) : null,
        note_type_id: selectedNoteTypeId,
        import_mode: importMode,
        uniqueness_fields:
          uniquenessFields.length > 0 ? uniquenessFields : fields.length > 0 ? [fields[0].name] : [],
        mapping,
        dont_overwrite_empty: dontOverwriteEmpty,
        confirm_column_mismatch: true,
        file_configs: Object.values(batchFileConfigs),
      }
      return appApi.mutate<BatchImportReport>('/flashcards/import/batch/estimate', 'POST', payload)
    },
    onSuccess: (data) => {
      setBatchReport(data)
      setHasEstimated(true)
      setExecutionDone(false)
      const s = data.overall_summary
      if (s.errors > 0) {
        toast.warning(`Ước lượng hoàn tất: ${s.errors} lỗi, ${s.inserted} thẻ mới sẽ thêm.`)
      } else {
        toast.success(`Ước lượng thành công: Tạo ${s.created_decks} bài mới, nạp ${s.inserted} thẻ.`)
      }
    },
    onError: (err: Error) => {
      toast.error('Ước lượng hàng loạt thất bại', { description: err.message })
    },
  })

  // Single Execute mutation
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

  // Batch Execute mutation
  const batchExecuteMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        token,
        parent_deck_id: selectedDeckId ? Number(selectedDeckId) : null,
        note_type_id: selectedNoteTypeId,
        import_mode: importMode,
        uniqueness_fields:
          uniquenessFields.length > 0 ? uniquenessFields : fields.length > 0 ? [fields[0].name] : [],
        mapping,
        dont_overwrite_empty: dontOverwriteEmpty,
        confirm_column_mismatch: true,
        file_configs: Object.values(batchFileConfigs),
      }
      return appApi.mutate<BatchImportReport>('/flashcards/import/batch/execute', 'POST', payload)
    },

    onSuccess: (data) => {
      setBatchReport(data)
      setExecutionDone(true)
      const s = data.overall_summary
      toast.success(`Import thành công ${s.processed_files} bài học! Thêm mới: ${s.inserted} thẻ, Tạo mới: ${s.created_decks} deck con.`)
    },
    onError: (err: Error) => {
      toast.error('Thực thi import hàng loạt thất bại', { description: err.message })
    },
  })

  const updateBatchFileConfig = (fileId: string, patch: Partial<BatchFileConfig>) => {
    setBatchFileConfigs((prev) => ({
      ...prev,
      [fileId]: {
        ...prev[fileId],
        ...patch,
      },
    }))
  }

  const checkDeckEmptyAndConfirm = () => {
    if (isBatchMode) return true
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
      if (isBatchMode) {
        batchEstimateMutation.mutate()
      } else {
        estimateMutation.mutate()
      }
    }
  }

  const handleExecute = () => {
    if (checkDeckEmptyAndConfirm()) {
      if (isBatchMode) {
        batchExecuteMutation.mutate()
      } else {
        executeMutation.mutate()
      }
    }
  }

  const handleFilesSelect = (selectedFiles: FileList | File[]) => {
    const list = Array.from(selectedFiles)
    if (!list.length) return

    setFiles(list)
    const firstFile = list[0]
    setFile(firstFile)

    const ext = firstFile.name.split('.').pop()?.toLowerCase()
    if (ext === 'tsv') {
      setDelimiterMode('tsv')
    } else if (ext === 'csv') {
      setDelimiterMode('csv')
    }

    if (list.length > 1) {
      batchParseMutation.mutate(list)
    } else {
      parseMutation.mutate(firstFile)
    }
  }

  const handleApplyNamingRule = () => {
    if (files.length > 1) {
      batchParseMutation.mutate(files)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelect(e.dataTransfer.files)
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
    files,
    setFiles,
    isBatchMode,
    batchFiles,
    batchFileConfigs,
    updateBatchFileConfig,
    namingMode,
    setNamingMode,
    customPattern,
    setCustomPattern,
    handleApplyNamingRule,
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
    batchReport,
    hasEstimated,
    setHasEstimated,
    executionDone,
    setExecutionDone,
    warnOnNonEmptyDeck,
    handleWarnOnNonEmptyDeckChange,
    optionsQuery,
    parseMutation,
    batchParseMutation,
    estimateMutation,
    batchEstimateMutation,
    executeMutation,
    batchExecuteMutation,
    handleEstimate,
    handleExecute,
    handleFilesSelect,
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
