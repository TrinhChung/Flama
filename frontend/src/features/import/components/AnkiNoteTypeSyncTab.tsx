import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import type { AnkiConnectStatus } from '../lib/ankiConnectClient'
import { ankiConnectClient } from '../lib/ankiConnectClient'
import { appApi } from '@/app/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AnkiModelSelectTable } from './anki-notetype/AnkiModelSelectTable'
import { AnkiModelCodeViewer } from './anki-notetype/AnkiModelCodeViewer'
import { AnkiNoteTypeSyncModal } from './anki-notetype/AnkiNoteTypeSyncModal'
import type { AnkiModelDetail, FlamaNoteTypeOption, PreviewResponse } from './anki-notetype/types'

interface AnkiNoteTypeSyncTabProps {
  noteTypeOptions: FlamaNoteTypeOption[]
  endpoint: string
  connectionStatus: AnkiConnectStatus
  ankiVersion: number | null
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

export const AnkiNoteTypeSyncTab: React.FC<AnkiNoteTypeSyncTabProps> = ({
  noteTypeOptions,
  endpoint,
  connectionStatus,
}) => {
  const { t } = useTranslation('import')
  const queryClient = useQueryClient()

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

  const loadAnkiModels = useCallback(async () => {
    setIsLoadingModels(true)
    try {
      const modelNames = await ankiConnectClient.getModelNames(endpoint)
      const initialActions: Record<string, string> = {}
      const initialCustomNames: Record<string, string> = {}

      const details: AnkiModelDetail[] = await Promise.all(
        modelNames.map(async (name) => {
          const [fields, styling, templates] = await Promise.all([
            ankiConnectClient.getModelFieldNames(name, endpoint),
            ankiConnectClient.getModelStyling(name, endpoint),
            ankiConnectClient.getModelTemplates(name, endpoint),
          ])

          const matchedFlama = noteTypeOptions.find(
            (nt) => nt.name.toLowerCase() === name.toLowerCase()
          )

          initialActions[name] = matchedFlama ? matchedFlama.id : 'create_new'
          initialCustomNames[name] = name

          return {
            name,
            fields,
            css: styling.css || '',
            templates: templates || [{ name: 'Card 1', front: '{{Front}}', back: '{{FrontSide}}<hr>{{Back}}' }],
            existingFlamaId: matchedFlama?.id,
          }
        })
      )

      setAnkiModels(details)
      setTargetActions(initialActions)
      setCustomNames(initialCustomNames)

      if (details.length > 0) {
        setActiveModelName(details[0].name)
      }
      setSelectedModelNames([])
    } catch (err: any) {
      console.warn('Lỗi tải danh sách NoteType:', err)
    }
    setIsLoadingModels(false)
  }, [endpoint, noteTypeOptions])

  useEffect(() => {
    if (connectionStatus === 'Connected') {
      loadAnkiModels()
    }
  }, [connectionStatus, loadAnkiModels])

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
      alert(t('anki_sync.notetypes_tab.alert_select_at_least_one', 'Vui lòng chọn ít nhất 1 NoteType để đồng bộ.'))
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
          setTargetActions((current) => ({ ...current, [originalAnkiName]: flamaNoteTypeId }))
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
              await appApi.mutate(`/note-types/${flamaNoteTypeId}/templates`, 'POST', {
                name: tmpl.name || `Card ${tIdx + 1}`,
                front_html: tmpl.front,
                back_html: tmpl.back,
                shared_css: modelDetail.css || '',
              })
              logs.push(`  + Template bổ sung: "${tmpl.name || `Card ${tIdx + 1}`}"`)
              setSyncLog([...logs])
            }
          }
        } else {
          // Sync into existing Flama NoteType
          const existingNT = await appApi.get<{
            id: string
            field_defs?: Array<{ name: string; identity_role?: string | null }>
            templates?: Array<{ id: string; name: string }>
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
            const existingTemplates = existingNT.templates || []
            const usedTemplateIds = new Set<string>()
            for (let tmplIndex = 0; tmplIndex < modelDetail.templates.length; tmplIndex++) {
              const tmpl = modelDetail.templates[tmplIndex]
              const templateName = tmpl.name || `Card ${tmplIndex + 1}`
              const matchedTemplate =
                existingTemplates.find(
                  (item) => !usedTemplateIds.has(item.id) && item.name.toLowerCase() === templateName.toLowerCase()
                ) || existingTemplates.find((item) => !usedTemplateIds.has(item.id))
              const templatePayload = {
                name: templateName,
                front_html: tmpl.front,
                back_html: tmpl.back,
                shared_css: modelDetail.css || '',
              }

              if (matchedTemplate) {
                await appApi.mutate(
                  `/note-types/${flamaNoteTypeId}/templates/${matchedTemplate.id}`,
                  'PATCH',
                  templatePayload
                )
                usedTemplateIds.add(matchedTemplate.id)
                logs.push(`  ↻ Đã cập nhật template: "${templateName}"`)
              } else {
                await appApi.mutate(`/note-types/${flamaNoteTypeId}/templates`, 'POST', templatePayload)
                logs.push(`  + Template mới: "${templateName}"`)
              }
              setSyncLog([...logs])
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

  const filteredModels = useMemo(() => {
    return ankiModels.filter((m) =>
      m.name.toLowerCase().includes(modelSearch.toLowerCase())
    )
  }, [ankiModels, modelSearch])

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 1. Anki NoteTypes List & Renaming Table */}
      <AnkiModelSelectTable
        ankiModels={ankiModels}
        filteredModels={filteredModels}
        selectedModelNames={selectedModelNames}
        onToggleSelectAll={(chk) => {
          if (chk) {
            setSelectedModelNames(ankiModels.map((m) => m.name))
          } else {
            setSelectedModelNames([])
          }
        }}
        onToggleSelectModel={(modelName) => {
          if (selectedModelNames.includes(modelName)) {
            setSelectedModelNames(selectedModelNames.filter((n) => n !== modelName))
          } else {
            setSelectedModelNames([...selectedModelNames, modelName])
          }
        }}
        activeModelName={activeModelName}
        onSelectActiveModel={(modelName) => {
          setActiveModelName(modelName)
          setSelectedTemplateIndex(0)
        }}
        modelSearch={modelSearch}
        onSearchChange={setModelSearch}
        customNames={customNames}
        onChangeCustomName={(modelName, val) => {
          setCustomNames((prev) => ({ ...prev, [modelName]: val }))
        }}
        targetActions={targetActions}
        onChangeTargetAction={(modelName, val) => {
          setTargetActions((prev) => ({ ...prev, [modelName]: val }))
        }}
        noteTypeOptions={noteTypeOptions}
        isLoadingModels={isLoadingModels}
        connectionStatus={connectionStatus}
        isSyncing={isSyncing}
        onSyncSelected={() => handleSyncSelectedModels(selectedModelNames)}
      />

      {/* 2. Live Preview & Code Display Frame */}
      {activeModelDetail && (
        <AnkiModelCodeViewer
          activeModelDetail={activeModelDetail}
          customName={customNames[activeModelDetail.name] || activeModelDetail.name}
          previewSide={previewSide}
          onPreviewSideChange={setPreviewSide}
          selectedTemplateIndex={selectedTemplateIndex}
          onSelectTemplateIndex={setSelectedTemplateIndex}
          previewResult={previewResult}
          isPreviewLoading={isPreviewLoading}
          previewError={previewError}
          codeTab={codeTab}
          setCodeTab={setCodeTab}
          copiedTab={copiedTab}
          onCopyCode={handleCopyCode}
          isSyncing={isSyncing}
          connectionStatus={connectionStatus}
          onSyncSingle={() => handleSyncSelectedModels([activeModelDetail.name])}
          inferFieldType={inferFieldType}
        />
      )}

      {/* 3. Sync Log & Summary Report */}
      {syncLog.length > 0 && (
        <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
          <CardHeader className="pb-2 bg-card/40 border-b">
            <CardTitle className="text-xs font-semibold flex items-center gap-2">
              {isSyncing && <Loader2 className="size-3.5 animate-spin text-primary" />}
              {t('anki_sync.notetypes_tab.sync_log.title', 'Nhật ký đồng bộ NoteType')}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-3 sm:p-4 pt-3 space-y-3">
            <div className="font-mono text-[11px] bg-muted/40 p-3 rounded-xl max-h-48 overflow-y-auto space-y-1 border">
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
                    ? t('anki_sync.notetypes_tab.sync_log.alert_success_title', 'Hoàn tất đồng bộ NoteTypes!')
                    : t('anki_sync.notetypes_tab.sync_log.alert_error_title', 'Đồng bộ NoteTypes có lỗi xảy ra')}
                </AlertTitle>
                <AlertDescription className="mt-1 text-xs space-y-1">
                  <div>
                    {t('anki_sync.notetypes_tab.sync_log.success_desc', {
                      count: syncReport.successCount,
                      defaultValue: `Đã nạp/cập nhật thành công ${syncReport.successCount} NoteType lên Flama.`,
                    })}
                  </div>
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
      <AnkiNoteTypeSyncModal
        open={showSyncModal}
        onOpenChange={setShowSyncModal}
        isSyncing={isSyncing}
        syncLog={syncLog}
        syncReport={syncReport}
      />
    </div>
  )
}
