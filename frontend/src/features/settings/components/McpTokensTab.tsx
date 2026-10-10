import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  ArrowRight,
  BookOpen,
  ChartNoAxesColumn,
  Check,
  Copy,
  FolderTree,
  Image,
  Info,
  Layers,
  MessagesSquare,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { TabsContent } from '@/components/ui/tabs'
import { BACKEND_ORIGIN, FLAMA_MCP_URL } from '@/config/env'
import { useBootstrap } from '@/shared/api/bootstrap'
import { McpTokensManager } from '@/features/mcp/components/McpTokensManager'
import { ALL_MCP_SCOPES, SCOPE_CATEGORIES } from '../hooks/useMcpTokenCRUD'

export interface McpTokensTabProps {
  hookResult?: any
  onSwitchToChatGPT?: () => void
}

function getCategoryIcon(key: string) {
  switch (key) {
    case 'decks':
      return FolderTree
    case 'notes':
      return BookOpen
    case 'note_types':
      return Layers
    case 'study_stats':
      return ChartNoAxesColumn
    case 'media':
      return Image
    default:
      return FolderTree
  }
}

export function McpTokensTab({ onSwitchToChatGPT }: McpTokensTabProps) {
  const { t } = useTranslation('mcp')
  const { data: bootstrap } = useBootstrap()
  const canManageTokens = Boolean(
    bootstrap?.user?.is_admin || bootstrap?.user?.can_manage_mcp_tokens
  )

  const [copiedEndpoint, setCopiedEndpoint] = useState<string | null>(null)
  const defaultBase = BACKEND_ORIGIN || window.location.origin
  const mcpServerUrl = FLAMA_MCP_URL || `${defaultBase}/api/mcp`

  const copyEndpoint = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopiedEndpoint(label)
      window.setTimeout(() => setCopiedEndpoint(null), 2000)
      toast.success(t('tokens_tab.endpoint_card.copied_toast', { label }))
    } catch {
      toast.error(t('tokens_tab.endpoint_card.copy_failed_toast'))
    }
  }

  return (
    <TabsContent value="tokens" className="space-y-6">
      {onSwitchToChatGPT && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 sm:p-4 rounded-xl border bg-muted/40">
          <div className="flex items-center gap-3">
            <MessagesSquare className="size-5 text-muted-foreground shrink-0" />
            <div className="space-y-0.5">
              <div className="text-xs sm:text-sm font-bold text-foreground">
                {t('tokens_tab.chatgpt_banner.question')}
              </div>
              <p className="text-[11px] sm:text-xs text-muted-foreground">
                {t('tokens_tab.chatgpt_banner.instruction')}
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={onSwitchToChatGPT}
            className="h-8 text-xs gap-1.5 shrink-0 w-full sm:w-auto justify-center"
          >
            <span>{t('tokens_tab.chatgpt_banner.button')}</span>
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      )}

      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <CardTitle className="text-base sm:text-lg font-bold">
                  {t('tokens_tab.endpoint_card.title')}
                </CardTitle>
                <Badge variant="outline" className="text-[10px] text-muted-foreground font-mono">
                  {t('tokens_tab.endpoint_card.badge')}
                </Badge>
              </div>
              <CardDescription className="text-xs sm:text-sm">
                {t('tokens_tab.endpoint_card.desc')}
              </CardDescription>
            </div>
            <div className="flex items-center gap-2 shrink-0 self-start sm:self-center">
              <Link
                to="/guide/integrations/mcp-ai"
                className="text-xs text-primary hover:underline font-medium inline-flex items-center gap-1"
              >
                <BookOpen className="size-3.5" />
                <span>{t('tokens_tab.endpoint_card.guide_link')}</span>
              </Link>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-xl border bg-muted/40 p-2.5 text-xs font-mono">
            <span className="text-muted-foreground font-sans text-[11px] font-semibold shrink-0">{t('tokens_tab.endpoint_card.url_label')}</span>
            <span className="flex-1 break-all select-all font-semibold text-foreground text-xs sm:text-sm">{mcpServerUrl}</span>
            <Button
              size="sm"
              variant="outline"
              className="shrink-0 h-8 gap-1.5 text-xs w-full sm:w-auto justify-center"
              onClick={() => copyEndpoint('Server URL', mcpServerUrl)}
            >
              {copiedEndpoint === 'Server URL' ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              <span>{copiedEndpoint === 'Server URL' ? t('tokens_tab.endpoint_card.copied_button') : t('tokens_tab.endpoint_card.copy_button')}</span>
            </Button>
          </div>

          <div className="flex items-start gap-2.5 p-2.5 rounded-lg border bg-muted/40 text-xs text-muted-foreground">
            <Info className="size-4 shrink-0 text-muted-foreground mt-0.5" />
            <div className="leading-relaxed text-[11px] sm:text-xs">
              <span className="font-semibold text-foreground">{t('tokens_tab.endpoint_card.claude_notice.label')} </span>
              {t('tokens_tab.endpoint_card.claude_notice.text')}
            </div>
          </div>
        </CardContent>
      </Card>

      {!canManageTokens && (
        <Card className="shadow-2xs">
          <CardHeader className="p-4 sm:p-5 pb-3">
            <div className="space-y-1">
              <CardTitle className="text-base sm:text-lg font-bold">
                {t('tokens_tab.managed_card.title')}
              </CardTitle>
              <CardDescription className="text-xs sm:text-sm leading-relaxed">
                {t('tokens_tab.managed_card.desc')}
              </CardDescription>
            </div>
          </CardHeader>
        </Card>
      )}

      {!canManageTokens && (
        <Card className="shadow-2xs">
          <CardHeader className="p-4 sm:p-6 pb-3">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <CardTitle className="text-base sm:text-lg font-bold">
                    {t('tokens_tab.all_scopes_card.title', { count: ALL_MCP_SCOPES.length })}
                  </CardTitle>
                  <Badge variant="secondary" className="text-[10px] font-medium">
                    {t('tokens_tab.all_scopes_card.granted_badge')}
                  </Badge>
                </div>
                <CardDescription className="text-xs sm:text-sm">
                  {t('tokens_tab.all_scopes_card.desc')}
                </CardDescription>
              </div>
              <Link to="/guide/integrations/mcp-tools" className="text-xs text-primary hover:underline font-normal shrink-0">
                {t('tokens_tab.all_scopes_card.tools_link')}
              </Link>
            </div>
          </CardHeader>
          <CardContent className="p-4 sm:p-6 pt-0 space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 pt-1">
              {SCOPE_CATEGORIES.map((cat) => {
                const CatIcon = getCategoryIcon(cat.key)
                const catScopes = ALL_MCP_SCOPES.filter((s) => s.category === cat.key)

                return (
                  <div
                    key={cat.key}
                    className="rounded-lg border p-3 space-y-2.5 flex flex-col justify-between"
                  >
                    <div className="space-y-2">
                      <div className="flex items-center justify-between gap-2 pb-1.5 border-b border-border/50">
                        <div className="flex items-center gap-1.5 min-w-0">
                          <CatIcon className="size-3.5 text-muted-foreground shrink-0" />
                          <span className="font-semibold text-xs text-foreground truncate">{t(`scopes.categories.${cat.key}.name`, cat.name)}</span>
                        </div>
                        <span className="text-[10px] font-medium text-muted-foreground shrink-0">
                          {t('tokens_tab.all_scopes_card.permissions_count', { count: catScopes.length, total: catScopes.length })}
                        </span>
                      </div>

                      <div className="space-y-1.5">
                        {catScopes.map((scope) => (
                          <div
                            key={scope.key}
                            className="flex items-start gap-2 py-0.5 text-xs"
                          >
                            <Check className="size-3.5 text-primary shrink-0 mt-0.5" />
                            <div className="min-w-0 flex-1">
                              <div className="font-medium text-[11px] leading-tight text-foreground">
                                {t(`scopes.items.${scope.key.replace(/[-:]/g, '_')}.label`, scope.label)}
                              </div>
                              <div className="text-[10px] text-muted-foreground leading-tight line-clamp-1 mt-0.5">
                                {t(`scopes.items.${scope.key.replace(/[-:]/g, '_')}.desc`, scope.desc)}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {canManageTokens && (
        <McpTokensManager
          mode="user"
          createLayout="inline"
          onSwitchToChatGPT={onSwitchToChatGPT}
        />
      )}
    </TabsContent>
  )
}
