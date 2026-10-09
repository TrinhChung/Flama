import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import {
  UploadCloud,
  FileSpreadsheet,
  Columns,
  RotateCcw,
  Loader2,
  FileText,
  Table as TableIcon,
  Filter,
  Files,
} from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { useFileImportWizard } from '../hooks/useFileImportWizard'
import { BatchFileTable } from './BatchFileTable'

interface ImportFileStepProps {
  wizard: ReturnType<typeof useFileImportWizard>
}

export function ImportFileStep({ wizard }: ImportFileStepProps) {
  const { t } = useTranslation('import')
  const {
    token,
    file,
    files,
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
    handleDrop,
    fileInputRef,
    handleFilesSelect,
    delimiterModeSelectId,
    delimiterMode,
    setDelimiterMode,
    customDelimiterInputId,
    customDelimiter,
    setCustomDelimiter,
    parseMutation,
    batchParseMutation,
    parseMeta,
    columns,
    previewRows,
    hasHeader,
    setHasHeader,
  } = wizard

  const isParsing = parseMutation.isPending || batchParseMutation.isPending

  return (
    <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
      <CardHeader className="pb-3 border-b bg-card/50">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <UploadCloud className="size-4 text-primary" />
              {isBatchMode
                ? t('file_import.step2.title_batch', {
                    count: files.length,
                    defaultValue: `Tải file & Parse dữ liệu (${files.length} bài học)`,
                  })
                : t('file_import.step2.title', 'Tải file & Parse dữ liệu')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t(
                'file_import.step2.desc',
                'Chọn 1 hoặc nhiều tệp CSV, TSV cùng lúc (mỗi tệp tương ứng 1 bài học / Deck con).'
              )}
            </CardDescription>
          </div>
          <Badge variant={token ? 'default' : 'secondary'} className="text-xs">
            {token
              ? isBatchMode
                ? t('file_import.step2.badge_batch_parsed', {
                    count: batchFiles.length,
                    defaultValue: `Đã phân tích ${batchFiles.length} bài`,
                  })
                : t('file_import.step2.badge_parsed', 'Parse thành công')
              : t('file_import.step2.badge_waiting', 'Chờ tải file')}
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
            multiple
            accept=".csv,.tsv,.txt"
            className="hidden"
            onChange={(e) => e.target.files && handleFilesSelect(e.target.files)}
          />
          {files.length > 1 ? (
            <Files className="size-10 mx-auto text-primary mb-2 opacity-85" />
          ) : (
            <FileSpreadsheet className="size-10 mx-auto text-primary mb-2 opacity-85" />
          )}
          <p className="text-sm font-semibold text-foreground">
            {files.length > 1
              ? `Đã chọn ${files.length} tệp (${files.map((f) => f.name).slice(0, 3).join(', ')}${files.length > 3 ? '...' : ''})`
              : file
              ? file.name
              : t(
                  'file_import.step2.dropzone_prompt',
                  'Kéo thả tệp CSV / TSV vào đây hoặc bấm để chọn tệp'
                )}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {t(
              'file_import.step2.dropzone_hint',
              'Hỗ trợ tải lên nhiều file cùng lúc để tạo hàng loạt bài học'
            )}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
          <div className="space-y-1.5">
            <Label htmlFor={delimiterModeSelectId} className="text-xs font-medium">
              {t('file_import.step2.delimiter_label', 'Ký tự phân tách')}
            </Label>
            <NativeSelect
              id={delimiterModeSelectId}
              value={delimiterMode}
              onChange={(e) => setDelimiterMode(e.target.value as 'csv' | 'tsv' | 'custom')}
            >
              <option value="csv">{t('file_import.step2.delimiter_csv', 'Tự động phân tách (Phẩy - CSV)')}</option>
              <option value="tsv">{t('file_import.step2.delimiter_tsv', 'Phân tách bằng Tab (TSV)')}</option>
              <option value="custom">{t('file_import.step2.delimiter_custom', 'Ký tự tùy chỉnh…')}</option>
            </NativeSelect>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={customDelimiterInputId} className="text-xs font-medium">
              {t('file_import.step2.delimiter_custom', 'Ký tự tùy chỉnh')}
            </Label>
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
              disabled={(!file && files.length === 0) || isParsing}
              onClick={() => {
                if (isBatchMode && files.length > 1) {
                  batchParseMutation.mutate(files)
                } else if (file) {
                  parseMutation.mutate(file)
                }
              }}
            >
              {isParsing ? <Loader2 className="size-4 animate-spin mr-1.5" /> : <RotateCcw className="size-4 mr-1.5" />}
              {t('file_import.step3.btn_auto_remap', 'Parse lại')}
            </Button>
          </div>
        </div>

        {parseMeta && (
          <div className="flex flex-wrap gap-2 text-xs pt-1">
            <Badge variant="secondary"><FileText className="size-3 mr-1" /> {parseMeta.filename}</Badge>
            <Badge variant="secondary"><TableIcon className="size-3 mr-1" /> {parseMeta.totalRows} {t('file_import.step4.stat_total', 'dòng')}</Badge>
            <Badge variant="secondary"><Columns className="size-3 mr-1" /> {parseMeta.columnCount} cột</Badge>
            <Badge variant="secondary"><Filter className="size-3 mr-1" /> Ký tự: {parseMeta.delimiterLabel}</Badge>
          </div>
        )}

        {/* Multi-file Interactive Table */}
        {isBatchMode && batchFiles.length > 0 && (
          <BatchFileTable
            batchFiles={batchFiles}
            fileConfigs={batchFileConfigs}
            onUpdateConfig={updateBatchFileConfig}
            namingMode={namingMode}
            onChangeNamingMode={setNamingMode}
            customPattern={customPattern}
            onChangeCustomPattern={setCustomPattern}
            onApplyNamingRule={handleApplyNamingRule}
            isReparsing={batchParseMutation.isPending}
          />
        )}

        {/* Single File Preview Table */}
        {!isBatchMode && columns.length > 0 && (
          <div className="border border-border/80 rounded-2xl overflow-hidden mt-3">
            <div className="bg-muted/40 p-3 border-b flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h4 className="text-xs font-bold text-foreground">
                  {t('file_import.step2.preview_table_title', 'Bảng xem trước dữ liệu trích xuất (Preview)')}
                </h4>
                <p className="text-[11px] text-muted-foreground">Hiển thị các dòng mẫu đã phân tách cột.</p>
              </div>
              <div className="flex items-center gap-4 text-xs font-medium">
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="headerMode"
                    className="accent-primary size-3.5 cursor-pointer"
                    checked={hasHeader}
                    onChange={() => {
                      setHasHeader(true)
                      if (file) parseMutation.mutate(file)
                    }}
                  />
                  <span>Có tiêu đề</span>
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="headerMode"
                    className="accent-primary size-3.5 cursor-pointer"
                    checked={!hasHeader}
                    onChange={() => {
                      setHasHeader(false)
                      if (file) parseMutation.mutate(file)
                    }}
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
  )
}
