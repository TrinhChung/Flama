import React, { useState, useEffect, useId, useMemo } from 'react'
import {
  RefreshCw,
  NotebookTabs,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Zap,
  Wifi,
  WifiOff,
  Search,
  Code2,
  Copy,
  Check,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import type { AnkiConnectStatus } from '@/lib/ankiConnectClient'
import { ankiConnectClient } from '@/lib/ankiConnectClient'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'

interface FlamaFieldDef {
  id: string
  name: string
  field_type: string
}

interface FlamaNoteTypeOption {
  id: string
  name: string
  fields: FlamaFieldDef[]
}

interface AnkiTemplateInfo {
  name: string
  front: string
  back: string
}

interface AnkiModelDetail {
  name: string // Original Anki Model Name
  fields: string[]
  css: string
  templates: AnkiTemplateInfo[]
  existingFlamaId?: string
}

interface AnkiNoteTypeSyncTabProps {
  noteTypeOptions: FlamaNoteTypeOption[]
}

function inferFieldType(fieldName: string): 'text' | 'image' | 'audio' | 'richtext' {
  const lower = fieldName.toLowerCase()
  if (lower.includes('audio') || lower.includes('sound') || lower.includes('voice')) {
    return 'audio'
  }
  if (lower.includes('image') || lower.includes('pic') || lower.includes('photo') || lower.includes('img')) {
    return 'image'
  }
  if (lower.includes('back') || lower.includes('meaning') || lower.includes('example') || lower.includes('definition')) {
    return 'richtext'
  }
  return 'text'
}

type PreviewResponse = {
  front_html?: string
  back_html?: string
  front_renderer_payload?: unknown
  back_renderer_payload?: unknown
}


export const AnkiNoteTypeSyncTab: React.FC<AnkiNoteTypeSyncTabProps> = ({ noteTypeOptions }) => {
  const queryClient = useQueryClient()

  // Connection state
  const [endpoint, setEndpoint] = useState('http://127.0.0.1:8765')
  const [connectionStatus, setConnectionStatus] = useState<AnkiConnectStatus>('Anki is not running')
  const [ankiVersion, setAnkiVersion] = useState<number | null>(null)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [isCheckingConn, setIsCheckingConn] = useState(false)

  // Models State
  const [ankiModels, setAnkiModels] = useState<AnkiModelDetail[]>([])
  const [activeModelName, setActiveModelName] = useState<string | null>(null)
  const [selectedModelNames, setSelectedModelNames] = useState<string[]>([])
  const [targetActions, setTargetActions] = useState<Record<string, 'create_new' | 'ignore' | string>>({})
  const [customNames, setCustomNames] = useState<Record<string, string>>({})
  const [modelSearch, setModelSearch] = useState('')
  const [isLoadingModels, setIsLoadingModels] = useState(false)

  // Code Viewer & Live Preview State
  const [selectedTemplateIndex, setSelectedTemplateIndex] = useState(0)
  const [codeTab, setCodeTab] = useState<'front' | 'back' | 'css' | 'fields'>('front')
  const [previewSide, setPreviewSide] = useState<'front' | 'back'>('front')
  const [copiedTab, setCopiedTab] = useState<string | null>(null)

  const [previewResult, setPreviewResult] = useState<PreviewResponse | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [isPreviewLoading, setIsPreviewLoading] = useState(false)


  // Execution state
  const [isSyncing, setIsSyncing] = useState(false)
  const [showSyncModal, setShowSyncModal] = useState(false)
  const [syncLog, setSyncLog] = useState<string[]>([])
  const [syncReport, setSyncReport] = useState<{ successCount: number; errors: string[] } | null>(null)

  const endpointInputId = useId()

  const checkAnkiConnection = async () => {
    setIsCheckingConn(true)
    setConnectionError(null)
    const result = await ankiConnectClient.checkConnection(endpoint)
    setConnectionStatus(result.status)
    if (result.version) setAnkiVersion(result.version)
    if (result.error) setConnectionError(result.error)

    if (result.status === 'Connected') {
      await loadAnkiModels()
    }
    setIsCheckingConn(false)
  }

  const loadAnkiModels = async () => {
    setIsLoadingModels(true)
    try {
      const modelNames = await ankiConnectClient.getModelNames(endpoint)
      const details: AnkiModelDetail[] = []
      const initialActions: Record<string, string> = {}
      const initialCustomNames: Record<string, string> = {}

      for (const name of modelNames) {
        const fields = await ankiConnectClient.getModelFieldNames(name, endpoint)
        const styling = await ankiConnectClient.getModelStyling(name, endpoint)
        const templates = await ankiConnectClient.getModelTemplates(name, endpoint)

        const matchedFlama = noteTypeOptions.find(
          (nt) => nt.name.toLowerCase() === name.toLowerCase()
        )

        details.push({
          name,
          fields,
          css: styling.css || '',
          templates: templates || [{ name: 'Card 1', front: '{{Front}}', back: '{{FrontSide}}<hr>{{Back}}' }],
          existingFlamaId: matchedFlama?.id,
        })

        initialActions[name] = matchedFlama ? matchedFlama.id : 'create_new'
        initialCustomNames[name] = name
      }

      setAnkiModels(details)
      setTargetActions(initialActions)
      setCustomNames(initialCustomNames)

      if (details.length > 0) {
        setActiveModelName(details[0].name)
      }
      setSelectedModelNames([])
    } catch (err: any) {
      setConnectionError(err.message || 'Không thể tải danh sách NoteType từ Anki.')
    }
    setIsLoadingModels(false)
  }

  useEffect(() => {
    checkAnkiConnection()
  }, [])

  const activeModelDetail = useMemo(
    () => ankiModels.find((m) => m.name === activeModelName) || null,
    [ankiModels, activeModelName]
  )

  const activeTemplate = useMemo(() => {
    if (!activeModelDetail || activeModelDetail.templates.length === 0) return null
    return activeModelDetail.templates[selectedTemplateIndex] || activeModelDetail.templates[0]
  }, [activeModelDetail, selectedTemplateIndex])

  // Fetch Live Preview from backend API with debouncing (300ms)
  useEffect(() => {
    if (!activeModelDetail || !activeTemplate) {
      setPreviewResult(null)
      return
    }
    let cancelled = false
    const timer = setTimeout(async () => {
      setIsPreviewLoading(true)
      setPreviewError(null)
      try {
        const res = await appApi.mutate<PreviewResponse>(
          '/note-types/preview',
          'POST',
          {
            front_html: activeTemplate.front,
            back_html: activeTemplate.back,
            shared_css: activeModelDetail.css,
            fields: activeModelDetail.fields,
          },
        )
        if (!cancelled) {
          setPreviewResult(res)
        }
      } catch (err: any) {
        if (!cancelled) {
          setPreviewResult(null)
          setPreviewError(err.message || 'Lỗi tải xem trước template.')
        }
      } finally {
        if (!cancelled) {
          setIsPreviewLoading(false)
        }
      }
    }, 300)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [activeModelDetail, activeTemplate, selectedTemplateIndex])


  const handleCopyCode = (text: string, tabName: string) => {
    void navigator.clipboard.writeText(text)
    setCopiedTab(tabName)
    setTimeout(() => setCopiedTab(null), 2000)
  }

  const handleSyncSelectedModels = async (modelsToSync: string[]) => {
    if (modelsToSync.length === 0) {
      alert('Vui lòng chọn ít nhất 1 NoteType để đồng bộ.')
      return
    }

    setIsSyncing(true)
    setShowSyncModal(true)
    setSyncReport(null)
    setSyncLog([])
    const logs: string[] = []
    const errors: string[] = []
    let successCount = 0

    for (const originalAnkiName of modelsToSync) {
      const modelDetail = ankiModels.find((m) => m.name === originalAnkiName)
      if (!modelDetail) continue

      const action = targetActions[originalAnkiName] || 'create_new'
      if (action === 'ignore') continue

      const customName = (customNames[originalAnkiName] || originalAnkiName).trim()

      logs.push(`[${originalAnkiName}] Đang đồng bộ cấu trúc (Tên Flama: "${customName}")...`)
      setSyncLog([...logs])

      try {
        let flamaNoteTypeId = action

        if (action === 'create_new') {
          const fieldDefsPayload = modelDetail.fields.map((fieldName, idx) => ({
            name: fieldName,
            field_type: inferFieldType(fieldName),
            position: idx,
            required: idx === 0,
            identity_role: idx === 0 ? 'primary' : null,
          }))

          const firstTmpl = modelDetail.templates[0]
          const templatePayload = firstTmpl
            ? {
                name: firstTmpl.name || 'Card 1',
                front_html: firstTmpl.front || `{{${modelDetail.fields[0] || 'Front'}}}`,
                back_html: firstTmpl.back || `{{FrontSide}}<hr id=answer>{{${modelDetail.fields[1] || 'Back'}}}`,
                shared_css: modelDetail.css || '',
              }
            : undefined

          const newTypeRes = await appApi.mutate<{ id: string; name: string }>('/note-types', 'POST', {
            name: customName,
            field_defs: fieldDefsPayload,
            template: templatePayload,
          })
          flamaNoteTypeId = newTypeRes.id
          logs.push(`✓ Đã tạo NoteType trên Flama: "${customName}" với ${modelDetail.fields.length} trường (ID: ${flamaNoteTypeId})`)
          setSyncLog([...logs])

          for (const fieldName of modelDetail.fields) {
            logs.push(`  + Trường "${fieldName}" (${inferFieldType(fieldName)})`)
          }
          if (firstTmpl) {
            logs.push(`  + Template Mặt trước & Mặt sau: "${firstTmpl.name || 'Card 1'}"`)
          }
          setSyncLog([...logs])

          if (modelDetail.templates.length > 1) {
            for (let tIdx = 1; tIdx < modelDetail.templates.length; tIdx++) {
              const tmpl = modelDetail.templates[tIdx]
              try {
                await appApi.mutate(`/note-types/${flamaNoteTypeId}/templates`, 'POST', {
                  name: tmpl.name || `Card ${tIdx + 1}`,
                  front_html: tmpl.front,
                  back_html: tmpl.back,
                  shared_css: modelDetail.css || '',
                })
                logs.push(`  + Template bổ sung: "${tmpl.name || `Card ${tIdx + 1}`}"`)
                setSyncLog([...logs])
              } catch (tmplErr) {
                console.warn('Lưu template bổ sung thất bại, tiếp tục...', tmplErr)
              }
            }
          }
        } else {
          // Sync into existing Flama NoteType
          const existingNT = await appApi.get<{
            id: string
            field_defs?: Array<{ name: string; identity_role?: string | null }>
          }>(`/note-types/${flamaNoteTypeId}`)
          const existingFields = existingNT.field_defs || []
          const existingNames = new Set(existingFields.map((f) => f.name.toLowerCase()))
          const hasPrimary = existingFields.some((f) => f.identity_role === 'primary')

          for (let idx = 0; idx < modelDetail.fields.length; idx++) {
            const fieldName = modelDetail.fields[idx]
            if (existingNames.has(fieldName.toLowerCase())) {
              logs.push(`  - Trường "${fieldName}" đã tồn tại trên Flama (bỏ qua)`)
              setSyncLog([...logs])
              continue
            }

            const fieldType = inferFieldType(fieldName)
            const shouldBePrimary = !hasPrimary && idx === 0

            await appApi.mutate(`/note-types/${flamaNoteTypeId}/fields`, 'POST', {
              name: fieldName,
              field_type: fieldType,
              required: shouldBePrimary,
              identity_role: shouldBePrimary ? 'primary' : null,
            })

            logs.push(`  + Trường mới "${fieldName}" (${fieldType})`)
            setSyncLog([...logs])
          }

          if (modelDetail.templates.length > 0) {
            for (const tmpl of modelDetail.templates) {
              try {
                await appApi.mutate(`/note-types/${flamaNoteTypeId}/templates`, 'POST', {
                  name: tmpl.name || 'Card 1',
                  front_html: tmpl.front,
                  back_html: tmpl.back,
                  shared_css: modelDetail.css || '',
                })
                logs.push(`  + Template Mặt trước & Mặt sau: "${tmpl.name || 'Card 1'}"`)
                setSyncLog([...logs])
              } catch (tmplErr) {
                console.warn('Lưu template thất bại, tiếp tục...', tmplErr)
              }
            }
          }
        }

        const mappingObj = {
          ankiModelName: originalAnkiName,
          customFlamaName: customName,
          flamaNoteTypeId,
          syncedAt: new Date().toISOString(),
        }
        localStorage.setItem(`anki_nt_map_${originalAnkiName}`, JSON.stringify(mappingObj))
        logs.push(`✓ [Đã ghi nhớ mapping]: Tên Anki gốc "${originalAnkiName}" ➔ Flama "${customName}"`)

        successCount++
        logs.push(`✓ [${originalAnkiName}] Đồng bộ NoteType hoàn tất thành công!`)
        setSyncLog([...logs])
      } catch (err: any) {
        const errorMsg = `Lỗi đồng bộ NoteType "${originalAnkiName}": ${err?.message || err}`
        errors.push(errorMsg)
        logs.push(`✗ ${errorMsg}`)
        setSyncLog([...logs])
      }
    }

    void queryClient.invalidateQueries({ queryKey: ['note-types'] })
    void queryClient.invalidateQueries({ queryKey: ['import-options'] })

    setSyncReport({ successCount, errors })
    setIsSyncing(false)
  }

  const filteredModels = ankiModels.filter((m) =>
    m.name.toLowerCase().includes(modelSearch.toLowerCase())
  )

  return (
    <div className="space-y-6">
      {/* 1. Connection Header */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden bg-card/60">
        <CardContent className="p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div
              className={`size-10 rounded-xl flex items-center justify-center shrink-0 ${
                connectionStatus === 'Connected'
                  ? 'bg-emerald-500/15 text-emerald-600'
                  : 'bg-destructive/15 text-destructive'
              }`}
            >
              {connectionStatus === 'Connected' ? <Wifi className="size-5" /> : <WifiOff className="size-5" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-foreground">AnkiConnect Endpoint</span>
                {connectionStatus === 'Connected' ? (
                  <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[11px]">
                    Connected (v{ankiVersion})
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="text-[11px]">
                    {connectionStatus}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                {connectionError || 'Danh sách NoteTypes từ Anki và Live View + Mã nguồn HTML/CSS phía dưới.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 w-full md:w-auto">
            <div className="w-48">
              <Input
                id={endpointInputId}
                value={endpoint}
                onChange={(e) => setEndpoint(e.target.value)}
                placeholder="http://127.0.0.1:8765"
                className="h-8 text-xs font-mono"
              />
            </div>
            <Button size="sm" variant="outline" onClick={checkAnkiConnection} disabled={isCheckingConn}>
              {isCheckingConn ? <Loader2 className="size-3.5 animate-spin mr-1" /> : <RefreshCw className="size-3.5 mr-1" />}
              Tải lại
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 2. Top Frame: Anki NoteTypes List & Renaming Table (Full Width) */}
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <NotebookTabs className="size-4 text-primary" /> Danh sách NoteTypes Anki ({ankiModels.length})
            </CardTitle>
            <CardDescription className="text-xs">
              Đổi tên NoteType hiển thị trên Flama và xem Live Preview + Mã nguồn ở khung phía dưới.
            </CardDescription>
          </div>

          <div className="flex items-center gap-3 w-full sm:w-auto">
            <div className="relative w-48">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <Input
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
                placeholder="Tìm kiếm..."
                className="pl-8 text-xs h-8"
              />
            </div>

            <Button
              size="sm"
              disabled={isSyncing || selectedModelNames.length === 0 || connectionStatus !== 'Connected'}
              onClick={() => handleSyncSelectedModels(selectedModelNames)}
              className="font-semibold shadow-sm shrink-0"
            >
              {isSyncing ? <Loader2 className="size-4 animate-spin mr-2" /> : <Zap className="size-4 mr-2" />}
              Đồng bộ {selectedModelNames.length} NoteType chọn
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-4 space-y-3">
          {isLoadingModels ? (
            <div className="text-center text-xs text-muted-foreground py-8 flex items-center justify-center gap-2">
              <Loader2 className="size-4 animate-spin text-primary" /> Đang tải NoteTypes từ Anki...
            </div>
          ) : filteredModels.length === 0 ? (
            <div className="text-center text-xs text-muted-foreground py-8">
              {connectionStatus === 'Connected' ? 'Không tìm thấy NoteType phù hợp.' : 'Chưa kết nối AnkiConnect.'}
            </div>
          ) : (
            <div className="border rounded-xl overflow-hidden max-h-64 overflow-y-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-10">
                      <Checkbox
                        checked={selectedModelNames.length === ankiModels.length}
                        onCheckedChange={(chk) => {
                          if (chk) {
                            setSelectedModelNames(ankiModels.map((m) => m.name))
                          } else {
                            setSelectedModelNames([])
                          }
                        }}
                      />
                    </TableHead>
                    <TableHead className="text-xs font-semibold">Tên Anki gốc</TableHead>
                    <TableHead className="text-xs font-semibold">Tên NoteType trên Flama (Rename)</TableHead>
                    <TableHead className="text-xs font-semibold">Cấu trúc</TableHead>
                    <TableHead className="text-xs font-semibold">Trạng thái Flama</TableHead>
                    <TableHead className="text-xs font-semibold">Hành động đồng bộ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredModels.map((model) => {
                    const isSelected = selectedModelNames.includes(model.name)
                    const isActive = activeModelName === model.name
                    const action = targetActions[model.name] || 'create_new'

                    return (
                      <TableRow
                        key={model.name}
                        onClick={() => {
                          if (!isActive) {
                            setActiveModelName(model.name)
                            setSelectedTemplateIndex(0)
                          }
                        }}
                        className={`cursor-pointer transition-colors hover:bg-muted/60 ${
                          isActive ? 'bg-primary/10 font-medium border-l-4 border-l-primary' : ''
                        }`}
                      >
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Checkbox
                            checked={isSelected}
                            onCheckedChange={() => {
                              if (isSelected) {
                                setSelectedModelNames(selectedModelNames.filter((n) => n !== model.name))
                              } else {
                                setSelectedModelNames([...selectedModelNames, model.name])
                              }
                            }}
                          />
                        </TableCell>
                        <TableCell className="font-bold text-xs text-foreground font-mono">
                          {model.name}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <div className="w-56">
                            <Input
                              value={customNames[model.name] ?? model.name}
                              onChange={(e) =>
                                setCustomNames({ ...customNames, [model.name]: e.target.value })
                              }
                              placeholder="Tên trên Flama..."
                              className="h-7 text-xs font-semibold"
                            />
                          </div>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {model.fields.length} trường • {model.templates.length} card
                        </TableCell>
                        <TableCell>
                          {model.existingFlamaId ? (
                            <Badge className="bg-emerald-500/15 text-emerald-600 border-emerald-500/30 text-[10px]">
                              Đã có
                            </Badge>
                          ) : (
                            <Badge variant="outline" className="text-amber-600 border-amber-500/30 text-[10px]">
                              Mới
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <div className="w-48">
                            <NativeSelect
                              value={action}
                              onChange={(e) =>
                                setTargetActions({ ...targetActions, [model.name]: e.target.value })
                              }
                              className="h-7 text-xs"
                            >
                              <option value="create_new">+ Tạo mới NoteType tên "{customNames[model.name] || model.name}"</option>
                              <option value="ignore">-- Bỏ qua --</option>
                              {noteTypeOptions.map((opt) => (
                                <option key={opt.id} value={opt.id}>
                                  Ghi đè: {opt.name}
                                </option>
                              ))}
                            </NativeSelect>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3. Bottom Frame: Full Width Read-only Code Display & Live Preview CardDisplay matching NoteTypeDetailPage */}
      {activeModelDetail ? (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-3 border-b bg-card/50 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <CardTitle className="text-base font-bold text-foreground">
                  Bản Xem Trực Tiếp &amp; Mã Nguồn (Live View &amp; Code Viewer)
                </CardTitle>
                <Badge variant="outline" className="text-[10px] font-mono">
                  Gốc từ Anki: "{activeModelDetail.name}"
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Hiển thị kết quả thẻ Live Card và mã nguồn Front HTML, Back HTML, CSS gốc từ Anki.
              </CardDescription>
            </div>

            <Button
              size="sm"
              disabled={isSyncing || connectionStatus !== 'Connected'}
              onClick={() => handleSyncSelectedModels([activeModelDetail.name])}
              className="font-semibold text-xs shrink-0 shadow-sm"
            >
              {isSyncing ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5" />}
              Đồng bộ NoteType "{customNames[activeModelDetail.name] || activeModelDetail.name}"
            </Button>
          </CardHeader>

          <CardContent className="pt-4 space-y-4">
            {/* 2-Column Grid: Left = Live Preview CardDisplay Frame, Right = Read-only Code Display */}
            <div className="grid gap-4 lg:grid-cols-12 items-stretch">
              {/* Left Column: Live Card Previewer (Reusing NoteTypeLivePreview) */}
              <div className="lg:col-span-6 flex flex-col">
                <NoteTypeLivePreview
                  cardId={`anki-live-preview-${activeModelDetail.name}`}
                  side={previewSide}
                  onSideChange={setPreviewSide}
                  templates={activeModelDetail.templates.map((tmpl, idx) => ({
                    id: String(idx),
                    name: tmpl.name || `Card ${idx + 1}`,
                  }))}
                  selectedTemplateId={String(selectedTemplateIndex)}
                  onSelectTemplate={(idStr) => setSelectedTemplateIndex(Number(idStr))}
                  frontPayload={previewResult?.front_renderer_payload}
                  backPayload={previewResult?.back_renderer_payload}
                  frontHtml={previewResult?.front_html || activeTemplate?.front}
                  backHtml={previewResult?.back_html || activeTemplate?.back}
                  scope="anki_note_type_preview"
                  scopeId={activeModelDetail.name}
                  fieldDefs={activeModelDetail.fields.map((f, i) => ({
                    id: f,
                    name: f,
                    field_type: inferFieldType(f),
                    position: i,
                  }))}
                  isLoading={isPreviewLoading}
                  error={previewError}
                  title="Live Card Preview"
                  subtitle="(Hiển thị mẫu thẻ với dữ liệu xem trước từ Flama)"
                />
              </div>

              {/* Right Column: Read-only Code Display (Front Code / Back Code / CSS / Fields) */}
              <div className="lg:col-span-6 flex flex-col">
                <Card className="p-4 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl">
                  <div className="flex items-center justify-between mb-3 min-h-[32px]">
                    <div className="flex items-center gap-2">
                      <div className="p-2 rounded-xl bg-amber-500/10 text-amber-600">
                        <Code2 className="size-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-foreground">Mã Nguồn Template &amp; CSS</h4>
                        <span className="text-[10px] text-muted-foreground block">(Đọc từ AnkiConnect)</span>
                      </div>
                    </div>
                  </div>

                  <Tabs
                    value={codeTab}
                    onValueChange={(val) => setCodeTab(val as any)}
                    className="flex-1 flex flex-col"
                  >
                    <TabsList className="grid grid-cols-4 w-full h-8 p-1 mb-2 rounded-lg">
                      <TabsTrigger value="front" className="text-xs font-semibold py-1 rounded-md">
                        Front HTML
                      </TabsTrigger>
                      <TabsTrigger value="back" className="text-xs font-semibold py-1 rounded-md">
                        Back HTML
                      </TabsTrigger>
                      <TabsTrigger value="css" className="text-xs font-semibold py-1 rounded-md">
                        Shared CSS
                      </TabsTrigger>
                      <TabsTrigger value="fields" className="text-xs font-semibold py-1 rounded-md">
                        Trường ({activeModelDetail.fields.length})
                      </TabsTrigger>
                    </TabsList>

                    {/* Code Container: Front HTML */}
                    <TabsContent value="front" className="flex-1 mt-0 relative">
                      <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 h-[clamp(14rem,35vh,25rem)] min-h-[14rem]">
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => handleCopyCode(activeTemplate?.front || '', 'front')}
                          className="absolute right-2 top-2 h-7 px-2 text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                        >
                          {copiedTab === 'front' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                          {copiedTab === 'front' ? 'Đã chép' : 'Sao chép'}
                        </Button>
                        <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto h-full pr-12">
                          {activeTemplate?.front || '/* Không có mã Front HTML */'}
                        </pre>
                      </div>
                    </TabsContent>

                    {/* Code Container: Back HTML */}
                    <TabsContent value="back" className="flex-1 mt-0 relative">
                      <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 h-[clamp(14rem,35vh,25rem)] min-h-[14rem]">
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => handleCopyCode(activeTemplate?.back || '', 'back')}
                          className="absolute right-2 top-2 h-7 px-2 text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                        >
                          {copiedTab === 'back' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                          {copiedTab === 'back' ? 'Đã chép' : 'Sao chép'}
                        </Button>
                        <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto h-full pr-12">
                          {activeTemplate?.back || '/* Không có mã Back HTML */'}
                        </pre>
                      </div>
                    </TabsContent>

                    {/* Code Container: Shared CSS */}
                    <TabsContent value="css" className="flex-1 mt-0 relative">
                      <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 h-[clamp(14rem,35vh,25rem)] min-h-[14rem]">
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => handleCopyCode(activeModelDetail.css || '', 'css')}
                          className="absolute right-2 top-2 h-7 px-2 text-[11px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                        >
                          {copiedTab === 'css' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                          {copiedTab === 'css' ? 'Đã chép' : 'Sao chép'}
                        </Button>
                        <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto h-full pr-12">
                          {activeModelDetail.css || '/* Không có quy tắc CSS tùy chỉnh */'}
                        </pre>
                      </div>
                    </TabsContent>

                    {/* Fields List Tab */}
                    <TabsContent value="fields" className="flex-1 mt-0">
                      <div className="border rounded-xl overflow-hidden bg-card/40 min-h-[14rem] max-h-[25rem] overflow-y-auto">
                        <div className="grid grid-cols-12 text-xs font-semibold p-2.5 bg-muted/40 border-b text-muted-foreground">
                          <span className="col-span-1">#</span>
                          <span className="col-span-6">Tên trường Anki</span>
                          <span className="col-span-5 text-right">Kiểu suy luận</span>
                        </div>
                        <div className="divide-y">
                          {activeModelDetail.fields.map((f, idx) => (
                            <div key={f} className="grid grid-cols-12 items-center p-2 text-xs hover:bg-muted/30">
                              <span className="col-span-1 font-mono text-muted-foreground">{idx + 1}</span>
                              <span className="col-span-6 font-bold text-foreground flex items-center gap-1.5">
                                {f}
                                {idx === 0 && (
                                  <Badge variant="secondary" className="text-[9px] py-0 px-1 font-normal">
                                    Primary
                                  </Badge>
                                )}
                              </span>
                              <span className="col-span-5 text-right">
                                <Badge variant="outline" className="text-[10px] font-mono">
                                  {inferFieldType(f)}
                                </Badge>
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </TabsContent>
                  </Tabs>
                </Card>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* 4. Sync Log & Summary Report */}
      {syncLog.length > 0 && (
        <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
          <CardHeader className="pb-2 bg-card/50 border-b">
            <CardTitle className="text-xs font-semibold flex items-center gap-2">
              {isSyncing && <Loader2 className="size-3.5 animate-spin text-primary" />}
              Nhật ký đồng bộ NoteType
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-3 space-y-3">
            <div className="font-mono text-[11px] bg-muted/40 p-3 rounded-xl max-h-48 overflow-y-auto space-y-1">
              {syncLog.map((logLine, idx) => (
                <div
                  key={idx}
                  className={
                    logLine.startsWith('✓')
                      ? 'text-emerald-600 font-semibold'
                      : logLine.startsWith('✗')
                      ? 'text-destructive font-semibold'
                      : 'text-muted-foreground'
                  }
                >
                  {logLine}
                </div>
              ))}
            </div>

            {syncReport && (
              <Alert
                className={
                  syncReport.errors.length === 0
                    ? 'border-primary/40 bg-primary/5'
                    : 'border-destructive/40 bg-destructive/5'
                }
              >
                {syncReport.errors.length === 0 ? (
                  <CheckCircle2 className="size-5 text-primary" />
                ) : (
                  <AlertTriangle className="size-5 text-destructive" />
                )}
                <AlertTitle className="font-bold text-xs">
                  {syncReport.errors.length === 0
                    ? 'Hoàn tất đồng bộ NoteTypes!'
                    : 'Đồng bộ NoteTypes có lỗi xảy ra'}
                </AlertTitle>
                <AlertDescription className="mt-1 text-xs space-y-1">
                  <div>Đã nạp/cập nhật thành công {syncReport.successCount} NoteType lên Flama.</div>
                  {syncReport.errors.map((err, idx) => (
                    <div key={idx} className="text-destructive font-mono text-[11px]">
                      • {err}
                    </div>
                  ))}
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Sync Progress Loading Modal Overlay */}
      <Dialog
        open={showSyncModal}
        onOpenChange={(open) => {
          if (!isSyncing) setShowSyncModal(open)
        }}
      >
        <DialogContent className="sm:max-w-md border-border/80 shadow-2xl rounded-2xl p-6">
          <DialogHeader className="items-center text-center space-y-3">
            <div className={`size-16 rounded-full flex items-center justify-center ${isSyncing ? 'bg-primary/10 text-primary animate-pulse' : 'bg-emerald-500/10 text-emerald-600'}`}>
              {isSyncing ? <Loader2 className="size-8 animate-spin text-primary" /> : <CheckCircle2 className="size-8 text-emerald-500" />}
            </div>
            <DialogTitle className="text-base font-bold text-foreground">
              {isSyncing ? 'Đang tiến hành đồng bộ NoteType...' : 'Hoàn tất đồng bộ!'}
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              {isSyncing
                ? 'Vui lòng giữ trình duyệt mở trong khi cấu trúc NoteType và các trường dữ liệu đang được nạp lên Flama.'
                : 'Đã hoàn thành nạp và ánh xạ cấu trúc NoteType.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="font-mono text-[11px] bg-muted/40 p-3 rounded-xl max-h-40 overflow-y-auto space-y-1 border">
              {syncLog.map((logLine, idx) => (
                <div
                  key={idx}
                  className={
                    logLine.startsWith('✓')
                      ? 'text-emerald-600 font-semibold'
                      : logLine.startsWith('✗')
                      ? 'text-destructive font-semibold'
                      : 'text-muted-foreground'
                  }
                >
                  {logLine}
                </div>
              ))}
            </div>

            {syncReport && (
              <Alert className={syncReport.errors.length === 0 ? 'border-emerald-500/40 bg-emerald-500/10' : 'border-destructive/40 bg-destructive/10'}>
                {syncReport.errors.length === 0 ? <CheckCircle2 className="size-5 text-emerald-600" /> : <AlertTriangle className="size-5 text-destructive" />}
                <AlertTitle className="font-bold text-xs">
                  {syncReport.errors.length === 0 ? 'Thành công!' : 'Có lỗi phát sinh'}
                </AlertTitle>
                <AlertDescription className="mt-1 text-xs space-y-1">
                  <div>Đã nạp thành công {syncReport.successCount} NoteType lên Flama.</div>
                  {syncReport.errors.map((err, idx) => (
                    <div key={idx} className="text-destructive font-mono text-[11px]">• {err}</div>
                  ))}
                </AlertDescription>
              </Alert>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <Button
              disabled={isSyncing}
              onClick={() => setShowSyncModal(false)}
              className="w-full sm:w-auto font-semibold text-xs rounded-xl"
            >
              {isSyncing ? 'Đang đồng bộ...' : 'Đóng cửa sổ'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
