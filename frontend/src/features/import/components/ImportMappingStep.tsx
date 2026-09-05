import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ArrowRightLeft, Sliders, Wand2 } from 'lucide-react'
import { toast } from 'sonner'
import type { useFileImportWizard } from '../hooks/useFileImportWizard'

interface ImportMappingStepProps {
  wizard: ReturnType<typeof useFileImportWizard>
}

export function ImportMappingStep({ wizard }: ImportMappingStepProps) {
  const {
    fields,
    mapping,
    setMapping,
    applyAutoMapping,
    columns,
    previewRows,
    importMode,
    setImportMode,
    dontOverwriteEmptyId,
    dontOverwriteEmpty,
    setDontOverwriteEmpty,
    uniquenessFields,
    setUniquenessFields,
    parseWarnings,
    columnMismatchConfirmId,
    confirmColumnMismatch,
    setConfirmColumnMismatch,
  } = wizard

  return (
    <div className="space-y-6">
      <Card className="border-border/80 shadow-sm rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b bg-card/50">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <ArrowRightLeft className="size-4 text-primary" />
                Ánh xạ Cột -&gt; Trường Note
              </CardTitle>
              <CardDescription className="text-xs">
                Ghép các cột trong tệp vào từng trường tương ứng của loại thẻ.
              </CardDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                applyAutoMapping()
                toast.info('Đã tự động ánh xạ lại các trường theo cột.')
              }}
              className="text-xs gap-1.5 h-8 font-medium shrink-0 self-start sm:self-auto"
              title="Tự động khớp cột theo tên hoặc xếp lần lượt theo thứ tự"
            >
              <Wand2 className="size-3.5 text-primary" />
              Tự động khớp lại
            </Button>
          </div>
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
              <div className="space-y-2 text-xs">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="importMode"
                    className="accent-primary size-3.5 cursor-pointer"
                    checked={importMode === 'insert_only'}
                    onChange={() => setImportMode('insert_only')}
                  />
                  <span>Chỉ thêm mới (Insert Only)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="importMode"
                    className="accent-primary size-3.5 cursor-pointer"
                    checked={importMode === 'update_only'}
                    onChange={() => setImportMode('update_only')}
                  />
                  <span>Chỉ cập nhật (Update Only)</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="radio"
                    name="importMode"
                    className="accent-primary size-3.5 cursor-pointer"
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
    </div>
  )
}
