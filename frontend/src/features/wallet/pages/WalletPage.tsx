import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { walletApi } from '../api/walletApi'
import { PayoutNoticeCard } from '../components/PayoutNoticeCard'
import { WalletSummaryCard } from '../components/WalletSummaryCard'
import { WalletTransactionsTable } from '../components/WalletTransactionsTable'

export function WalletPage() {
  const { t } = useTranslation('wallet')
  const { data, isPending, error } = useQuery({
    queryKey: ['wallet-summary'],
    queryFn: () => walletApi.getWallet(),
  })

  if (isPending) {
    return <PageLoading label={t('loading')} />
  }

  if (error) {
    return (
      <Page>
        <PageError error={error} />
      </Page>
    )
  }

  return (
    <Page>
      <PageHeader
        title={t('header.title')}
        description={t('header.description')}
      />

      <div className="space-y-6">
        <WalletSummaryCard wallet={data} />

        <PayoutNoticeCard message={data.payout_status_message} />

        <WalletTransactionsTable />
      </div>
    </Page>
  )
}
