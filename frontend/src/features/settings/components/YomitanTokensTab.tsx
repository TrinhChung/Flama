import { useTranslation } from 'react-i18next'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { EmptyState } from '@/shared/components/PageState'
import { RefreshCw } from 'lucide-react'
import type { useYomitanTokenCRUD } from '../hooks/useYomitanTokenCRUD'
import { YomitanCreateTokenCard } from './yomitan/YomitanCreateTokenCard'
import { YomitanTokenListMobile } from './yomitan/YomitanTokenListMobile'
import { YomitanTokenListDesktop } from './yomitan/YomitanTokenListDesktop'

type TokenCrudResult = ReturnType<typeof useYomitanTokenCRUD>

interface YomitanTokensTabProps {
  hookResult: TokenCrudResult
}

export function YomitanTokensTab({ hookResult }: YomitanTokensTabProps) {
  const { t } = useTranslation('settings')
  const {
    tokens,
    name,
    setName,
    expiry,
    setExpiry,
    copied,
    copy,
    issuedConnectUrl,
    refresh,
    createMutation,
    revokeMutation,
    rotateMutation,
  } = hookResult

  return (
    <div className="space-y-6">
      <YomitanCreateTokenCard
        name={name}
        setName={setName}
        expiry={expiry}
        setExpiry={setExpiry}
        isPending={createMutation.isPending}
        onCreate={() => createMutation.mutate()}
        issuedConnectUrl={issuedConnectUrl}
        copied={copied}
        onCopy={copy}
      />

      {/* Tokens List */}
      <Card className="shadow-2xs">
        <CardHeader className="p-4 sm:p-6 flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base sm:text-lg font-bold">
              {t('yomitan.tokens.title')}
            </CardTitle>
            <CardDescription className="text-xs">
              {t('yomitan.tokens.description')}
            </CardDescription>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={refresh}
            title={t('yomitan.tokens.refresh_tooltip')}
            className="h-8 px-2.5 text-xs"
          >
            <RefreshCw className="size-3.5 mr-1" /> {t('yomitan.tokens.refresh')}
          </Button>
        </CardHeader>
        <CardContent className="p-4 sm:p-6 pt-0">
          {!tokens.length ? (
            <EmptyState
              title={t('yomitan.tokens.empty_title')}
              description={t('yomitan.tokens.empty_desc')}
            />
          ) : (
            <>
              <YomitanTokenListMobile
                tokens={tokens}
                isRotating={rotateMutation.isPending}
                isRevoking={revokeMutation.isPending}
                onRotate={(id) => rotateMutation.mutate(id)}
                onRevoke={(id) => revokeMutation.mutate(id)}
              />
              <YomitanTokenListDesktop
                tokens={tokens}
                isRotating={rotateMutation.isPending}
                isRevoking={revokeMutation.isPending}
                onRotate={(id) => rotateMutation.mutate(id)}
                onRevoke={(id) => revokeMutation.mutate(id)}
              />
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
