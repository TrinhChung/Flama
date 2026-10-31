import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { KeyRound, AlertTriangle, Check, Copy, LinkIcon } from 'lucide-react'
import { CodeSnippetBox } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import type { IssuedTokenResult, McpMode } from '../types'
import { useMcpTokenSecret } from '../hooks/useMcpTokenSecret'

export interface McpTokenSecretModalProps {
  issuedToken: IssuedTokenResult | null
  isOpen?: boolean
  onClose: () => void
  mode?: McpMode
}

export function McpTokenSecretModal({
  issuedToken,
  isOpen,
  onClose,
  mode = 'user',
}: McpTokenSecretModalProps) {
  const { t } = useTranslation('mcp')
  const showModal = isOpen !== undefined ? isOpen : Boolean(issuedToken)
  const { serverUrl, jsonConfig, copiedToken, copiedUrl, handleCopyToken, handleCopyUrl } =
    useMcpTokenSecret({ issuedToken, isOpen: showModal, mode })

  return (
    <Dialog open={showModal} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <KeyRound className="size-5 text-primary" />
            {t('secret_modal.title')}
          </DialogTitle>
          <DialogDescription>
            {t('secret_modal.desc')}
          </DialogDescription>
        </DialogHeader>

        {issuedToken && (
          <div className="space-y-4 py-2">
            <input
              type="text"
              readOnly
              value={issuedToken.token}
              className="sr-only font-mono"
              tabIndex={-1}
              aria-hidden="true"
            />

            <div className="p-3 rounded-lg border bg-muted/40 text-xs space-y-1">
              <div><strong>{t('secret_modal.token_name_label')}</strong> {issuedToken.name}</div>
              {issuedToken.username && <div><strong>{t('secret_modal.owner_label')}</strong> {issuedToken.username}</div>}
              {issuedToken.expires_at && <div><strong>{t('secret_modal.expiry_label')}</strong> {issuedToken.expires_at}</div>}
            </div>

            <div className="flex items-start gap-2.5 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-800 dark:text-amber-300">
              <AlertTriangle className="size-4 shrink-0 mt-0.5" />
              <span>{t('secret_modal.one_time_warning')}</span>
            </div>

            <div className="rounded-lg border bg-muted/20 overflow-hidden text-sm">
              <div className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground font-mono">{t('secret_modal.bearer_header')}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={handleCopyToken}
                  className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copiedToken ? <Check className="size-3 text-emerald-500" /> : <Copy className="size-3" />}
                  <span>{copiedToken ? t('secret_modal.copied') : t('secret_modal.copy')}</span>
                </Button>
              </div>
              <pre className="p-3 overflow-x-auto font-mono text-xs text-foreground">
                <code>{issuedToken.token}</code>
              </pre>
            </div>

            <div className="rounded-lg border bg-muted/20 overflow-hidden text-sm">
              <div className="flex items-center justify-between border-b border-border/80 bg-muted/40 px-3 py-1.5 text-xs text-muted-foreground">
                <span className="font-medium text-foreground font-mono">{t('secret_modal.endpoint_header')}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="xs"
                  onClick={handleCopyUrl}
                  className="h-6 gap-1 px-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted"
                >
                  {copiedUrl ? <Check className="size-3 text-emerald-500" /> : <LinkIcon className="size-3" />}
                  <span>{copiedUrl ? t('secret_modal.copied') : t('secret_modal.copy_url')}</span>
                </Button>
              </div>
              <pre className="p-3 overflow-x-auto font-mono text-xs text-foreground">
                <code>{serverUrl}</code>
              </pre>
            </div>

            <CodeSnippetBox
              code={jsonConfig}
              language="json"
              title={t('secret_modal.json_snippet_title')}
              showCopyButton
            />
          </div>
        )}

        <DialogFooter className="flex-row justify-end gap-2">
          <Button variant="outline" onClick={onClose}>{t('secret_modal.close_btn')}</Button>
          <Button onClick={onClose}>{t('secret_modal.saved_and_close_btn')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
