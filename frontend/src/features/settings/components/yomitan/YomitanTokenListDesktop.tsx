import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { RefreshCw, Trash2 } from 'lucide-react'
import type { IntegrationToken } from '../../hooks/useYomitanTokenCRUD'

interface YomitanTokenListDesktopProps {
  tokens: IntegrationToken[]
  isRotating: boolean
  isRevoking: boolean
  onRotate: (id: number) => void
  onRevoke: (id: number) => void
}

export function YomitanTokenListDesktop({
  tokens,
  isRotating,
  isRevoking,
  onRotate,
  onRevoke,
}: YomitanTokenListDesktopProps) {
  const { t, i18n } = useTranslation('settings')

  const displayDate = (value: string | null) => {
    if (!value) return t('yomitan.tokens.never_expires')
    return new Date(value).toLocaleString(i18n.language === 'en' ? 'en-US' : 'vi-VN')
  }

  const renderStatusBadge = (status: string) => {
    if (status === 'active') {
      return (
        <Badge variant="default" className="text-[11px]">
          {t('yomitan.tokens.status_active')}
        </Badge>
      )
    }
    if (status === 'revoked') {
      return (
        <Badge variant="destructive" className="text-[11px]">
          {t('yomitan.tokens.status_revoked')}
        </Badge>
      )
    }
    if (status === 'expired') {
      return (
        <Badge variant="secondary" className="text-[11px]">
          {t('yomitan.tokens.status_expired')}
        </Badge>
      )
    }
    return (
      <Badge variant="secondary" className="text-[11px]">
        {status}
      </Badge>
    )
  }

  return (
    <div className="hidden md:block overflow-x-auto rounded-xl border">
      <Table>
        <TableHeader className="bg-muted/50">
          <TableRow>
            <TableHead>{t('yomitan.tokens.th_name')}</TableHead>
            <TableHead>{t('yomitan.tokens.th_status')}</TableHead>
            <TableHead>{t('yomitan.tokens.th_expiry')}</TableHead>
            <TableHead>{t('yomitan.tokens.th_last_used')}</TableHead>
            <TableHead className="text-right">{t('yomitan.tokens.th_actions')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tokens.map((token) => (
            <TableRow key={token.id} className="hover:bg-muted/30">
              <TableCell>
                <div className="font-semibold text-sm">{token.name}</div>
                <code className="text-[11px] text-muted-foreground">{token.token_prefix}…</code>
              </TableCell>
              <TableCell>{renderStatusBadge(token.status)}</TableCell>
              <TableCell className="text-xs">{displayDate(token.expires_at)}</TableCell>
              <TableCell className="text-xs">
                {token.last_used_at ? displayDate(token.last_used_at) : t('yomitan.tokens.never_used')}
              </TableCell>
              <TableCell className="text-right">
                {token.status === 'active' ? (
                  <div className="flex justify-end gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={isRotating}
                      onClick={() =>
                        window.confirm(t('yomitan.tokens.confirm_rotate')) && onRotate(token.id)
                      }
                    >
                      <RefreshCw className="mr-1 size-3.5 text-muted-foreground" />{' '}
                      {t('yomitan.tokens.action_rotate')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive hover:bg-destructive/10"
                      disabled={isRevoking}
                      onClick={() =>
                        window.confirm(t('yomitan.tokens.confirm_revoke')) && onRevoke(token.id)
                      }
                    >
                      <Trash2 className="mr-1 size-3.5" /> {t('yomitan.tokens.action_revoke')}
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
