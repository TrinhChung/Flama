import React from 'react'
import { Code2, Copy, Check, Loader2, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { NoteTypeLivePreview } from '@/features/note-types/components/NoteTypeLivePreview'
import type { AnkiConnectStatus } from '@/lib/ankiConnectClient'
import type { AnkiModelDetail, PreviewResponse } from './types'

interface AnkiModelCodeViewerProps {
  activeModelDetail: AnkiModelDetail
  customName: string
  previewSide: 'front' | 'back'
  onPreviewSideChange: (side: 'front' | 'back') => void
  selectedTemplateIndex: number
  onSelectTemplateIndex: (idx: number) => void
  previewResult: PreviewResponse | null
  isPreviewLoading: boolean
  previewError: string | null
  codeTab: 'front' | 'back' | 'css' | 'fields'
  setCodeTab: (tab: 'front' | 'back' | 'css' | 'fields') => void
  copiedTab: string | null
  onCopyCode: (text: string, tabName: string) => void
  isSyncing: boolean
  connectionStatus: AnkiConnectStatus
  onSyncSingle: () => void
  inferFieldType: (fieldName: string) => 'text' | 'image' | 'audio' | 'richtext'
}

export const AnkiModelCodeViewer: React.FC<AnkiModelCodeViewerProps> = ({
  activeModelDetail,
  customName,
  previewSide,
  onPreviewSideChange,
  selectedTemplateIndex,
  onSelectTemplateIndex,
  previewResult,
  isPreviewLoading,
  previewError,
  codeTab,
  setCodeTab,
  copiedTab,
  onCopyCode,
  isSyncing,
  connectionStatus,
  onSyncSingle,
  inferFieldType,
}) => {
  const { t } = useTranslation('import')
  const activeTemplate = activeModelDetail.templates[selectedTemplateIndex] || activeModelDetail.templates[0]

  return (
    <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-sm sm:text-base font-bold text-foreground">
              {t('anki_sync.notetypes_tab.code_viewer.title', 'Xem Trực Tiếp & Mã Nguồn (Live View & Code Viewer)')}
            </CardTitle>
            <Badge variant="outline" className="text-[10px] font-mono">
              "{activeModelDetail.name}"
            </Badge>
          </div>
          <CardDescription className="text-xs">
            {t(
              'anki_sync.notetypes_tab.code_viewer.desc',
              'Hiển thị kết quả thẻ Live Card và mã nguồn Front HTML, Back HTML, CSS gốc từ Anki.'
            )}
          </CardDescription>
        </div>

        <Button
          size="sm"
          disabled={isSyncing || connectionStatus !== 'Connected'}
          onClick={onSyncSingle}
          className="font-semibold text-xs shrink-0 shadow-sm h-8"
        >
          {isSyncing ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5" />}
          {t('anki_sync.notetypes_tab.code_viewer.btn_sync_single', {
            name: customName || activeModelDetail.name,
            defaultValue: `Đồng bộ NoteType "${customName || activeModelDetail.name}"`,
          })}
        </Button>
      </CardHeader>

      <CardContent className="p-3 sm:p-5 pt-4 space-y-4">
        <div className="grid gap-4 lg:grid-cols-12 items-stretch">
          {/* Left Column: Live Card Previewer */}
          <div className="lg:col-span-6 flex flex-col">
            <NoteTypeLivePreview
              cardId={`anki-live-preview-${activeModelDetail.name}`}
              side={previewSide}
              onSideChange={onPreviewSideChange}
              templates={activeModelDetail.templates.map((tmpl, idx) => ({
                id: String(idx),
                name: tmpl.name || `Card ${idx + 1}`,
              }))}
              selectedTemplateId={String(selectedTemplateIndex)}
              onSelectTemplate={(idStr) => onSelectTemplateIndex(Number(idStr))}
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
              title={t('anki_sync.notetypes_tab.code_viewer.live_preview_title', 'Live Card Preview')}
              subtitle={t(
                'anki_sync.notetypes_tab.code_viewer.live_preview_subtitle',
                '(Hiển thị mẫu thẻ với dữ liệu xem trước)'
              )}
            />
          </div>

          {/* Right Column: Read-only Code Display */}
          <div className="lg:col-span-6 flex flex-col">
            <Card className="p-3.5 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl">
              <div className="flex items-center justify-between mb-3 min-h-[32px]">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 sm:p-2 rounded-xl bg-amber-500/10 text-amber-600">
                    <Code2 className="size-4" />
                  </div>
                  <div>
                    <h4 className="text-xs sm:text-sm font-bold text-foreground">
                      {t('anki_sync.notetypes_tab.code_viewer.front', 'Mã Nguồn Template & CSS')}
                    </h4>
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
                  <TabsTrigger value="front" className="text-[11px] sm:text-xs font-semibold py-1 rounded-md">
                    {t('anki_sync.notetypes_tab.code_viewer.tab_front', 'Front')}
                  </TabsTrigger>
                  <TabsTrigger value="back" className="text-[11px] sm:text-xs font-semibold py-1 rounded-md">
                    {t('anki_sync.notetypes_tab.code_viewer.tab_back', 'Back')}
                  </TabsTrigger>
                  <TabsTrigger value="css" className="text-[11px] sm:text-xs font-semibold py-1 rounded-md">
                    {t('anki_sync.notetypes_tab.code_viewer.tab_css', 'CSS')}
                  </TabsTrigger>
                  <TabsTrigger value="fields" className="text-[11px] sm:text-xs font-semibold py-1 rounded-md">
                    {t('anki_sync.notetypes_tab.code_viewer.tab_fields', {
                      count: activeModelDetail.fields.length,
                      defaultValue: `Trường (${activeModelDetail.fields.length})`,
                    })}
                  </TabsTrigger>
                </TabsList>

                {/* Code Container: Front HTML */}
                <TabsContent value="front" className="flex-1 mt-0 relative">
                  <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 max-h-64 sm:max-h-96 min-h-[12rem]">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => onCopyCode(activeTemplate?.front || '', 'front')}
                      className="absolute right-2 top-2 h-6 px-2 text-[10px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                    >
                      {copiedTab === 'front' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                      {copiedTab === 'front'
                        ? t('anki_sync.notetypes_tab.code_viewer.copied', 'Đã chép')
                        : t('anki_sync.notetypes_tab.code_viewer.copy', 'Sao chép')}
                    </Button>
                    <pre className="font-mono text-[11px] sm:text-xs whitespace-pre-wrap overflow-auto max-h-56 sm:max-h-80 pr-12">
                      {activeTemplate?.front || t('anki_sync.notetypes_tab.code_viewer.no_front', '/* Không có mã Front HTML */')}
                    </pre>
                  </div>
                </TabsContent>

                {/* Code Container: Back HTML */}
                <TabsContent value="back" className="flex-1 mt-0 relative">
                  <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 max-h-64 sm:max-h-96 min-h-[12rem]">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => onCopyCode(activeTemplate?.back || '', 'back')}
                      className="absolute right-2 top-2 h-6 px-2 text-[10px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                    >
                      {copiedTab === 'back' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                      {copiedTab === 'back'
                        ? t('anki_sync.notetypes_tab.code_viewer.copied', 'Đã chép')
                        : t('anki_sync.notetypes_tab.code_viewer.copy', 'Sao chép')}
                    </Button>
                    <pre className="font-mono text-[11px] sm:text-xs whitespace-pre-wrap overflow-auto max-h-56 sm:max-h-80 pr-12">
                      {activeTemplate?.back || t('anki_sync.notetypes_tab.code_viewer.no_back', '/* Không có mã Back HTML */')}
                    </pre>
                  </div>
                </TabsContent>

                {/* Code Container: Shared CSS */}
                <TabsContent value="css" className="flex-1 mt-0 relative">
                  <div className="relative border rounded-xl overflow-hidden bg-slate-950 text-slate-100 p-3 max-h-64 sm:max-h-96 min-h-[12rem]">
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => onCopyCode(activeModelDetail.css || '', 'css')}
                      className="absolute right-2 top-2 h-6 px-2 text-[10px] font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-800"
                    >
                      {copiedTab === 'css' ? <Check className="size-3 mr-1 text-emerald-400" /> : <Copy className="size-3 mr-1" />}
                      {copiedTab === 'css'
                        ? t('anki_sync.notetypes_tab.code_viewer.copied', 'Đã chép')
                        : t('anki_sync.notetypes_tab.code_viewer.copy', 'Sao chép')}
                    </Button>
                    <pre className="font-mono text-[11px] sm:text-xs whitespace-pre-wrap overflow-auto max-h-56 sm:max-h-80 pr-12">
                      {activeModelDetail.css || t('anki_sync.notetypes_tab.code_viewer.no_css', '/* Không có quy tắc CSS tùy chỉnh */')}
                    </pre>
                  </div>
                </TabsContent>

                {/* Fields List Tab */}
                <TabsContent value="fields" className="flex-1 mt-0">
                  <div className="border rounded-xl overflow-hidden bg-card/40 min-h-[12rem] max-h-64 sm:max-h-96 overflow-y-auto">
                    <div className="grid grid-cols-12 text-xs font-semibold p-2 bg-muted/40 border-b text-muted-foreground">
                      <span className="col-span-1">
                        {t('anki_sync.notetypes_tab.code_viewer.field_header_idx', '#')}
                      </span>
                      <span className="col-span-6">
                        {t('anki_sync.notetypes_tab.code_viewer.field_header_name', 'Tên trường Anki')}
                      </span>
                      <span className="col-span-5 text-right">
                        {t('anki_sync.notetypes_tab.code_viewer.field_header_type', 'Kiểu suy luận')}
                      </span>
                    </div>
                    <div className="divide-y divide-border/40">
                      {activeModelDetail.fields.map((f, idx) => (
                        <div key={f} className="grid grid-cols-12 items-center p-2 text-xs hover:bg-muted/30">
                          <span className="col-span-1 font-mono text-muted-foreground">{idx + 1}</span>
                          <span className="col-span-6 font-bold text-foreground flex items-center gap-1.5 truncate">
                            {f}
                            {idx === 0 && (
                              <Badge variant="secondary" className="text-[9px] py-0 px-1 font-normal">
                                {t('anki_sync.notetypes_tab.code_viewer.badge_primary', 'Primary')}
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
  )
}
