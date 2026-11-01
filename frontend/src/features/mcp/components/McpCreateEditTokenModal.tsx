import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
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
  isPermissionsOnly?: boolean
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
  isPermissionsOnly = false,
}: McpCreateEditTokenModalProps) {
  const { t } = useTranslation('mcp')
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
    if ((!isPermissionsOnly && !name.trim()) || scopes.length === 0) return
    if (isEditing && editingToken) {
      await onSubmitEdit({
        id: editingToken.id,
        name: isPermissionsOnly ? editingToken.name : name.trim(),
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
      <DialogContent className="w-[95vw] sm:max-w-xl max-h-[90vh] flex flex-col overflow-hidden p-0 rounded-2xl border-border/60 shadow-2xl">
        <DialogHeader className="px-5 py-4 border-b bg-muted/20 text-left shrink-0">
          <DialogTitle>
            {isPermissionsOnly
              ? t('modal.title_permissions_only')
              : isEditing
              ? mode === 'admin' ? t('modal.title_edit_admin') : t('modal.title_edit_user')
              : mode === 'admin' ? t('modal.title_create_admin') : t('modal.title_create_user')}
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground mt-0.5">
            {isPermissionsOnly
              ? t('modal.desc_permissions_only')
              : isEditing
              ? t('modal.desc_edit')
              : t('modal.desc_create')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-w-0">
            {mode === 'admin' && !isEditing && (
              <div className="space-y-1.5">
                <Label htmlFor="admin-token-user" className="text-xs font-semibold">
                  {t('modal.select_user_label')}
                </Label>
                <NativeSelect
                  id="admin-token-user"
                  value={String(userId)}
                  onChange={(e) => setUserId(e.target.value)}
                  className="w-full text-xs"
                >
                  {!userId && <NativeSelectOption value="">{t('modal.select_user_placeholder')}</NativeSelectOption>}
                  {users?.map((u) => (
                    <NativeSelectOption key={u.id} value={String(u.id)}>
                      {u.display_name || u.username} ({u.username} - {u.email})
                    </NativeSelectOption>
                  ))}
                </NativeSelect>
              </div>
            )}

            {!isPermissionsOnly && (
              <div className="space-y-1.5">
                <Label htmlFor={isEditing ? 'edit-token-name' : 'mcp-token-name'} className="text-xs font-semibold">
                  {t('modal.name_label')}
                </Label>
                <Input
                  id={isEditing ? 'edit-token-name' : 'mcp-token-name'}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={mode === 'admin' ? t('modal.name_placeholder_admin') : t('modal.name_placeholder_user')}
                  className="text-xs"
                  maxLength={120}
                  required
                />
              </div>
            )}

            {mode === 'admin' && !isEditing && (
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">{t('modal.custom_token_label')}</Label>
                <Input
                  value={customToken}
                  onChange={(e) => setCustomToken(e.target.value)}
                  placeholder={t('modal.custom_token_placeholder')}
                  className="text-xs font-mono"
                />
              </div>
            )}

            {!isPermissionsOnly && (
              <div className="space-y-1.5">
                <Label htmlFor={isEditing ? 'edit-token-expiry' : 'mcp-token-expiry'} className="text-xs font-semibold">
                  {t('modal.expiry_label')}
                </Label>
                <NativeSelect
                  id={isEditing ? 'edit-token-expiry' : 'mcp-token-expiry'}
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                  className="w-full text-xs"
                >
                  {isEditing && <NativeSelectOption value="keep">{t('modal.expiry_options.keep')}</NativeSelectOption>}
                  <NativeSelectOption value="180">{t('modal.expiry_options.days_180')}</NativeSelectOption>
                  <NativeSelectOption value="365">{t('modal.expiry_options.days_365')}</NativeSelectOption>
                  <NativeSelectOption value="none">{t('modal.expiry_options.none')}</NativeSelectOption>
                  <NativeSelectOption value="90">{t('modal.expiry_options.days_90')}</NativeSelectOption>
                  <NativeSelectOption value="30">{t('modal.expiry_options.days_30')}</NativeSelectOption>
                  <NativeSelectOption value="7">{t('modal.expiry_options.days_7')}</NativeSelectOption>
                </NativeSelect>
              </div>
            )}

            <div className="space-y-2 pt-2 border-t">
              <div className="flex flex-wrap items-center justify-between gap-1 text-xs font-semibold">
                <span>{t('modal.scopes_count', { count: scopes.length, total: ALL_MCP_SCOPES.length })}</span>
                <div className="flex items-center gap-1">
                  <Button type="button" variant="ghost" size="xs" onClick={() => setScopes(ALL_MCP_SCOPES.map((s) => s.key))} className="h-6 px-1.5 text-[11px]">
                    {t('modal.select_all')}
                  </Button>
                  <Button type="button" variant="ghost" size="xs" onClick={() => setScopes([])} className="h-6 px-1.5 text-[11px]">
                    {t('modal.deselect_all')}
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
                    className="h-6 px-2 text-[11px]"
                  >
                    {t(`scopes.presets.${preset.key}.label`, preset.label)}
                  </Button>
                ))}
              </div>

              <div className="space-y-2 max-h-56 overflow-y-auto border rounded-lg p-2.5 bg-muted/20">
                {SCOPE_CATEGORIES.map((cat) => (
                  <div key={cat.key} className="space-y-1 pb-2 border-b last:border-b-0">
                    <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                      <span>{t(`scopes.categories.${cat.key}.name`, cat.name)}</span>
                      <div className="flex gap-1 text-[10px]">
                        <button type="button" onClick={() => handleToggleCategory(cat.scopes, true)} className="hover:underline text-muted-foreground">{t('modal.category_select_all')}</button>
                        <span>|</span>
                        <button type="button" onClick={() => handleToggleCategory(cat.scopes, false)} className="hover:underline text-muted-foreground">{t('modal.category_deselect_all')}</button>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                      {ALL_MCP_SCOPES.filter((s) => s.category === cat.key).map((sc) => (
                        <label key={sc.key} className="flex items-center gap-2 p-1 rounded-md hover:bg-muted/50 cursor-pointer text-xs">
                          <Checkbox checked={scopes.includes(sc.key)} onCheckedChange={() => handleToggleScope(sc.key)} />
                          <span className="truncate" title={t(`scopes.items.${sc.key.replace(/[-:]/g, '_')}.desc`, sc.desc)}>{t(`scopes.items.${sc.key.replace(/[-:]/g, '_')}.label`, sc.label)}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <DialogFooter className="px-5 py-3 border-t bg-muted/30 m-0 shrink-0 flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {t('modal.cancel')}
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting || (!isPermissionsOnly && !name.trim()) || scopes.length === 0 || (mode === 'admin' && !isEditing && !userId)}
            >
              {isSubmitting
                ? t('modal.saving')
                : isEditing
                ? mode === 'admin' ? t('modal.save_edit_admin') : t('modal.save_edit_user')
                : mode === 'admin' ? t('modal.save_create_admin') : t('modal.save_create_user')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
