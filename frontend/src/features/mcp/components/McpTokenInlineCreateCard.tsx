import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { KeyRound, Key, Shield, AlertCircle, ShieldCheck, BookOpen, FolderTree, Brain } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import type { CreateTokenPayload, McpToken } from '../types'
import { ALL_MCP_SCOPES, SCOPE_CATEGORIES, SCOPE_PRESETS } from '../types'

export interface McpTokenInlineCreateCardProps {
  tokens: McpToken[]
  onCreateToken: (payload: CreateTokenPayload) => Promise<void>
  isCreating?: boolean
}

export function McpTokenInlineCreateCard({ tokens, onCreateToken, isCreating = false }: McpTokenInlineCreateCardProps) {
  const { t } = useTranslation('mcp')
  const [name, setName] = useState('Claude Desktop / Cursor IDE')
  const [expiry, setExpiry] = useState('180')
  const [selectedScopes, setSelectedScopes] = useState<string[]>(ALL_MCP_SCOPES.map((s) => s.key))

  const isDuplicateName = tokens.some(
    (t) => t.status === 'active' && t.name.trim().toLowerCase() === name.trim().toLowerCase()
  )

  const handlePreset = (presetKey: string) => {
    const preset = SCOPE_PRESETS.find((p) => p.key === presetKey)
    if (preset) setSelectedScopes([...preset.scopes])
  }

  const toggleScope = (scopeKey: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeKey) ? prev.filter((k) => k !== scopeKey) : [...prev, scopeKey]
    )
  }

  const handleSubmit = async () => {
    if (!name.trim() || selectedScopes.length === 0 || isCreating) return
    await onCreateToken({
      name: name.trim(),
      expires_in_days: expiry === 'none' ? null : Number(expiry),
      scopes: selectedScopes,
    })
  }

  return (
    <Card className="shadow-2xs border-primary/20">
      <CardHeader className="p-4 sm:p-6 pb-3">
        <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
          <KeyRound className="size-5 text-primary shrink-0" />
          {t('inline_create.title')}
        </CardTitle>
        <CardDescription className="text-xs sm:text-sm">
          {t('inline_create.desc')}{' '}
          <Link to="/guide/integrations/mcp-ai" className="text-primary hover:underline font-medium inline-flex items-center gap-0.5">
            {t('inline_create.json_guide_link')}
          </Link>
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-6 pt-0 space-y-5">
        <div className="grid gap-4 md:grid-cols-[1fr_220px_auto] md:items-end">
          <div className="space-y-2">
            <Label htmlFor="mcp-token-name" className="text-xs font-semibold">{t('inline_create.name_label')}</Label>
            <Input id="mcp-token-name" value={name} maxLength={120} placeholder={t('inline_create.name_placeholder')} className="h-10 text-sm" onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="mcp-token-expiry" className="text-xs font-semibold">{t('inline_create.expiry_label')}</Label>
            <NativeSelect id="mcp-token-expiry" className="w-full h-10 text-sm" value={expiry} onChange={(e) => setExpiry(e.target.value)}>
              <NativeSelectOption value="180">{t('modal.expiry_options.days_180')}</NativeSelectOption>
              <NativeSelectOption value="365">{t('modal.expiry_options.days_365')}</NativeSelectOption>
              <NativeSelectOption value="none">{t('modal.expiry_options.none')}</NativeSelectOption>
              <NativeSelectOption value="90">{t('modal.expiry_options.days_90')}</NativeSelectOption>
              <NativeSelectOption value="30">{t('modal.expiry_options.days_30')}</NativeSelectOption>
              <NativeSelectOption value="7">{t('modal.expiry_options.days_7')}</NativeSelectOption>
            </NativeSelect>
          </div>
          <Button size="lg" className="w-full md:w-auto h-10 font-semibold shadow-2xs gap-2" disabled={!name.trim() || selectedScopes.length === 0 || isCreating} onClick={handleSubmit}>
            <Key className="size-4" />
            {isCreating ? t('inline_create.submitting_btn') : t('inline_create.submit_btn')}
          </Button>
        </div>

        {isDuplicateName && (
          <div className="flex items-center gap-2 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-900 dark:text-amber-200 text-xs">
            <AlertCircle className="size-4 text-amber-600 shrink-0" />
            <span>{t('inline_create.duplicate_warning')}</span>
          </div>
        )}

        <div className="space-y-3 pt-2 border-t">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="text-xs font-semibold text-foreground flex items-center gap-1.5 flex-wrap">
              <Shield className="size-4 text-primary shrink-0" />
              <span>{t('inline_create.scopes_header', { count: selectedScopes.length, total: ALL_MCP_SCOPES.length })}</span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[11px] text-muted-foreground font-medium mr-1">{t('inline_create.presets_label')}</span>
              {SCOPE_PRESETS.map((preset) => (
                <Button key={preset.key} type="button" variant="outline" size="xs" className="text-[11px] h-6 px-2 gap-1 rounded-md" onClick={() => handlePreset(preset.key)}>
                  {preset.key === 'all' && <ShieldCheck className="size-3" />}
                  {preset.key === 'readonly' && <BookOpen className="size-3" />}
                  {preset.key === 'manager' && <FolderTree className="size-3" />}
                  {preset.key === 'study' && <Brain className="size-3" />}
                  <span>{t(`scopes.presets.${preset.key}.label`, preset.label)}</span>
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 pt-1 max-h-48 overflow-y-auto">
            {SCOPE_CATEGORIES.map((cat) => (
              <div key={cat.key} className="rounded-lg border bg-muted/20 p-2 space-y-1 text-xs">
                <span className="font-semibold text-primary block">{t(`scopes.categories.${cat.key}.name`, cat.name)}</span>
                {ALL_MCP_SCOPES.filter((s) => s.category === cat.key).map((sc) => (
                  <label key={sc.key} className="flex items-center gap-1.5 cursor-pointer py-0.5 hover:text-primary">
                    <Checkbox checked={selectedScopes.includes(sc.key)} onCheckedChange={() => toggleScope(sc.key)} />
                    <span className="truncate text-[11px]">{t(`scopes.items.${sc.key.replace(/[-:]/g, '_')}.label`, sc.label)}</span>
                  </label>
                ))}
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
