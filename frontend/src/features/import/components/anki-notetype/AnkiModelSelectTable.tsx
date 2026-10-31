import React from 'react'
import { NotebookTabs, Search, Loader2, Zap } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import type { AnkiConnectStatus } from '../../lib/ankiConnectClient'
import type { AnkiModelDetail, FlamaNoteTypeOption } from './types'

interface AnkiModelSelectTableProps {
  ankiModels: AnkiModelDetail[]
  filteredModels: AnkiModelDetail[]
  selectedModelNames: string[]
  onToggleSelectAll: (checked: boolean) => void
  onToggleSelectModel: (name: string) => void
  activeModelName: string | null
  onSelectActiveModel: (name: string) => void
  modelSearch: string
  onSearchChange: (val: string) => void
  customNames: Record<string, string>
  onChangeCustomName: (modelName: string, val: string) => void
  targetActions: Record<string, string>
  onChangeTargetAction: (modelName: string, val: string) => void
  noteTypeOptions: FlamaNoteTypeOption[]
  isLoadingModels: boolean
  connectionStatus: AnkiConnectStatus
  isSyncing: boolean
  onSyncSelected: () => void
}

export const AnkiModelSelectTable: React.FC<AnkiModelSelectTableProps> = ({
  ankiModels,
  filteredModels,
  selectedModelNames,
  onToggleSelectAll,
  onToggleSelectModel,
  activeModelName,
  onSelectActiveModel,
  modelSearch,
  onSearchChange,
  customNames,
  onChangeCustomName,
  targetActions,
  onChangeTargetAction,
  noteTypeOptions,
  isLoadingModels,
  connectionStatus,
  isSyncing,
  onSyncSelected,
}) => {
  const { t } = useTranslation('import')

  return (
    <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <NotebookTabs className="size-4 text-primary shrink-0" />{' '}
            {t('anki_sync.notetypes_tab.card_title', {
              count: ankiModels.length,
              defaultValue: `Danh sách NoteTypes Anki (${ankiModels.length})`,
            })}
          </CardTitle>
          <CardDescription className="text-xs">
            {t(
              'anki_sync.notetypes_tab.card_desc',
              'Đổi tên NoteType hiển thị trên Flama và xem Live Preview + Mã nguồn ở khung phía dưới.'
            )}
          </CardDescription>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full sm:w-auto">
          <div className="relative w-full sm:w-44">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <Input
              value={modelSearch}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder={t('anki_sync.notetypes_tab.search_placeholder', 'Tìm kiếm...')}
              className="pl-8 text-xs h-8"
            />
          </div>

          <Button
            size="sm"
            disabled={isSyncing || selectedModelNames.length === 0 || connectionStatus !== 'Connected'}
            onClick={onSyncSelected}
            className="font-semibold text-xs shadow-sm shrink-0 h-8"
          >
            {isSyncing ? <Loader2 className="size-3.5 animate-spin mr-1.5" /> : <Zap className="size-3.5 mr-1.5" />}
            {t('anki_sync.notetypes_tab.btn_sync_selected', {
              count: selectedModelNames.length,
              defaultValue: `Đồng bộ ${selectedModelNames.length} NoteType chọn`,
            })}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-3 sm:p-5 pt-3 space-y-3">
        {isLoadingModels ? (
          <div className="text-center text-xs text-muted-foreground py-8 flex items-center justify-center gap-2">
            <Loader2 className="size-4 animate-spin text-primary" />{' '}
            {t('anki_sync.notetypes_tab.loading_models', 'Đang tải NoteTypes từ Anki...')}
          </div>
        ) : filteredModels.length === 0 ? (
          <div className="text-center text-xs text-muted-foreground py-8">
            {connectionStatus === 'Connected'
              ? t('anki_sync.notetypes_tab.empty_no_models', 'Không tìm thấy NoteType phù hợp.')
              : t('anki_sync.notetypes_tab.not_connected', 'Chưa kết nối AnkiConnect local.')}
          </div>
        ) : (
          <div className="border rounded-xl overflow-x-auto max-h-64 overflow-y-auto">
            <Table className="min-w-[650px]">
              <TableHeader>
                <TableRow className="bg-muted/30">
                  <TableHead className="w-10">
                    <Checkbox
                      checked={selectedModelNames.length === ankiModels.length && ankiModels.length > 0}
                      onCheckedChange={(chk) => onToggleSelectAll(Boolean(chk))}
                    />
                  </TableHead>
                  <TableHead className="text-xs font-semibold">
                    {t('anki_sync.notetypes_tab.table.col_anki_name', 'Tên Anki gốc')}
                  </TableHead>
                  <TableHead className="text-xs font-semibold">
                    {t('anki_sync.notetypes_tab.table.col_flama_name', 'Tên NoteType trên Flama (Rename)')}
                  </TableHead>
                  <TableHead className="text-xs font-semibold">
                    {t('anki_sync.notetypes_tab.table.col_structure', 'Cấu trúc')}
                  </TableHead>
                  <TableHead className="text-xs font-semibold">
                    {t('anki_sync.notetypes_tab.table.col_status', 'Trạng thái')}
                  </TableHead>
                  <TableHead className="text-xs font-semibold">
                    {t('anki_sync.notetypes_tab.table.col_action', 'Hành động đồng bộ')}
                  </TableHead>
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
                          onSelectActiveModel(model.name)
                        }
                      }}
                      className={`cursor-pointer transition-colors hover:bg-muted/60 ${
                        isActive ? 'bg-primary/10 font-medium border-l-4 border-l-primary' : ''
                      }`}
                    >
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={isSelected}
                          onCheckedChange={() => onToggleSelectModel(model.name)}
                        />
                      </TableCell>
                      <TableCell className="font-bold text-xs text-foreground font-mono">
                        {model.name}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <div className="w-48 sm:w-56">
                          <Input
                            value={customNames[model.name] ?? model.name}
                            onChange={(e) => onChangeCustomName(model.name, e.target.value)}
                            placeholder={t('anki_sync.notetypes_tab.table.rename_placeholder', 'Tên trên Flama...')}
                            className="h-7 text-xs font-semibold"
                          />
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {t('anki_sync.notetypes_tab.table.structure_summary', {
                          fields: model.fields.length,
                          templates: model.templates.length,
                          defaultValue: `${model.fields.length} trường • ${model.templates.length} card`,
                        })}
                      </TableCell>
                      <TableCell>
                        {model.existingFlamaId ? (
                          <Badge className="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 text-[10px]">
                            {t('anki_sync.notetypes_tab.table.badge_existing', 'Đã có')}
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px]">
                            {t('anki_sync.notetypes_tab.table.badge_new', 'Mới')}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <div className="w-44 sm:w-48">
                          <NativeSelect
                            value={action}
                            onChange={(e) => onChangeTargetAction(model.name, e.target.value)}
                            className="h-7 text-xs"
                          >
                            <option value="create_new">
                              {t('anki_sync.notetypes_tab.table.action_create_new', '+ Tạo mới NoteType')}
                            </option>
                            <option value="ignore">
                              {t('anki_sync.notetypes_tab.table.action_ignore', '-- Bỏ qua --')}
                            </option>
                            {noteTypeOptions.map((opt) => (
                              <option key={opt.id} value={opt.id}>
                                {t('anki_sync.notetypes_tab.table.action_merge', {
                                  name: opt.name,
                                  defaultValue: `Hợp nhất & cập nhật: ${opt.name}`,
                                })}
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
  )
}
