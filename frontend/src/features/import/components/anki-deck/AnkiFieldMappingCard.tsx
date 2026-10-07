import { ArrowRightLeft, Loader2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect } from '@/components/ui/native-select'

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

interface AnkiFieldMappingCardProps {
  isDeckLoading: boolean
  selectedAnkiModel: string
  onAnkiModelChange: (modelName: string) => Promise<void>
  ankiModelOptions: string[]
  selectedFlamaModelId: string
  onFlamaModelChange: (modelId: string) => void
  noteTypeOptions: FlamaNoteTypeOption[]
  targetDeckInputId: string
  targetFlamaDeckName: string
  setTargetFlamaDeckName: (val: string) => void
  ankiFields: string[]
  fieldMapping: Record<string, string>
  setFieldMapping: React.Dispatch<React.SetStateAction<Record<string, string>>>
}

export function AnkiFieldMappingCard({
  isDeckLoading,
  selectedAnkiModel,
  onAnkiModelChange,
  ankiModelOptions,
  selectedFlamaModelId,
  onFlamaModelChange,
  noteTypeOptions,
  targetDeckInputId,
  targetFlamaDeckName,
  setTargetFlamaDeckName,
  ankiFields,
  fieldMapping,
  setFieldMapping,
}: AnkiFieldMappingCardProps) {
  return (
    <Card className="border-border/80 shadow-xs rounded-2xl overflow-hidden">
      <CardHeader className="p-4 sm:p-5 pb-3 border-b bg-card/40">
        <CardTitle className="text-sm font-semibold flex items-center justify-between flex-wrap gap-2">
          <span className="flex items-center gap-2">
            <ArrowRightLeft className="size-4 text-primary shrink-0" /> 2. Cấu hình Deck &amp; Ánh xạ Trường
          </span>
          {isDeckLoading && (
            <span className="text-xs text-muted-foreground font-normal flex items-center gap-1.5">
              <Loader2 className="size-3.5 animate-spin" /> Đang đọc thông tin...
            </span>
          )}
        </CardTitle>
        <CardDescription className="text-xs">
          Tùy chỉnh tên Deck đích trên Flama (dùng <code className="font-mono text-primary font-bold">::</code> tạo phân cấp) và ghép các trường.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-5 pt-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
          <div className="space-y-1">
            <Label className="text-xs font-semibold text-muted-foreground">NoteType Anki gốc</Label>
            <NativeSelect
              value={selectedAnkiModel}
              onChange={(event) => void onAnkiModelChange(event.target.value)}
              className="h-8 text-xs font-semibold"
            >
              {ankiModelOptions.map((modelName) => (
                <option key={modelName} value={modelName}>{modelName}</option>
              ))}
            </NativeSelect>
          </div>

          <div className="space-y-1">
            <Label className="text-xs font-semibold text-muted-foreground">Flama NoteType đích</Label>
            <NativeSelect
              value={selectedFlamaModelId}
              onChange={(e) => onFlamaModelChange(e.target.value)}
              className="h-8 text-xs font-semibold text-primary"
            >
              <option value="">-- Chưa có NoteType tương thích --</option>
              {noteTypeOptions.map((nt) => (
                <option key={nt.id} value={nt.id}>
                  {nt.name} ({nt.fields?.length || 0} trường)
                </option>
              ))}
            </NativeSelect>
          </div>

          <div className="space-y-1">
            <Label htmlFor={targetDeckInputId} className="text-xs font-semibold text-muted-foreground">
              Tên Deck Flama đích
            </Label>
            <Input
              id={targetDeckInputId}
              value={targetFlamaDeckName}
              onChange={(e) => setTargetFlamaDeckName(e.target.value)}
              placeholder="Ví dụ: Tiếng Nhật::JLPT N3::Từ vựng"
              className="h-8 text-xs font-semibold"
            />
          </div>
        </div>

        {/* Field Mapping Container */}
        <div className="border rounded-xl p-3 bg-card/30 space-y-2">
          <div className="hidden sm:flex items-center justify-between text-xs font-semibold border-b pb-2 text-muted-foreground">
            <span>Trường dữ liệu Anki</span>
            <span>Trường Flama tương ứng</span>
          </div>
          <div className="divide-y divide-border/40">
            {ankiFields.map((ankiField) => {
              const currentFlamaField = fieldMapping[ankiField] || 'ignore'
              const targetFlamaModel = noteTypeOptions.find((m) => m.id === selectedFlamaModelId)

              return (
                <div
                  key={ankiField}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-4 py-2 border-b border-border/40 last:border-0"
                >
                  <span className="text-xs font-bold text-foreground truncate max-w-full sm:max-w-xs">
                    {ankiField}
                  </span>
                  <div className="w-full sm:w-64 shrink-0">
                    <NativeSelect
                      value={currentFlamaField}
                      onChange={(e) => setFieldMapping({ ...fieldMapping, [ankiField]: e.target.value })}
                      className="h-8 text-xs font-medium"
                      disabled={!targetFlamaModel}
                    >
                      {!targetFlamaModel && <option value={ankiField}>{ankiField} (sẽ tự tạo)</option>}
                      <option value="ignore">-- Bỏ qua trường này --</option>
                      {targetFlamaModel?.fields.map((ff) => (
                        <option key={ff.id} value={ff.name}>
                          {ff.name} ({ff.field_type})
                        </option>
                      ))}
                    </NativeSelect>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
