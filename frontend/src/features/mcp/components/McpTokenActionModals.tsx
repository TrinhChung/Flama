import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Check, Shield } from 'lucide-react'
import { ConfirmDialog } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import type { McpMode, McpToken } from '../types'
import { ALL_MCP_SCOPES } from '../types'

export interface McpTokenActionModalsProps {
  mode: McpMode
  rotatingToken: McpToken | null
  onRotateClose: () => void
  onRotateConfirm: (tokenId: number, expiryDays: number | null | 'none') => Promise<void>
  isRotating?: boolean
  revokingTokenId: number | null
  onRevokeClose: () => void
  onRevokeConfirm: (tokenId: number) => Promise<void>
  isRevoking?: boolean
  purgingToken: McpToken | null
  onPurgeClose: () => void
  onPurgeConfirm: (tokenId: number) => Promise<void>
  isPurging?: boolean
  isCleanupOpen: boolean
  inactiveCount: number
  onCleanupClose: () => void
  onCleanupConfirm: () => Promise<void>
  isCleaningUp?: boolean
  viewingScopeToken: McpToken | null
  onScopeDetailsClose: () => void
}

export function McpTokenActionModals({
  mode,
  rotatingToken,
  onRotateClose,
  onRotateConfirm,
  isRotating = false,
  revokingTokenId,
  onRevokeClose,
  onRevokeConfirm,
  isRevoking = false,
  purgingToken,
  onPurgeClose,
  onPurgeConfirm,
  isPurging = false,
  isCleanupOpen,
  inactiveCount,
  onCleanupClose,
  onCleanupConfirm,
  isCleaningUp = false,
  viewingScopeToken,
  onScopeDetailsClose,
}: McpTokenActionModalsProps) {
  const { t } = useTranslation('mcp')
  const [rotateExpiry, setRotateExpiry] = useState('180')

  useEffect(() => {
    if (!rotatingToken) {
      setRotateExpiry('180')
    }
  }, [rotatingToken])

  return (
    <>
      {/* 1. Rotate Secret ConfirmDialog */}
      <ConfirmDialog
        open={Boolean(rotatingToken)}
        onOpenChange={(open) => !open && onRotateClose()}
        variant="primary"
        title={mode === 'admin' ? t('actions.rotate.title_admin') : t('actions.rotate.title_user')}
        description={
          mode === 'admin'
            ? t('actions.rotate.desc_admin')
            : t('actions.rotate.desc_user')
        }
        confirmText={mode === 'admin' ? t('actions.rotate.confirm_admin') : t('actions.rotate.confirm_user')}
        isLoading={isRotating}
        onConfirm={async () => {
          if (rotatingToken) {
            await onRotateConfirm(
              rotatingToken.id,
              rotateExpiry === 'none' ? 'none' : Number(rotateExpiry)
            )
          }
        }}
      >
        <div className="mt-3 space-y-1.5">
          <label htmlFor="rotate-token-expiry" className="text-xs font-semibold text-foreground">
            {t('actions.rotate.expiry_label')}
          </label>
          <NativeSelect
            id="rotate-token-expiry"
            value={rotateExpiry}
            onChange={(e) => setRotateExpiry(e.target.value)}
            className="w-full text-xs"
          >
            <NativeSelectOption value="30">{t('actions.rotate.days_30')}</NativeSelectOption>
            <NativeSelectOption value="90">{t('actions.rotate.days_90')}</NativeSelectOption>
            <NativeSelectOption value="180">{t('actions.rotate.days_180')}</NativeSelectOption>
            <NativeSelectOption value="365">{t('actions.rotate.days_365')}</NativeSelectOption>
            <NativeSelectOption value="none">{t('actions.rotate.none')}</NativeSelectOption>
          </NativeSelect>
        </div>
      </ConfirmDialog>

      {/* 2. Revoke ConfirmDialog */}
      <ConfirmDialog
        open={revokingTokenId !== null}
        onOpenChange={(open) => !open && onRevokeClose()}
        variant="destructive"
        title={mode === 'admin' ? t('actions.revoke.title_admin') : t('actions.revoke.title_user')}
        description={
          mode === 'admin'
            ? t('actions.revoke.desc_admin')
            : t('actions.revoke.desc_user')
        }
        confirmText={mode === 'admin' ? t('actions.revoke.confirm_admin') : t('actions.revoke.confirm_user')}
        isLoading={isRevoking}
        onConfirm={async () => {
          if (revokingTokenId !== null) {
            await onRevokeConfirm(revokingTokenId)
          }
        }}
      />

      {/* 3. Purge ConfirmDialog */}
      <ConfirmDialog
        open={Boolean(purgingToken)}
        onOpenChange={(open) => !open && onPurgeClose()}
        variant="destructive"
        title={mode === 'admin' ? t('actions.purge.title_admin') : t('actions.purge.title_user')}
        description={t('actions.purge.desc', { name: purgingToken?.name || '' })}
        confirmText={mode === 'admin' ? t('actions.purge.confirm_admin') : t('actions.purge.confirm_user')}
        isLoading={isPurging}
        onConfirm={async () => {
          if (purgingToken) {
            await onPurgeConfirm(purgingToken.id)
          }
        }}
      />

      {/* 4. Cleanup ConfirmDialog */}
      <ConfirmDialog
        open={isCleanupOpen}
        onOpenChange={(open) => !open && onCleanupClose()}
        variant="primary"
        title={mode === 'admin' ? t('actions.cleanup.title_admin') : t('actions.cleanup.title_user')}
        description={
          mode === 'admin'
            ? t('actions.cleanup.desc_admin', { count: inactiveCount })
            : t('actions.cleanup.desc_user', { count: inactiveCount })
        }
        confirmText={mode === 'admin' ? t('actions.cleanup.confirm_admin') : t('actions.cleanup.confirm_user', { count: inactiveCount })}
        isLoading={isCleaningUp}
        onConfirm={onCleanupConfirm}
      />

      {/* 5. Scope Details Dialog */}
      <Dialog
        open={Boolean(viewingScopeToken)}
        onOpenChange={(open) => !open && onScopeDetailsClose()}
      >
        <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="size-5 text-primary" />
              {t('actions.scope_details.title', { name: viewingScopeToken?.name || '' })}
            </DialogTitle>
            <DialogDescription>
              {viewingScopeToken?.username
                ? t('actions.scope_details.admin_desc', { username: viewingScopeToken.username, email: viewingScopeToken.email || '' })
                : t('actions.scope_details.user_desc')}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2">
            {viewingScopeToken?.scopes?.length ? (
              <div className="grid grid-cols-1 gap-2">
                {viewingScopeToken.scopes.map((scopeKey) => {
                  const scopeMeta = ALL_MCP_SCOPES.find((s) => s.key === scopeKey)
                  return (
                    <div
                      key={scopeKey}
                      className="p-2 rounded-lg border bg-muted/30 flex items-start gap-2.5 text-xs"
                    >
                      <Check className="size-4 text-primary shrink-0 mt-0.5" />
                      <div>
                        <div className="font-semibold text-foreground">
                          {t(`scopes.items.${scopeKey.replace(/[-:]/g, '_')}.label`, scopeMeta?.label || scopeKey)}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {t(`scopes.items.${scopeKey.replace(/[-:]/g, '_')}.desc`, scopeMeta?.desc || scopeKey)}
                        </div>
                        <div className="text-[10px] font-mono text-muted-foreground/80 mt-0.5">
                          {scopeKey}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                {t('actions.scope_details.empty')}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button onClick={onScopeDetailsClose}>{t('actions.scope_details.close')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
