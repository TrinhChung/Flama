import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import { Plus, Trash2, Key, ShieldCheck, ShieldAlert } from 'lucide-react'
import { SearchInput } from '@/shared/ui'
import { Button } from '@/components/ui/button'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Card } from '@/components/ui/card'
import { useMcpTokens } from '../hooks/useMcpTokens'
import type { IssuedTokenResult, McpMode, McpToken } from '../types'
import { McpTokenTable } from './McpTokenTable'
import { McpCreateEditTokenModal } from './McpCreateEditTokenModal'
import { McpTokenSecretModal } from './McpTokenSecretModal'
import { McpTokenActionModals } from './McpTokenActionModals'
import { McpTokenInlineCreateCard } from './McpTokenInlineCreateCard'

export interface McpTokensManagerProps {
  mode: McpMode
  users?: Array<{ id: number; username: string; email: string; display_name?: string }>
  initialCreateUserId?: number | null
  onSuccessMutation?: () => void
  onSwitchToChatGPT?: () => void
  headerTitle?: string
  headerDescription?: string
  createLayout?: 'modal' | 'inline'
}

export function McpTokensManager({
  mode,
  users,
  initialCreateUserId,
  onSuccessMutation,
  headerTitle,
  headerDescription,
  createLayout = 'modal',
}: McpTokensManagerProps) {
  const { t } = useTranslation('mcp')
  const {
    tokens, isLoading, search, setSearch, statusFilter, setStatusFilter,
    page, setPage, totalPages, totalItems, inactiveCount, canManageTokens,
    createToken, updateToken, rotateToken, revokeToken, purgeToken, cleanupExpired,
    isCreating, isUpdating, isRotating, isRevoking, isPurging, isCleaningUp,
  } = useMcpTokens({ mode, userId: initialCreateUserId ?? undefined, onSuccessMutation })

  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [editingToken, setEditingToken] = useState<McpToken | null>(null)
  const [isPermissionsOnly, setIsPermissionsOnly] = useState(false)
  const [issuedResult, setIssuedResult] = useState<IssuedTokenResult | null>(null)
  const [rotatingToken, setRotatingToken] = useState<McpToken | null>(null)
  const [revokingTokenId, setRevokingTokenId] = useState<number | null>(null)
  const [purgingToken, setPurgingToken] = useState<McpToken | null>(null)
  const [isCleanupOpen, setIsCleanupOpen] = useState(false)
  const [viewingScopeToken, setViewingScopeToken] = useState<McpToken | null>(null)

  const activeCount = tokens.filter((t) => t.status === 'active').length

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-foreground">
            {headerTitle ||
              (createLayout === 'inline'
                ? t('manager.inline_title', { count: tokens.length })
                : mode === 'admin'
                ? t('manager.admin_title')
                : t('manager.title'))}
          </h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {headerDescription ||
              (mode === 'admin'
                ? t('manager.admin_desc')
                : t('manager.desc'))}
          </p>
        </div>

        {canManageTokens && (
          <div className="flex items-center gap-2 flex-wrap">
            {inactiveCount > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsCleanupOpen(true)}
                className="gap-1.5 text-xs"
              >
                <Trash2 className="size-3.5" />
                <span>{t('manager.cleanup_btn', { count: inactiveCount })}</span>
              </Button>
            )}

            {createLayout !== 'inline' && (
              <Button
                size="sm"
                onClick={() => {
                  setIsCreateOpen(true)
                  setIsPermissionsOnly(false)
                }}
                className="gap-1.5 text-xs font-semibold shadow-2xs"
              >
                <Plus className="size-3.5" />
                <span>{mode === 'admin' ? t('manager.admin_create_btn') : t('manager.create_btn')}</span>
              </Button>
            )}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Card className="p-3 bg-card/60">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">{t('manager.stats.total')}</span>
            <Key className="size-3.5 text-muted-foreground" />
          </div>
          <div className="text-xl font-bold mt-1">{totalItems}</div>
        </Card>

        <Card className="p-3 bg-card/60">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">{t('manager.stats.active')}</span>
            <ShieldCheck className="size-3.5 text-muted-foreground" />
          </div>
          <div className="text-xl font-bold mt-1">{activeCount}</div>
        </Card>

        <Card className="p-3 bg-card/60">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">{t('manager.stats.inactive')}</span>
            <ShieldAlert className="size-3.5 text-muted-foreground" />
          </div>
          <div className="text-xl font-bold mt-1">{inactiveCount}</div>
        </Card>
      </div>

      {canManageTokens && createLayout === 'inline' && (
        <McpTokenInlineCreateCard
          tokens={tokens}
          onCreateToken={async (payload) => {
            try {
              const res = await createToken(payload)
              setIssuedResult(res)
            } catch {}
          }}
          isCreating={isCreating}
        />
      )}

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex-1 max-w-sm">
          <SearchInput
            placeholder={t('manager.search_placeholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClear={() => setSearch('')}
            size="sm"
          />
        </div>

        <div className="flex items-center gap-2">
          <NativeSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'revoked' | 'expired')}
            size="sm"
            className="w-40 text-xs"
          >
            <NativeSelectOption value="all">{t('manager.filter.all')}</NativeSelectOption>
            <NativeSelectOption value="active">{t('manager.filter.active')}</NativeSelectOption>
            <NativeSelectOption value="revoked">{t('manager.filter.revoked')}</NativeSelectOption>
            <NativeSelectOption value="expired">{t('manager.filter.expired')}</NativeSelectOption>
          </NativeSelect>
        </div>
      </div>

      <McpTokenTable
        tokens={tokens}
        mode={mode}
        canManageTokens={canManageTokens}
        isLoading={isLoading}
        onEdit={(token) => {
          setEditingToken(token)
          setIsPermissionsOnly(false)
        }}
        onPermissionsEdit={(token) => {
          setEditingToken(token)
          setIsPermissionsOnly(true)
        }}
        onRotate={(token) => setRotatingToken(token)}
        onRevoke={(id) => setRevokingTokenId(id)}
        onPurge={(token) => setPurgingToken(token)}
        onViewScopes={(token) => setViewingScopeToken(token)}
        page={page}
        totalPages={totalPages}
        totalItems={totalItems}
        onPageChange={(p) => setPage(p)}
      />

      <McpCreateEditTokenModal
        open={isCreateOpen || Boolean(editingToken)}
        onOpenChange={(open) => {
          if (!open) {
            setIsCreateOpen(false)
            setEditingToken(null)
            setIsPermissionsOnly(false)
          }
        }}
        editingToken={editingToken}
        isPermissionsOnly={isPermissionsOnly}
        mode={mode}
        users={users}
        initialUserId={initialCreateUserId}
        isSubmitting={isCreating || isUpdating}
        onSubmitCreate={async (payload) => {
          try {
            const res = await createToken(payload)
            setIssuedResult(res)
            setIsCreateOpen(false)
          } catch {}
        }}
        onSubmitEdit={async (payload) => {
          try {
            await updateToken(payload)
            setEditingToken(null)
            setIsPermissionsOnly(false)
          } catch {}
        }}
      />

      <McpTokenSecretModal
        issuedToken={issuedResult}
        isOpen={Boolean(issuedResult)}
        onClose={() => setIssuedResult(null)}
        mode={mode}
      />

      <McpTokenActionModals
        mode={mode}
        rotatingToken={rotatingToken}
        onRotateClose={() => setRotatingToken(null)}
        isRotating={isRotating}
        onRotateConfirm={async (tokenId, expiryDays) => {
          try {
            const res = await rotateToken({ id: tokenId, expires_in_days: expiryDays })
            setIssuedResult(res)
            setRotatingToken(null)
          } catch {}
        }}
        revokingTokenId={revokingTokenId}
        onRevokeClose={() => setRevokingTokenId(null)}
        isRevoking={isRevoking}
        onRevokeConfirm={async (tokenId) => {
          try {
            await revokeToken(tokenId)
            setRevokingTokenId(null)
          } catch {}
        }}
        purgingToken={purgingToken}
        onPurgeClose={() => setPurgingToken(null)}
        isPurging={isPurging}
        onPurgeConfirm={async (tokenId) => {
          try {
            await purgeToken(tokenId)
            setPurgingToken(null)
          } catch {}
        }}
        isCleanupOpen={isCleanupOpen}
        inactiveCount={inactiveCount}
        onCleanupClose={() => setIsCleanupOpen(false)}
        isCleaningUp={isCleaningUp}
        onCleanupConfirm={async () => {
          try {
            await cleanupExpired()
            setIsCleanupOpen(false)
          } catch {}
        }}
        viewingScopeToken={viewingScopeToken}
        onScopeDetailsClose={() => setViewingScopeToken(null)}
      />
    </div>
  )
}
