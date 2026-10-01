import { useEffect, useState } from 'react'
import { Shield, ShieldCheck, BookOpen, FolderTree, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import type { CreateTokenPayload, McpMode, McpToken, UpdateTokenPayload } from '../types'
import { ALL_MCP_SCOPES, SCOPE_CATEGORIES, SCOPE_PRESETS } from '../types'

export interface McpCreateEditTokenModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  editingToken: McpToken | null
  mode: McpMode
  users?: Array<{ id: number; username: string; email: string; display_name?: string }>
  initialUserId?: number | null
  onSubmitCreate: (payload: CreateTokenPayload) => Promise<void>
  onSubmitEdit: (payload: UpdateTokenPayload) => Promise<void>
  isSubmitting?: boolean
  isViewOnly?: boolean
}

export function McpCreateEditTokenModal({
  open,
  onOpenChange,
  editingToken,
  mode,
  users,
  initialUserId,
  onSubmitCreate,
  onSubmitEdit,
  isSubmitting = false,
}: McpCreateEditTokenModalProps) {
  const isEditing = Boolean(editingToken)
  const [name, setName] = useState('')
  const [expiry, setExpiry] = useState('180')
  const [scopes, setScopes] = useState<string[]>([])
  const [userId, setUserId] = useState<number | string>('')
  const [customToken, setCustomToken] = useState('')

  useEffect(() => {
    if (editingToken) {
      setName(editingToken.name || '')
      setExpiry('keep')
      setScopes([...(editingToken.scopes || [])])
      setUserId(editingToken.user_id ?? '')
      setCustomToken('')
    } else {
      setName('')
      setExpiry('180')
      setScopes(ALL_MCP_SCOPES.map((s) => s.key))
      setUserId(initialUserId ?? (users && users.length > 0 ? users[0].id : ''))
      setCustomToken('')
    }
  }, [editingToken, initialUserId, users, open])

  const handleApplyPreset = (presetKey: string) => {
    const preset = SCOPE_PRESETS.find((p) => p.key === presetKey)
    if (preset) setScopes([...preset.scopes])
  }

  const handleToggleScope = (scopeKey: string) => {
    setScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((k) => k !== scopeKey) : [...prev, scopeKey]
    )
  }

  const handleToggleCategory = (catScopes: string[], selectAll: boolean) => {
    setScopes((prev) => {
      const rest = prev.filter((s) => !catScopes.includes(s))
      return selectAll ? [...rest, ...catScopes] : rest
    })
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || scopes.length === 0) return
    if (isEditing && editingToken) {
      await onSubmitEdit({
        id: editingToken.id,
        name: name.trim(),
        scopes,
        expires_in_days: expiry === 'keep' ? 'keep' : expiry === 'none' ? 'none' : Number(expiry),
      })
    } else {
      await onSubmitCreate({
        name: name.trim(),
        scopes,
        expires_in_days: expiry === 'none' ? null : Number(expiry),
        user_id: mode === 'admin' && userId ? Number(userId) : undefined,
        custom_token: customToken.trim() || undefined,
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {isEditing
              ? mode === 'admin' ? 'Chỉnh Sửa Token & Scopes' : 'Chỉnh sửa MCP Token'
              : mode === 'admin' ? 'Cấp MCP Access Token Mới' : 'Tạo MCP Access Token mới'}
          </DialogTitle>
          <DialogDescription>
            {isEditing
              ? 'Cập nhật tên gợi nhớ, thời hạn hoặc thay đổi trực tiếp quyền hạn (scopes).'
              : 'Tạo token ủy quyền kết nối API cho một thiết bị hoặc tài khoản người dùng.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-2">
          {mode === 'admin' && !isEditing && (
            <div className="space-y-1.5">
              <Label htmlFor="admin-token-user" className="text-xs font-semibold">
                Chọn người dùng nhận token *
              </Label>
              <NativeSelect
                id="admin-token-user"
                value={String(userId)}
                onChange={(e) => setUserId(e.target.value)}
                className="w-full text-xs"
              >
                {!userId && <NativeSelectOption value="">-- Chọn người dùng --</NativeSelectOption>}
                {users?.map((u) => (
                  <NativeSelectOption key={u.id} value={String(u.id)}>
                    {u.display_name || u.username} ({u.username} - {u.email})
                  </NativeSelectOption>
                ))}
              </NativeSelect>
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor={isEditing ? 'edit-token-name' : 'mcp-token-name'} className="text-xs font-semibold">
              Tên gợi nhớ (Client / Thiết bị) *
            </Label>
            <Input
              id={isEditing ? 'edit-token-name' : 'mcp-token-name'}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={mode === 'admin' ? 'VD: Claude Desktop PC, ChatGPT Connector...' : 'Ví dụ: Claude Desktop - MacBook Pro'}
              className="text-xs"
              maxLength={120}
              required
            />
          </div>

          {mode === 'admin' && !isEditing && (
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Chuỗi Secret Token (Tùy chọn)</Label>
              <Input
                value={customToken}
                onChange={(e) => setCustomToken(e.target.value)}
                placeholder="Dán chuỗi token hoặc để trống để sinh tự động"
                className="text-xs font-mono"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor={isEditing ? 'edit-token-expiry' : 'mcp-token-expiry'} className="text-xs font-semibold">
              Thời hạn hiệu lực
            </Label>
            <NativeSelect
              id={isEditing ? 'edit-token-expiry' : 'mcp-token-expiry'}
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="w-full text-xs"
            >
              {isEditing && <NativeSelectOption value="keep">Giữ nguyên thời hạn hiện tại</NativeSelectOption>}
              <NativeSelectOption value="180">6 tháng (180 ngày) - Mặc định</NativeSelectOption>
              <NativeSelectOption value="365">1 năm (365 ngày)</NativeSelectOption>
              <NativeSelectOption value="none">Vĩnh viễn (Không hết hạn)</NativeSelectOption>
              <NativeSelectOption value="90">3 tháng (90 ngày)</NativeSelectOption>
              <NativeSelectOption value="30">1 tháng (30 ngày)</NativeSelectOption>
              <NativeSelectOption value="7">7 ngày (Ngắn hạn / Test)</NativeSelectOption>
            </NativeSelect>
          </div>

          <div className="space-y-2 pt-2 border-t">
            <div className="flex flex-wrap items-center justify-between gap-1 text-xs font-semibold">
              <div className="flex items-center gap-1.5">
                <Shield className="size-4 text-primary shrink-0" />
                <span>Quyền hạn cấp cho Token ({scopes.length}/{ALL_MCP_SCOPES.length} Scopes)</span>
              </div>
              <div className="flex items-center gap-1">
                <Button type="button" variant="ghost" size="xs" onClick={() => setScopes(ALL_MCP_SCOPES.map((s) => s.key))} className="h-6 px-1.5 text-[11px]">
                  Chọn tất cả
                </Button>
                <Button type="button" variant="ghost" size="xs" onClick={() => setScopes([])} className="h-6 px-1.5 text-[11px]">
                  Bỏ chọn
                </Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-1.5 pb-1">
              {SCOPE_PRESETS.map((preset) => (
                <Button
                  key={preset.key}
                  type="button"
                  variant="outline"
                  size="xs"
                  onClick={() => handleApplyPreset(preset.key)}
                  className="h-6 px-2 text-[11px] gap-1"
                >
                  {preset.key === 'all' && <ShieldCheck className="size-3" />}
                  {preset.key === 'readonly' && <BookOpen className="size-3" />}
                  {preset.key === 'manager' && <FolderTree className="size-3" />}
                  {preset.key === 'study' && <Brain className="size-3" />}
                  <span>{preset.label}</span>
                </Button>
              ))}
            </div>

            <div className="space-y-2 max-h-56 overflow-y-auto border rounded-lg p-2.5 bg-muted/20">
              {SCOPE_CATEGORIES.map((cat) => (
                <div key={cat.key} className="space-y-1 pb-2 border-b last:border-b-0">
                  <div className="flex items-center justify-between text-xs font-semibold text-primary">
                    <span>{cat.name}</span>
                    <div className="flex gap-1 text-[10px]">
                      <button type="button" onClick={() => handleToggleCategory(cat.scopes, true)} className="hover:underline text-muted-foreground">Chọn hết</button>
                      <span>|</span>
                      <button type="button" onClick={() => handleToggleCategory(cat.scopes, false)} className="hover:underline text-muted-foreground">Bỏ chọn</button>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                    {ALL_MCP_SCOPES.filter((s) => s.category === cat.key).map((sc) => (
                      <label key={sc.key} className="flex items-center gap-2 p-1 rounded-md hover:bg-muted/50 cursor-pointer text-xs">
                        <Checkbox checked={scopes.includes(sc.key)} onCheckedChange={() => handleToggleScope(sc.key)} />
                        <span className="truncate" title={sc.desc}>{sc.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter className="pt-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Hủy
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || !name.trim() || scopes.length === 0 || (mode === 'admin' && !isEditing && !userId)}
            >
              {isSubmitting
                ? 'Đang lưu…'
                : isEditing
                ? mode === 'admin' ? 'Lưu thay đổi' : 'Lưu quyền hạn'
                : mode === 'admin' ? 'Cấp Token Mới' : 'Tạo Token mới'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
