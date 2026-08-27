import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/native-select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  FileSpreadsheet,
  Layers,
  Sparkles,
  Info,
} from 'lucide-react'
import type {
  BatchFileMeta,
  BatchFileConfig,
} from '../api'

interface BatchFileTableProps {
  batchFiles: BatchFileMeta[]
  fileConfigs: Record<string, BatchFileConfig>
  onUpdateConfig: (fileId: string, patch: Partial<BatchFileConfig>) => void
  namingMode: 'auto' | 'filename' | 'custom'
  onChangeNamingMode: (mode: 'auto' | 'filename' | 'custom') => void
  customPattern: string
  onChangeCustomPattern: (pattern: string) => void
  onApplyNamingRule: () => void
  isReparsing?: boolean
}

export const BatchFileTable: React.FC<BatchFileTableProps> = ({
  batchFiles,
  fileConfigs,
  onUpdateConfig,
  namingMode,
  onChangeNamingMode,
  customPattern,
  onChangeCustomPattern,
  onApplyNamingRule,
  isReparsing,
}) => {
  const hasDangerousCollision = batchFiles.some(
    (f) => f.collision.is_collision && f.collision.status === 'different'
  )

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  return (
    <div className="space-y-4">
      {/* Batch Naming Toolbar */}
      <div className="p-3.5 rounded-2xl border border-border/80 bg-muted/20 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            <span className="text-xs font-semibold text-foreground">
              Quy tắc đặt tên bài học ({batchFiles.length} tệp)
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => onChangeNamingMode('auto')}
              className={`text-xs px-2.5 py-1 rounded-xl border transition-all cursor-pointer ${
                namingMode === 'auto'
                  ? 'bg-primary/10 border-primary text-primary font-medium shadow-sm'
                  : 'border-border/60 hover:bg-muted text-muted-foreground'
              }`}
            >
              Tự động theo Deck cha
            </button>
            <button
              type="button"
              onClick={() => onChangeNamingMode('filename')}
              className={`text-xs px-2.5 py-1 rounded-xl border transition-all cursor-pointer ${
                namingMode === 'filename'
                  ? 'bg-primary/10 border-primary text-primary font-medium shadow-sm'
                  : 'border-border/60 hover:bg-muted text-muted-foreground'
              }`}
            >
              Theo tên tệp gốc
            </button>
            <button
              type="button"
              onClick={() => onChangeNamingMode('custom')}
              className={`text-xs px-2.5 py-1 rounded-xl border transition-all cursor-pointer ${
                namingMode === 'custom'
                  ? 'bg-primary/10 border-primary text-primary font-medium shadow-sm'
                  : 'border-border/60 hover:bg-muted text-muted-foreground'
              }`}
            >
              Mẫu tùy biến
            </button>
          </div>
        </div>

        {namingMode === 'custom' && (
          <div className="flex flex-col sm:flex-row items-center gap-2 pt-1 border-t border-border/40">
            <div className="text-xs text-muted-foreground shrink-0">
              Nhập mẫu (dùng <code className="text-primary font-mono">{'{n}'}</code> để đánh số):
            </div>
            <Input
              value={customPattern}
              onChange={(e) => onChangeCustomPattern(e.target.value)}
              placeholder="Ví dụ: Bài {n} hoặc Lesson {n}"
              className="h-8 text-xs max-w-xs"
            />
            <button
              type="button"
              disabled={isReparsing}
              onClick={onApplyNamingRule}
              className="text-xs px-3 py-1.5 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 transition-colors shrink-0"
            >
              Áp dụng mẫu
            </button>
          </div>
        )}
      </div>

      {/* Dangerous Collision Warning Banner */}
      {hasDangerousCollision && (
        <div className="p-3.5 rounded-2xl border border-destructive/30 bg-destructive/5 text-destructive flex items-start gap-3">
          <AlertTriangle className="size-5 shrink-0 mt-0.5" />
          <div className="space-y-1 text-xs">
            <div className="font-bold">
              Phát hiện xung đột tên bài nhưng nội dung khác hoàn toàn!
            </div>
            <p className="opacity-90">
              Một số tệp có tên trùng với bài học đã có trong deck cha nhưng danh sách từ vựng bên trong không trùng khớp.
              Hệ thống đã tự động đề xuất đổi tên bài mới để tránh ghi đè nhầm làm mất dữ liệu học tập cũ của bạn.
            </p>
          </div>
        </div>
      )}

      {/* Interactive Files Table */}
      <div className="border border-border/80 rounded-2xl overflow-hidden shadow-sm">
        <Table className="text-xs">
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-12 text-center">#</TableHead>
              <TableHead className="min-w-44">Tệp dữ liệu</TableHead>
              <TableHead className="w-24 text-center">Số dòng</TableHead>
              <TableHead className="min-w-48">Tên Deck con tạo mới</TableHead>
              <TableHead className="min-w-44">Kiểm tra trùng lặp</TableHead>
              <TableHead className="min-w-36">Hành động xử lý</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {batchFiles.map((fileMeta, idx) => {
              const config = fileConfigs[fileMeta.file_id] || {
                file_id: fileMeta.file_id,
                target_deck_name: fileMeta.suggested_deck_name,
                action: fileMeta.collision.suggested_action || 'create_new',
              }
              const col = fileMeta.collision

              return (
                <TableRow
                  key={fileMeta.file_id}
                  className={
                    col.is_collision && col.status === 'different'
                      ? 'bg-destructive/5'
                      : undefined
                  }
                >
                  <TableCell className="text-center font-mono text-muted-foreground">
                    {idx + 1}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="size-4 text-primary shrink-0 opacity-80" />
                      <div className="min-w-0">
                        <div className="font-medium text-foreground truncate max-w-48" title={fileMeta.filename}>
                          {fileMeta.filename}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {formatFileSize(fileMeta.file_size)} • {fileMeta.column_count} cột
                        </div>
                      </div>
                    </div>
                  </TableCell>

                  <TableCell className="text-center font-medium">
                    <Badge variant="outline" className="text-[11px] font-mono">
                      {fileMeta.total_rows} thẻ
                    </Badge>
                  </TableCell>

                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Layers className="size-3.5 text-primary/70 shrink-0" />
                      <Input
                        value={config.target_deck_name}
                        onChange={(e) =>
                          onUpdateConfig(fileMeta.file_id, {
                            target_deck_name: e.target.value,
                          })
                        }
                        placeholder="Tên bài học"
                        className="h-8 text-xs font-medium"
                      />
                    </div>
                  </TableCell>

                  <TableCell>
                    {!col.is_collision ? (
                      <Badge
                        variant="outline"
                        className="bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20 text-[11px] gap-1 font-medium"
                      >
                        <CheckCircle2 className="size-3" /> Bài mới tinh
                      </Badge>
                    ) : col.status === 'identical' ? (
                      <div className="space-y-1">
                        <Badge
                          variant="outline"
                          className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20 text-[11px] gap-1 font-medium"
                        >
                          <Copy className="size-3" /> Trùng 100% nội dung
                        </Badge>
                        <p className="text-[10px] text-muted-foreground">
                          {col.existing_notes_count} thẻ đã có trong deck
                        </p>
                      </div>
                    ) : col.status === 'partial' ? (
                      <div className="space-y-1">
                        <Badge
                          variant="outline"
                          className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20 text-[11px] gap-1 font-medium"
                        >
                          <Info className="size-3" /> Trùng {col.overlap_percentage}% thẻ
                        </Badge>
                        <p className="text-[10px] text-muted-foreground truncate max-w-44" title={col.message}>
                          {col.message}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-1">
                        <Badge
                          variant="destructive"
                          className="text-[10px] gap-1 font-semibold"
                        >
                          <AlertTriangle className="size-3" /> Trùng tên, khác nội dung!
                        </Badge>
                        <p className="text-[10px] text-destructive/80 truncate max-w-44" title={col.message}>
                          {col.message}
                        </p>
                      </div>
                    )}
                  </TableCell>

                  <TableCell>
                    <NativeSelect
                      value={config.action}
                      onChange={(e) =>
                        onUpdateConfig(fileMeta.file_id, {
                          action: e.target.value as BatchFileConfig['action'],
                        })
                      }
                      className="h-8 text-xs"
                    >
                      <option value="create_new">Tạo bài mới</option>
                      <option value="auto_rename">Tự đổi tên mới</option>
                      <option value="upsert">Cập nhật vào deck cũ</option>
                      <option value="skip">Bỏ qua file này</option>
                    </NativeSelect>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
