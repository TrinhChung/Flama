import { useEffect, useState } from 'react'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'

type FieldDef = {
  name: string
  field_type: string
  required?: boolean
}

type EditCardModalProps = {
  opened: boolean
  onClose: () => void
  cardId?: string | null
  saveUrl?: string | null
  fieldDefs?: FieldDef[]
  initialFieldValues?: Record<string, string>
  onSaved?: () => void
}

export function EditCardModal({
  opened,
  onClose,
  cardId,
  saveUrl,
  fieldDefs = [],
  initialFieldValues = {},
  onSaved,
}: EditCardModalProps) {
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (opened) {
      setFieldValues({ ...initialFieldValues })
      setError(null)
    }
  }, [opened, initialFieldValues])

  if (!opened) return null

  const handleSave = async () => {
    if (!cardId) return
    setSaving(true)
    setError(null)
    try {
      const endpoint = saveUrl || `/api/study/cards/${cardId}/edit`
      await appApi.mutate(endpoint, 'PATCH', {
        field_values: fieldValues,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể lưu thay đổi.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl rounded-2xl border border-border bg-card p-6 shadow-xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between border-b pb-3 mb-4">
          <h3 className="text-lg font-bold text-foreground">Sửa thẻ hiện tại</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl font-bold px-2"
            aria-label="Đóng"
          >
            &times;
          </button>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive font-medium">
            {error}
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          {fieldDefs.length ? (
            fieldDefs.map((field) => (
              <div key={field.name} className="space-y-1.5">
                <label className="flex items-center justify-between text-xs font-bold text-foreground">
                  <span>
                    {field.name}
                    {field.required ? (
                      <span className="text-destructive ml-0.5">*</span>
                    ) : null}
                  </span>
                  <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                    {field.field_type}
                  </span>
                </label>
                <textarea
                  rows={field.field_type === 'markdown' ? 4 : 2}
                  className="w-full rounded-lg border border-input bg-background p-2.5 text-xs text-foreground focus:ring-2 focus:ring-primary focus:outline-none font-mono"
                  value={fieldValues[field.name] || ''}
                  onChange={(e) =>
                    setFieldValues((prev) => ({
                      ...prev,
                      [field.name]: e.target.value,
                    }))
                  }
                />
              </div>
            ))
          ) : (
            <p className="text-xs text-muted-foreground italic">
              Không tìm thấy thông tin trường của thẻ này.
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t pt-4 mt-4">
          <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
            Hủy
          </Button>
          <Button
            size="sm"
            onClick={handleSave}
            disabled={saving}
            className="bg-primary font-bold text-primary-foreground"
          >
            {saving ? 'Đang lưu…' : 'Lưu thay đổi'}
          </Button>
        </div>
      </div>
    </div>
  )
}
