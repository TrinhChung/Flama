import { useQuery } from '@tanstack/react-query'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { profileApi } from '../api/profileApi'
import { ProfileHeroCard } from '../components/ProfileHeroCard'
import { ProfileTransactionsTable } from '../components/ProfileTransactionsTable'
import { ProfileWalletCard } from '../components/ProfileWalletCard'

export function ProfilePage() {
  const { data, isPending, error } = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.getProfile(),
  })

  if (isPending) {
    return <PageLoading label="Đang tải thông tin hồ sơ và số dư ví…" />
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
        title="Trang cá nhân & Ví doanh thu"
        description=""
      />

      <div className="space-y-6">
        <ProfileHeroCard user={data.user} />

        <ProfileWalletCard wallet={data.wallet} />

        <ProfileTransactionsTable />
      </div>
    </Page>
  )
}
