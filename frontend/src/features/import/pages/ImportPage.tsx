import { useState, useEffect, useRef, useId } from 'react'
import {
  UploadCloud,
  FileSpreadsheet,
  Columns,
  Sparkles,
  ArrowRightLeft,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Loader2,
  FileText,
  Table as TableIcon,
  Filter,
  Layers,
  Check,
  Zap,
} from 'lucide-react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { apiRequest } from '@/shared/api/client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Checkbox } from '@/components/ui/checkbox'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type DeckOption = {
  id: number
  name: string
  path: string
  note_type_id?: string | null
  parent_id?: number | null
}

type NoteField = {
  id: string
  name: string
  position: number
  required: boolean
  field_type: string
}

type NoteTypeOption = {
  id: string
  name: string
  fields: NoteField[]
}

type ImportOptionsResponse = {
  deck_options: DeckOption[]
  note_type_options: NoteTypeOption[]
  initial_deck_id: number | null
  initial_note_type_id: string | null
  uniqueness_defaults: Record<string, string[]>
}

type ParsedColumn = {
  index: number
  name: string
  display: string
}

type ParseResponse = {
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

type FieldMapping = {
  source_type: 'column' | 'ignore' | 'constant'
  column_index: number | null
  constant_value: string
}

type ReportSummary = {
  total_rows: number
  valid_rows: number
  inserted: number
  updated: number
  skipped: number
  unchanged: number
  errors: number
}

type IssueItem = {
  kind: string
  row: number
  reason: string
  message: string
}

type ImportReport = {
  summary: ReportSummary
  issues: IssueItem[]
}

export function ImportPage() {
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

  // Generate unique form control IDs
  const targetDeckSelectId = useId()
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
  const fields = currentNoteType?.fields || []

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
  }, [selectedNoteTypeId, optionsQuery.data])

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

      return apiRequest<ParseResponse>('/api/v1/flashcards/import/parse', {
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

  // Calculate current active wizard step
  let currentStep = 1
  if (token) currentStep = 2
  if (token && fields.length > 0) currentStep = 3
  if (hasEstimated || executionDone) currentStep = 4

  if (optionsQuery.isPending) return <PageLoading label="Đang tải cấu hình import…" />
  if (optionsQuery.error) return <Page><PageError error={optionsQuery.error} /></Page>

  return (
    <Page className="w-full max-w-6xl px-4 lg:px-8 py-3 space-y-6">
      <PageHeader
        title="Import Note & Thẻ Flashcard"
        description="Nhập dữ liệu flashcard hàng loạt từ tệp CSV, TSV hoặc định dạng phân tách tùy chỉnh với quy trình rà soát an toàn."
      />

      {/* Modern Stepper Indicator */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { step: 1, label: '1. Đích & Thẻ', desc: 'Chọn Deck & NoteType', icon: Layers },
          { step: 2, label: '2. Tải & Parse', desc: 'Kéo thả file dữ liệu', icon: UploadCloud },
          { step: 3, label: '3. Ánh xạ Cột', desc: 'Ghép cột & Chế độ ghi', icon: ArrowRightLeft },
          { step: 4, label: '4. Thực thi', desc: 'Ước lượng & Nạp thẻ', icon: Zap },
        ].map((s) => {
          const IconComp = s.icon
          const isActive = currentStep === s.step
          const isDone = currentStep > s.step

          return (
            <div
              key={s.step}
              className={`p-3 rounded-2xl border transition-all flex items-center gap-3 ${
                isActive
                  ? 'border-primary bg-primary/5 shadow-sm'
                  : isDone
                  ? 'border-border/80 bg-card/60 text-muted-foreground'
                  : 'border-border/40 bg-card/30 opacity-60'
              }`}
            >
              <div
                className={`size-9 rounded-xl flex items-center justify-center text-xs font-bold shrink-0 ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : isDone
                    ? 'bg-primary/15 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {isDone ? <Check className="size-4" /> : <IconComp className="size-4" />}
              </div>
              <div className="min-w-0">
                <div className={`text-xs font-bold truncate ${isActive ? 'text-primary' : 'text-foreground'}`}>
                  {s.label}
                </div>
                <div className="text-[11px] text-muted-foreground truncate">{s.desc}</div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Step 1 Card: Target Deck & Note Type */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Layers className="size-4 text-primary" />
            Cấu hình Deck &amp; Loại Note
          </CardTitle>
          <CardDescription className="text-xs">
            Xác định Deck lưu trữ thẻ và cấu trúc NoteType phù hợp với file import.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label htmlFor={targetDeckSelectId} className="font-medium text-xs">
                Deck đích
              </Label>
              <NativeSelect
                id={targetDeckSelectId}
                value={selectedDeckId}
                onChange={(e) => handleDeckChange(e.target.value)}
              >
                {deckOptions.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.path || d.name}
                  </option>
                ))}
              </NativeSelect>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor={noteTypeSelectId} className="font-medium text-xs">
                  Loại note
                </Label>
                {autoSelectBadge && (
                  <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 text-[11px] font-medium gap-1">
                    <Sparkles className="size-3" /> Tự động khớp theo deck
                  </Badge>
                )}
              </div>
              <NativeSelect
                id={noteTypeSelectId}
                value={selectedNoteTypeId}
                onChange={(e) => {
                  setSelectedNoteTypeId(e.target.value)
                  setAutoSelectBadge(false)
                }}
              >
                {noteTypeOptions.map((nt) => (
                  <option key={nt.id} value={nt.id}>
                    {nt.name}
                  </option>
                ))}
              </NativeSelect>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Step 2 Card: File Upload & Parse */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <UploadCloud className="size-4 text-primary" />
                Tải file &amp; Parse dữ liệu
              </CardTitle>
              <CardDescription className="text-xs">
                Chọn tệp CSV, TSV hoặc định dạng có phân tách tự định nghĩa.
              </CardDescription>
            </div>
            <Badge variant={token ? 'default' : 'secondary'} className="text-xs">
              {token ? 'Parse thành công' : 'Chờ tải file'}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-4 space-y-4">
          <div
            className={`border-2 border-dashed rounded-2xl p-6 text-center cursor-pointer transition-all ${
              isDragOver
                ? 'border-primary bg-primary/5 shadow-inner'
                : 'border-border/80 hover:border-primary/40 bg-muted/20 hover:bg-muted/30'
            }`}
            onDragOver={(e) => {
              e.preventDefault()
              setIsDragOver(true)
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.tsv,.txt"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
            />
            <FileSpreadsheet className="size-10 mx-auto text-primary mb-2 opacity-85" />
            <p className="text-sm font-semibold text-foreground">
              {file ? file.name : 'Kéo thả file vào đây hoặc nhấp để chọn tệp'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Định dạng hỗ trợ: CSV, TSV, TXT (Tối đa 50MB)
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
            <div className="space-y-1.5">
              <Label htmlFor={delimiterModeSelectId} className="text-xs font-medium">Ký tự phân tách</Label>
              <NativeSelect
                id={delimiterModeSelectId}
                value={delimiterMode}
                onChange={(e) => setDelimiterMode(e.target.value as 'csv' | 'tsv' | 'custom')}
              >
                <option value="csv">CSV (,)</option>
                <option value="tsv">TSV (tab)</option>
                <option value="custom">Tùy chỉnh</option>
              </NativeSelect>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={customDelimiterInputId} className="text-xs font-medium">Ký tự tùy chỉnh</Label>
              <Input
                id={customDelimiterInputId}
                maxLength={1}
                placeholder="|"
                disabled={delimiterMode !== 'custom'}
                value={customDelimiter}
                onChange={(e) => setCustomDelimiter(e.target.value)}
              />
            </div>

            <div>
              <Button
                variant="outline"
                className="w-full font-medium"
                disabled={!file || parseMutation.isPending}
                onClick={() => file && parseMutation.mutate(file)}
              >
                {parseMutation.isPending ? <Loader2 className="size-4 animate-spin mr-1.5" /> : <RotateCcw className="size-4 mr-1.5" />}
                Parse lại
              </Button>
            </div>
          </div>

          {parseMeta && (
            <div className="flex flex-wrap gap-2 text-xs pt-1">
              <Badge variant="secondary"><FileText className="size-3 mr-1" /> {parseMeta.filename}</Badge>
              <Badge variant="secondary"><TableIcon className="size-3 mr-1" /> {parseMeta.totalRows} dòng</Badge>
              <Badge variant="secondary"><Columns className="size-3 mr-1" /> {parseMeta.columnCount} cột</Badge>
              <Badge variant="secondary"><Filter className="size-3 mr-1" /> Ký tự: {parseMeta.delimiterLabel}</Badge>
            </div>
          )}

          {/* Preview Table */}
          {columns.length > 0 && (
            <div className="border border-border/80 rounded-2xl overflow-hidden mt-3">
              <div className="bg-muted/40 p-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <div>
                  <h4 className="text-xs font-bold text-foreground">Xem trước dữ liệu tệp</h4>
                  <p className="text-[11px] text-muted-foreground">Hiển thị các dòng mẫu đã phân tách cột.</p>
                </div>
                <div className="flex items-center gap-4 text-xs font-medium">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="headerMode"
                      checked={hasHeader}
                      onChange={() => setHasHeader(true)}
                    />
                    <span>Có tiêu đề</span>
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="headerMode"
                      checked={!hasHeader}
                      onChange={() => setHasHeader(false)}
                    />
                    <span>Không tiêu đề</span>
                  </label>
                </div>
              </div>

              <div className="overflow-x-auto">
                <Table className="text-xs">
                  <TableHeader className="bg-muted/30">
                    <TableRow>
                      {columns.map((col) => (
                        <TableHead key={col.index} className="min-w-36 font-semibold text-foreground">
                          {col.display || `Cột ${col.index + 1}`}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {previewRows.map((row, rIdx) => (
                      <TableRow key={rIdx}>
                        {columns.map((col) => (
                          <TableCell key={col.index} className="max-w-48 truncate text-muted-foreground">
                            {row[col.index] || ''}
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Step 3 Card: Column Mapping */}
      {fields.length > 0 && token && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <ArrowRightLeft className="size-4 text-primary" />
              Ánh xạ Cột -&gt; Trường Note
            </CardTitle>
            <CardDescription className="text-xs">
              Ghép các cột trong tệp vào từng trường tương ứng của loại thẻ.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="font-semibold">Trường Note</TableHead>
                  <TableHead className="font-semibold">Nguồn dữ liệu</TableHead>
                  <TableHead className="font-semibold">Giá trị mẫu / Cố định</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {fields.map((field) => {
                  const currentMap = mapping[field.name] || { source_type: 'ignore', column_index: null, constant_value: '' }
                  const selectVal =
                    currentMap.source_type === 'column' && currentMap.column_index !== null
                      ? `col:${currentMap.column_index}`
                      : currentMap.source_type

                  return (
                    <TableRow key={field.name}>
                      <TableCell className="font-medium text-foreground">
                        {field.name} {field.required && <span className="text-destructive">*</span>}
                        <div className="text-[11px] text-muted-foreground font-normal">{field.field_type}</div>
                      </TableCell>
                      <TableCell className="w-56">
                        <NativeSelect
                          value={selectVal}
                          onChange={(e) => {
                            const val = e.target.value
                            if (val === 'ignore') {
                              setMapping((prev) => ({ ...prev, [field.name]: { source_type: 'ignore', column_index: null, constant_value: '' } }))
                            } else if (val === 'constant') {
                              setMapping((prev) => ({ ...prev, [field.name]: { source_type: 'constant', column_index: null, constant_value: currentMap.constant_value || '' } }))
                            } else if (val.startsWith('col:')) {
                              const idx = Number(val.replace('col:', ''))
                              setMapping((prev) => ({ ...prev, [field.name]: { source_type: 'column', column_index: idx, constant_value: '' } }))
                            }
                          }}
                        >
                          <option value="ignore">Bỏ qua</option>
                          <option value="constant">Giá trị cố định</option>
                          {columns.map((c) => (
                            <option key={c.index} value={`col:${c.index}`}>
                              Cột {c.index + 1} - {c.display}
                            </option>
                          ))}
                        </NativeSelect>
                      </TableCell>
                      <TableCell>
                        {currentMap.source_type === 'constant' ? (
                          <Input
                            placeholder="Nhập giá trị cố định…"
                            value={currentMap.constant_value}
                            onChange={(e) => {
                              const val = e.target.value
                              setMapping((prev) => ({
                                ...prev,
                                [field.name]: { ...currentMap, constant_value: val },
                              }))
                            }}
                          />
                        ) : currentMap.source_type === 'column' && currentMap.column_index !== null ? (
                          <span className="text-xs text-muted-foreground italic">
                            {previewRows[0]?.[currentMap.column_index] || '(Rỗng)'}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Step 4 Card: Import Mode & Uniqueness Keys */}
      {token && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Sliders className="size-4 text-primary" />
              Chế độ Import &amp; Khóa đối chiếu
            </CardTitle>
            <CardDescription className="text-xs">
              Thiết lập quy tắc ghi đè dữ liệu và nhận diện bản ghi đã có.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <Label className="font-semibold text-xs">Chế độ ghi đè</Label>
                <div className="space-y-2 text-xs font-medium">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="importMode"
                      checked={importMode === 'insert_only'}
                      onChange={() => setImportMode('insert_only')}
                    />
                    <span>Chỉ thêm mới (Insert Only)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="importMode"
                      checked={importMode === 'update_only'}
                      onChange={() => setImportMode('update_only')}
                    />
                    <span>Chỉ cập nhật (Update Only)</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="importMode"
                      checked={importMode === 'upsert'}
                      onChange={() => setImportMode('upsert')}
                    />
                    <span>Thêm mới + Cập nhật (Upsert)</span>
                  </label>
                </div>

                <div className="flex items-center space-x-2 pt-2">
                  <Checkbox
                    id={dontOverwriteEmptyId}
                    checked={dontOverwriteEmpty}
                    onCheckedChange={(checked) => setDontOverwriteEmpty(Boolean(checked))}
                  />
                  <Label htmlFor={dontOverwriteEmptyId} className="text-xs font-medium cursor-pointer">
                    Không ghi đè giá trị rỗng (An toàn dữ liệu)
                  </Label>
                </div>
              </div>

              <div className="space-y-3">
                <Label className="font-semibold text-xs">Khóa đối chiếu (Trường so khớp trùng lặp)</Label>
                <p className="text-xs text-muted-foreground">Chọn trường để hệ thống nhận diện bản ghi đã tồn tại.</p>
                <div className="border border-border/80 rounded-xl p-3 max-h-44 overflow-y-auto space-y-2 bg-muted/20">
                  {fields.map((f) => {
                    const isChecked = uniquenessFields.includes(f.name)
                    return (
                      <div key={f.name} className="flex items-center space-x-2">
                        <Checkbox
                          id={`uniq-${f.name}`}
                          checked={isChecked}
                          onCheckedChange={(checked) => {
                            if (checked) {
                              setUniquenessFields((prev) => [...prev, f.name])
                            } else {
                              setUniquenessFields((prev) => prev.filter((item) => item !== f.name))
                            }
                          }}
                        />
                        <Label htmlFor={`uniq-${f.name}`} className="text-xs font-medium cursor-pointer">
                          {f.name}
                        </Label>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {parseWarnings.length > 0 && (
              <div className="flex items-center space-x-2 pt-2 text-destructive">
                <Checkbox
                  id={columnMismatchConfirmId}
                  checked={confirmColumnMismatch}
                  onCheckedChange={(checked) => setConfirmColumnMismatch(Boolean(checked))}
                />
                <Label htmlFor={columnMismatchConfirmId} className="text-xs font-semibold cursor-pointer text-destructive">
                  Tôi xác nhận tiếp tục dù số cột không khớp với số trường của NoteType
                </Label>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Step 5 Card: Execution & Report */}
      {token && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <CheckCircle2 className="size-4 text-primary" />
              Rà soát &amp; Thực thi Import
            </CardTitle>
            <CardDescription className="text-xs">
              Chạy ước lượng thử nghiệm hoặc tiến hành nạp dữ liệu chính thức.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4 space-y-4">
            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                disabled={estimateMutation.isPending || executeMutation.isPending}
                onClick={() => estimateMutation.mutate()}
                className="font-medium"
              >
                {estimateMutation.isPending ? <Loader2 className="size-4 animate-spin mr-1.5" /> : null}
                1. Ước lượng thử nghiệm
              </Button>

              <Button
                disabled={!hasEstimated || estimateMutation.isPending || executeMutation.isPending}
                onClick={() => executeMutation.mutate()}
                className="font-semibold shadow-sm"
              >
                {executeMutation.isPending ? <Loader2 className="size-4 animate-spin mr-1.5" /> : null}
                2. Thực thi import
              </Button>
            </div>

            {(estimateMutation.isPending || executeMutation.isPending) && (
              <div className="space-y-1.5">
                <Progress value={85} className="h-2" />
                <p className="text-xs text-muted-foreground text-center">Đang xử lý dữ liệu import…</p>
              </div>
            )}

            {report && (
              <div className="space-y-4 pt-2">
                <Alert className={executionDone ? 'border-primary/40 bg-primary/5' : 'border-border/80 bg-muted/30'}>
                  {executionDone ? <CheckCircle2 className="size-5 text-primary" /> : <AlertTriangle className="size-5 text-muted-foreground" />}
                  <AlertTitle className="font-bold text-foreground">
                    {executionDone ? 'Thực thi Import thành công!' : 'Kết quả ước lượng trước import'}
                  </AlertTitle>
                  <AlertDescription className="mt-2 text-xs">
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-medium">
                      <div>Tổng dòng: {report.summary.total_rows}</div>
                      <div>Dòng hợp lệ: {report.summary.valid_rows}</div>
                      <div className="text-primary font-bold">Thêm mới: {report.summary.inserted}</div>
                      <div className="font-semibold">Cập nhật: {report.summary.updated}</div>
                      <div className="text-muted-foreground">Bỏ qua: {report.summary.skipped}</div>
                      <div className="text-destructive font-semibold">Lỗi: {report.summary.errors}</div>
                    </div>
                  </AlertDescription>
                </Alert>

                {report.issues && report.issues.length > 0 && (
                  <div className="border border-border/80 rounded-xl overflow-hidden">
                    <div className="bg-destructive/10 p-3 text-destructive font-semibold text-xs">
                      Báo cáo chi tiết dòng gặp sự cố ({report.issues.length} vấn đề)
                    </div>
                    <Table className="text-xs">
                      <TableHeader className="bg-muted/40">
                        <TableRow>
                          <TableHead className="w-16 font-semibold">Dòng</TableHead>
                          <TableHead className="w-24 font-semibold">Loại</TableHead>
                          <TableHead className="w-36 font-semibold">Lý do</TableHead>
                          <TableHead className="font-semibold">Chi tiết</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {report.issues.map((issue, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="font-mono">{issue.row}</TableCell>
                            <TableCell><Badge variant="outline">{issue.kind}</Badge></TableCell>
                            <TableCell className="font-medium">{issue.reason}</TableCell>
                            <TableCell className="text-muted-foreground">{issue.message}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </Page>
  )
}
