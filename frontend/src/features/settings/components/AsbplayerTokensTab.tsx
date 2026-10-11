import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/shared/components/PageState'
import { RefreshCw } from 'lucide-react'
import type { useAsbplayerTokenCRUD } from '../hooks/useAsbplayerTokenCRUD'
import { AsbplayerCreateTokenCard } from './asbplayer/AsbplayerCreateTokenCard'
import { AsbplayerTokenListMobile } from './asbplayer/AsbplayerTokenListMobile'
import { AsbplayerTokenListDesktop } from './asbplayer/AsbplayerTokenListDesktop'

type AsbplayerTokenCrudResult = ReturnType<typeof useAsbplayerTokenCRUD>

interface AsbplayerTokensTabProps {
  hookResult: AsbplayerTokenCrudResult
}

export function AsbplayerTokensTab({ hookResult }: AsbplayerTokensTabProps) {
  const { t } = useTranslation('settings')
  const {
    tokens,
    name,
    setName,
    expiry,
    setExpiry,
    preset,
    setPreset,
    copied,
    copy,
    issuedConnectUrl,
    issuedMiningKey,
    refresh,
    createMutation,
    revokeMutation,
    rotateMutation,
    setupMiningMutation,
  } = hookResult

  return (
    <div className="space-y-6">
      <AsbplayerCreateTokenCard
        name={name}
        setName={setName}
        expiry={expiry}
        setExpiry={setExpiry}
        preset={preset}
        setPreset={setPreset}
        isPending={createMutation.isPending}
        onCreate={() => createMutation.mutate()}
        issuedConnectUrl={issuedConnectUrl}
        issuedMiningKey={issuedMiningKey}
        onSetupMining={() => setupMiningMutation.mutate()}
        isPreparingMining={setupMiningMutation.isPending}
        copied={copied}
        onCopy={copy}
      />

      {/* Tokens List */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base sm:text-lg font-bold">
              {t('asbplayer.tokens.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('asbplayer.tokens.description')}
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={refresh}
            title={t('asbplayer.tokens.refresh_tooltip')}
            className="h-8 px-2.5 text-xs"
          >
            <RefreshCw className="size-3.5 mr-1" /> {t('asbplayer.tokens.refresh')}
          </Button>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0">
          {!tokens.length ? (
            <EmptyState
              title={t('asbplayer.tokens.empty_title')}
              description={t('asbplayer.tokens.empty_desc')}
            />
          ) : (
            <>
              <AsbplayerTokenListMobile
                tokens={tokens}
                isRotating={rotateMutation.isPending}
                isRevoking={revokeMutation.isPending}
                onRotate={(id) => rotateMutation.mutate(id)}
                onRevoke={(id) => revokeMutation.mutate(id)}
                onCopy={copy}
              />
              <AsbplayerTokenListDesktop
                tokens={tokens}
                isRotating={rotateMutation.isPending}
                isRevoking={revokeMutation.isPending}
                onRotate={(id) => rotateMutation.mutate(id)}
                onRevoke={(id) => revokeMutation.mutate(id)}
                onCopy={copy}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
