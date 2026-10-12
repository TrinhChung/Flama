import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Copy, RefreshCw, Trash2 } from 'lucide-react'
import { FLAMA_ANKI_CONNECT_URL } from '@/config/env'
import type { IntegrationToken } from '../../hooks/useYomitanTokenCRUD'

interface AsbplayerTokenListDesktopProps {
  tokens: IntegrationToken[]
  isRotating: boolean
  isRevoking: boolean
  onRotate: (id: number) => void
  onRevoke: (id: number) => void
  onCopy?: (label: string, value: string) => void
}

export function AsbplayerTokenListDesktop({
  tokens,
  isRotating,
  isRevoking,
  onRotate,
  onRevoke,
  onCopy,
}: AsbplayerTokenListDesktopProps) {
  const { t, i18n } = useTranslation('settings')

  const displayDate = (value: string | null) => {
    if (!value) return t('asbplayer.tokens.never_expires')
    return new Date(value).toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')
  }

  const renderStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <Badge variant="default" className="text-[11px]">
          {t('asbplayer.tokens.status_active')}
        </Badge>
      )
    }
    if (status === 'revoked') {
      return (
        <Badge variant="destructive" className="text-[11px]">
          {t('asbplayer.tokens.status_revoked')}
        </Badge>
      )
    }
    if (status === 'expired') {
      return (
        <Badge variant="secondary" className="text-[11px]">
          {t('asbplayer.tokens.status_expired')}
        </Badge>
      )
    }
    return (
      <Badge variant="secondary" className="text-[11px]">
        {status}
      </Badge>
    )
  }

  const renderPresetBadge = (preset?: string) => {
    if (preset === 'mining-media') {
      return (
        <Badge
          variant="secondary"
          className="text-[10px] font-semibold bg-purple-500/10 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800"
        >
          {t('asbplayer.tokens.badge_media')}
        </Badge>
      )
    }
    return (
      <Badge
        variant="outline"
        className="text-[10px] font-semibold text-sky-700 dark:text-sky-300 border-sky-300 dark:border-sky-800"
      >
        {t('asbplayer.tokens.badge_text')}
      </Badge>
    )
  }

  const handleCopyPrefix = (prefix: string) => {
    if (onCopy) {
      onCopy('token-prefix', prefix)
    } else {
      navigator.clipboard.writeText(prefix)
    }
  }

  const handleCopyUrl = () => {
    if (onCopy) {
      onCopy('anki-connect-url', FLAMA_ANKI_CONNECT_URL)
    } else {
      navigator.clipboard.writeText(FLAMA_ANKI_CONNECT_URL)
    }
  }

  return (
    <div className="hidden md:block overflow-x-auto rounded-xl border">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead>{t('asbplayer.tokens.th_name')}</TableHead>
            <TableHead>{t('asbplayer.tokens.th_status')}</TableHead>
            <TableHead>{t('asbplayer.tokens.th_expiry')}</TableHead>
            <TableHead>{t('asbplayer.tokens.th_last_used')}</TableHead>
            <TableHead className="text-right">{t('asbplayer.tokens.th_actions')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tokens.map((token) => (
            <TableRow key={token.id} className="hover:bg-muted/30">
              <TableCell>
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm">{token.name}</span>
                  {renderPresetBadge(token.preset)}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <code className="text-[11px] text-muted-foreground">{token.token_prefix}…</code>
                  <button
                    type="button"
                    onClick={() => handleCopyPrefix(token.token_prefix)}
                    className="text-muted-foreground hover:text-foreground text-[10px] inline-flex items-center gap-0.5 transition-colors"
                    title="Sao chép prefix"
                  >
                    <Copy className="size-2.5" />
                  </button>
                </div>
              </TableCell>
              <TableCell>{renderStatusBadge(token.status)}</TableCell>
              <TableCell className="text-xs">{displayDate(token.expires_at)}</TableCell>
              <TableCell className="text-xs">
                {token.last_used_at ? displayDate(token.last_used_at) : t('asbplayer.tokens.never_used')}
              </TableCell>
              <TableCell className="text-right">
                {token.status === 'active' ? (
                  <div className="flex justify-end gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleCopyUrl}
                      title={t('asbplayer.tokens.action_copy_url')}
                      className="text-xs text-muted-foreground hover:text-foreground"
                    >
                      <Copy className="mr-1 size-3.5" />
                      URL
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={isRotating}
                      onClick={() =>
                        window.confirm(t('asbplayer.tokens.confirm_rotate')) && onRotate(token.id)
                      }
                    >
                      <RefreshCw className="mr-1 size-3.5 text-muted-foreground" />{' '}
                      {t('asbplayer.tokens.action_rotate')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      disabled={isRevoking}
                      onClick={() =>
                        window.confirm(t('asbplayer.tokens.confirm_revoke')) && onRevoke(token.id)
                      }
                    >
                      <Trash2 className="mr-1 size-3.5" /> {t('asbplayer.tokens.action_revoke')}
                    </Button>
                  </div>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
