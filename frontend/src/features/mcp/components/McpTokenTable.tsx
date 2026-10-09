import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  Key,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  RefreshCw,
  Pencil,
  Clock,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { StatusPill } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from '@/components/ui/table'
import type { McpMode, McpToken } from '../types'
import { ALL_MCP_SCOPES } from '../types'

export interface McpTokenTableProps {
  tokens: McpToken[]
  mode: McpMode
  canManageTokens?: boolean
  isLoading?: boolean
  onEdit: (token: McpToken) => void
  onPermissionsEdit?: (token: McpToken) => void
  onRotate: (token: McpToken) => void
  onRevoke: (tokenId: number) => void
  onPurge: (token: McpToken) => void
  onViewScopes: (token: McpToken) => void
  page?: number
  totalPages?: number
  totalItems?: number
  onPageChange?: (page: number) => void
}

function formatDate(isoString: string | null | undefined, neverExpiresText: string, lang: string): string {
  if (!isoString) return neverExpiresText
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return isoString
    return d.toLocaleDateString(lang === 'en' ? 'en-US' : 'vi-VN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return isoString
  }
}

export function McpTokenTable({
  tokens,
  mode,
  canManageTokens = true,
  isLoading = false,
  onEdit,
  onPermissionsEdit,
  onRotate,
  onRevoke,
  onPurge,
  onViewScopes,
  page = 1,
  totalPages = 1,
  onPageChange,
}: McpTokenTableProps) {
  const { t, i18n } = useTranslation('mcp')

  const displayDate = (isoString: string | null | undefined) =>
    formatDate(isoString, t('table.never_expires'), i18n.language)

  const renderStatusPill = (status: string) => {
    if (status === 'active') {
      return <StatusPill variant="active" dot dotStyle="solid">{t('table.status.active')}</StatusPill>
    }
    if (status === 'revoked') {
      return <StatusPill variant="revoked">{t('table.status.revoked')}</StatusPill>
    }
    if (status === 'expired') {
      return <StatusPill variant="due">{t('table.status.expired')}</StatusPill>
    }
    return <StatusPill variant="pending">{t('table.status.exhausted')}</StatusPill>
  }

  if (!isLoading && tokens.length === 0) {
    return (
      <div className="text-center py-12 border rounded-xl bg-card/40">
        <Key className="size-8 text-muted-foreground/40 mx-auto mb-2" />
        <h4 className="text-sm font-semibold text-foreground">
          {mode === 'admin' ? t('table.empty.admin_title') : t('table.empty.user_title')}
        </h4>
        <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
          {mode === 'admin' ? t('table.empty.admin_desc') : t('table.empty.user_desc')}
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40">
              {mode === 'admin' && <TableHead className="font-semibold">{t('table.cols.owner')}</TableHead>}
              <TableHead className="font-semibold">{t('table.cols.name')}</TableHead>
              <TableHead className="font-semibold">{t('table.cols.status')}</TableHead>
              <TableHead className="font-semibold">{t('table.cols.expiry')}</TableHead>
              <TableHead className="font-semibold">{t('table.cols.scopes')}</TableHead>
              <TableHead className="font-semibold">{t('table.cols.last_used')}</TableHead>
              <TableHead className="text-right font-semibold">{t('table.cols.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tokens.map((token) => {
              const tokenScopes = token.scopes || []
              const isFullAccess = tokenScopes.length === ALL_MCP_SCOPES.length
              const isReadOnly =
                tokenScopes.length > 0 &&
                tokenScopes.every((s) => s.includes(':read') || s === 'note:check')

              return (
                <TableRow key={token.id}>
                  {mode === 'admin' && (
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-semibold text-xs">{token.username || t('table.unknown_user')}</span>
                        <span className="text-[10px] text-muted-foreground">{token.email}</span>
                      </div>
                    </TableCell>
                  )}

                  <TableCell className="font-medium text-xs sm:text-sm">
                    <div className="flex items-center gap-2">
                      <Key className="size-3.5 text-primary shrink-0" />
                      <span className="font-semibold">{token.name || 'MCP Token'}</span>
                      {token.client_name && (
                        <Badge variant="outline" className="text-[10px] py-0 px-1 text-muted-foreground">
                          OAuth: {token.client_name}
                        </Badge>
                      )}
                    </div>
                  </TableCell>

                  <TableCell>{renderStatusPill(token.status)}</TableCell>

                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    <div className="flex items-center gap-1.5 font-medium">
                      <Clock className="size-3 text-muted-foreground/80 shrink-0" />
                      <span>{displayDate(token.expires_at)}</span>
                    </div>
                  </TableCell>

                  <TableCell>
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-1.5 text-[11px] font-semibold gap-1 text-primary hover:text-primary hover:bg-primary/10"
                        onClick={() => onViewScopes(token)}
                        title={t('table.actions_tooltip.view_scopes_details')}
                      >
                        <Shield className="size-3" />
                        <span>{t('table.scopes_count', { count: tokenScopes.length })}</span>
                      </Button>
                      {isFullAccess && (
                        <Badge variant="outline" className="text-[10px] text-purple-600 dark:text-purple-400 border-purple-500/30 py-0">
                          {t('table.full_access')}
                        </Badge>
                      )}
                      {isReadOnly && (
                        <Badge variant="outline" className="text-[10px] text-sky-600 dark:text-sky-400 border-sky-500/30 py-0">
                          {t('table.read_only')}
                        </Badge>
                      )}
                    </div>
                  </TableCell>

                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {token.last_used_at ? displayDate(token.last_used_at) : mode === 'admin' ? t('table.admin_never_used') : t('table.never_used')}
                  </TableCell>

                  <TableCell className="text-right whitespace-nowrap">
                    {canManageTokens ? (
                      <div className="flex items-center justify-end gap-1">
                        {mode === 'user' && (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-indigo-600 hover:bg-indigo-50 hover:text-indigo-700 dark:hover:bg-indigo-950/40"
                            title={t('table.actions_tooltip.permissions')}
                            onClick={() => onPermissionsEdit?.(token)}
                          >
                            <ShieldCheck className="size-3.5" />
                          </Button>
                        )}

                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-8 text-muted-foreground hover:text-foreground"
                          title={mode === 'admin' ? t('table.actions_tooltip.edit_admin') : t('table.actions_tooltip.edit_user')}
                          onClick={() => onEdit(token)}
                        >
                          <Pencil className="size-3.5" />
                        </Button>

                        <Button
                          size="icon"
                          variant="ghost"
                          className="size-8 text-amber-600 hover:bg-amber-50 hover:text-amber-700 dark:hover:bg-amber-950/40"
                          title={mode === 'admin' ? t('table.actions_tooltip.rotate_admin') : t('table.actions_tooltip.rotate_user')}
                          onClick={() => onRotate(token)}
                        >
                          <RefreshCw className="size-3.5" />
                        </Button>

                        {token.status === 'active' ? (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/40"
                            title={t('table.actions_tooltip.revoke')}
                            onClick={() => onRevoke(token.id)}
                          >
                            <ShieldAlert className="size-3.5" />
                          </Button>
                        ) : (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="size-8 text-destructive hover:bg-destructive/10"
                            title={mode === 'admin' ? t('table.actions_tooltip.purge_admin') : t('table.actions_tooltip.purge_user')}
                            onClick={() => onPurge(token)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        )}
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-8 gap-1 text-xs text-muted-foreground hover:text-foreground"
                        title={t('table.actions_tooltip.view_scopes_details')}
                        onClick={() => onViewScopes(token)}
                      >
                        <Shield className="size-3.5 text-primary" />
                        <span>{t('table.view_scopes')}</span>
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {totalPages > 1 && onPageChange && (
        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-muted-foreground">{t('table.pagination.page_info', { page, totalPages })}</p>
          <div className="flex items-center gap-1.5">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange(page - 1)} className="gap-1 text-xs">
              <ChevronLeft className="size-3.5" /> {t('table.pagination.prev')}
            </Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} className="gap-1 text-xs">
              {t('table.pagination.next')} <ChevronRight className="size-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
