import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Copy, RefreshCw, Trash2 } from 'lucide-react'
import { FLAMA_ANKI_CONNECT_URL } from '@/config/env'
import type { IntegrationToken } from '../../hooks/useYomitanTokenCRUD'

interface AsbplayerTokenListMobileProps {
  tokens: IntegrationToken[]
  isRotating: boolean
  isRevoking: boolean
  onRotate: (id: number) => void
  onRevoke: (id: number) => void
  onCopy?: (label: string, value: string) => void
}

export function AsbplayerTokenListMobile({
  tokens,
  isRotating,
  isRevoking,
  onRotate,
  onRevoke,
  onCopy,
}: AsbplayerTokenListMobileProps) {
  const { t, i18n } = useTranslation('settings')

  const displayDate = (value: string | null) => {
    if (!value) return t('asbplayer.tokens.never_expires')
    return new Date(value).toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')
  }

  const renderStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <Badge variant="default" className="text-[11px] shrink-0">
          {t('asbplayer.tokens.status_active')}
        </Badge>
      )
    }
    if (status === 'revoked') {
      return (
        <Badge variant="destructive" className="text-[11px] shrink-0">
          {t('asbplayer.tokens.status_revoked')}
        </Badge>
      )
    }
    if (status === 'expired') {
      return (
        <Badge variant="secondary" className="text-[11px] shrink-0">
          {t('asbplayer.tokens.status_expired')}
        </Badge>
      )
    }
    return (
      <Badge variant="secondary" className="text-[11px] shrink-0">
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
    <div className="grid gap-3.5 md:hidden">
      {tokens.map((token) => (
        <div key={token.id} className="rounded-xl border bg-card p-4 space-y-3 shadow-2xs">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-sm truncate">{token.name}</span>
                {renderPresetBadge(token.preset)}
              </div>
              <div className="flex items-center gap-1.5">
                <code className="text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded font-mono">
                  {token.token_prefix}…
                </code>
                <button
                  type="button"
                  onClick={() => handleCopyPrefix(token.token_prefix)}
                  className="text-muted-foreground hover:text-foreground text-[10px] inline-flex items-center gap-0.5 transition-colors"
                  title="Sao chép prefix"
                >
                  <Copy className="size-2.5" />
                </button>
              </div>
            </div>
            {renderStatusBadge(token.status)}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1 border-t">
            <div>
              <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">
                {t('asbplayer.tokens.th_expiry')}
              </span>
              <span className="text-foreground font-medium">{displayDate(token.expires_at)}</span>
            </div>
            <div>
              <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">
                {t('asbplayer.tokens.th_last_used')}
              </span>
              <span className="text-foreground font-medium">
                {token.last_used_at ? displayDate(token.last_used_at) : t('asbplayer.tokens.never_used')}
              </span>
            </div>
          </div>

          {token.status === 'active' ? (
            <div className="flex gap-2 pt-2 border-t">
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-9 text-xs"
                onClick={handleCopyUrl}
                title={t('asbplayer.tokens.action_copy_url')}
              >
                <Copy className="mr-1.5 size-3.5 text-muted-foreground" /> URL
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-9 text-xs"
                disabled={isRotating}
                onClick={() =>
                  window.confirm(t('asbplayer.tokens.confirm_rotate')) && onRotate(token.id)
                }
              >
                <RefreshCw className="mr-1.5 size-3.5 text-muted-foreground" />{' '}
                {t('asbplayer.tokens.action_rotate')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-9 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
                disabled={isRevoking}
                onClick={() =>
                  window.confirm(t('asbplayer.tokens.confirm_revoke')) && onRevoke(token.id)
                }
              >
                <Trash2 className="mr-1.5 size-3.5" /> {t('asbplayer.tokens.action_revoke')}
              </Button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}
