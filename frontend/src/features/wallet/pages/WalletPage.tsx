import { useQuery } from '@tanstack/react-query'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { walletApi } from '../api/walletApi'
import { PayoutNoticeCard } from '../components/PayoutNoticeCard'
import { WalletSummaryCard } from '../components/WalletSummaryCard'
import { WalletTransactionsTable } from '../components/WalletTransactionsTable'

export function WalletPage() {
  const { data, isPending, error } = useQuery({
    queryKey: ['wallet-summary'],
    queryFn: () => walletApi.getWallet(),
  })

  if (isPending) {
    return <PageLoading label="Đang tải thông tin số dư ví và doanh thu…" />
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
        title="Ví cá nhân & Doanh thu"
        description="Quản lý số dư, theo dõi doanh thu bán học liệu và lịch sử giao dịch trên Flama"
      />

      <div className="space-y-6">
        <WalletSummaryCard wallet={data} />

        <PayoutNoticeCard message={data.payout_status_message} />

        <WalletTransactionsTable />
      </div>
    </Page>
  )
}
