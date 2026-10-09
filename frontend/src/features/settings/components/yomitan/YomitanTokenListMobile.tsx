import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { RefreshCw, Trash2 } from 'lucide-react'
import type { IntegrationToken } from '../../hooks/useYomitanTokenCRUD'

interface YomitanTokenListMobileProps {
  tokens: IntegrationToken[]
  isRotating: boolean
  isRevoking: boolean
  onRotate: (id: number) => void
  onRevoke: (id: number) => void
}

export function YomitanTokenListMobile({
  tokens,
  isRotating,
  isRevoking,
  onRotate,
  onRevoke,
}: YomitanTokenListMobileProps) {
  const { t, i18n } = useTranslation('settings')

  const displayDate = (value: string | null) => {
    if (!value) return t('yomitan.tokens.never_expires')
    return new Date(value).toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')
  }

  const renderStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <Badge variant="default" className="text-[11px] shrink-0">
          {t('yomitan.tokens.status_active')}
        </Badge>
      )
    }
    if (status === 'revoked') {
      return (
        <Badge variant="destructive" className="text-[11px] shrink-0">
          {t('yomitan.tokens.status_revoked')}
        </Badge>
      )
    }
    if (status === 'expired') {
      return (
        <Badge variant="secondary" className="text-[11px] shrink-0">
          {t('yomitan.tokens.status_expired')}
        </Badge>
      )
    }
    return (
      <Badge variant="secondary" className="text-[11px] shrink-0">
        {status}
      </Badge>
    )
  }

  return (
    <div className="grid gap-3.5 md:hidden">
      {tokens.map((token) => (
        <div key={token.id} className="rounded-xl border bg-card p-4 space-y-3 shadow-2xs">
          <div className="flex items-start justify-between gap-2">
            <div className="space-y-1 min-w-0">
              <div className="font-semibold text-sm truncate">{token.name}</div>
              <code className="text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded font-mono">
                {token.token_prefix}…
              </code>
            </div>
            {renderStatusBadge(token.status)}
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground pt-1 border-t">
            <div>
              <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">
                {t('yomitan.tokens.th_expiry')}
              </span>
              <span className="text-foreground font-medium">{displayDate(token.expires_at)}</span>
            </div>
            <div>
              <span className="block text-[10px] font-medium text-muted-foreground/70 uppercase">
                {t('yomitan.tokens.th_last_used')}
              </span>
              <span className="text-foreground font-medium">
                {token.last_used_at ? displayDate(token.last_used_at) : t('yomitan.tokens.never_used')}
              </span>
            </div>
          </div>

          {token.status === 'active' ? (
            <div className="flex gap-2 pt-2 border-t">
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-9 text-xs"
                disabled={isRotating}
                onClick={() =>
                  window.confirm(t('yomitan.tokens.confirm_rotate')) && onRotate(token.id)
                }
              >
                <RefreshCw className="mr-1.5 size-3.5 text-muted-foreground" />{' '}
                {t('yomitan.tokens.action_rotate')}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 h-9 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 border-destructive/30"
                disabled={isRevoking}
                onClick={() =>
                  window.confirm(t('yomitan.tokens.confirm_revoke')) && onRevoke(token.id)
                }
              >
                <Trash2 className="mr-1.5 size-3.5" /> {t('yomitan.tokens.action_revoke')}
              </Button>
            </div>
          ) : null}
        </div>
      ))}
    </div>
  )
}
