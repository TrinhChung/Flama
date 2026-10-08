import { Flame } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { SupportCheckoutModal } from '../components/SupportCheckoutModal'
import { SupportDonationForm } from '../components/SupportDonationForm'
import { SupportManualTransfer } from '../components/SupportManualTransfer'
import { SupportStatusBanner } from '../components/SupportStatusBanner'
import { useSupportDonation } from '../hooks/useSupportDonation'

export function SupportPage() {
  const { t } = useTranslation('support')
  const queryClient = useQueryClient()
  const { data: bootstrap } = useBootstrap()
  const authenticated = Boolean(bootstrap?.user)

  const {
    query,
    donationStatusQuery,
    amount,
    setAmount,
    anonymous,
    setAnonymous,
    copiedField,
    activeCheckout,
    isCheckoutModalOpen,
    setIsCheckoutModalOpen,
    checkoutMutation,
    modalStatusQuery,
    handleCopy,
  } = useSupportDonation()

  if (query.isPending) return <PageLoading label={t('feedback.submitting')} />
  if (query.error) {
    return (
      <Page>
        <PageError error={query.error} />
      </Page>
    )
  }

  const support = query.data
  const minAmount = support.limits.min_amount_minor || 10000
  const maxAmount = support.limits.max_amount_minor || 50000000
  const suggested = support.limits.suggested_amounts.length
    ? support.limits.suggested_amounts
    : [20000, 50000, 100000, 200000, 500000]

  return (
    <Page className="space-y-6 sm:space-y-10 px-3 sm:px-6">
      {/* Hero Header */}
      <div className="relative overflow-hidden rounded-2xl sm:rounded-3xl border border-primary/20 bg-gradient-to-br from-card via-card to-primary/5 p-4 sm:p-6 md:p-10 shadow-xl">
        <div className="pointer-events-none absolute -right-10 -top-10 size-40 sm:size-60 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative z-10 max-w-3xl space-y-3 sm:space-y-4">
          <Badge
            className="border-primary/20 bg-primary/10 text-primary text-xs"
            variant="secondary"
          >
            <Flame className="size-3.5 fill-primary mr-1" />
            {t('donation.badge')}
          </Badge>
          <PageHeader
            title={support.title || t('donation.default_title')}
            description={support.description || t('donation.default_description')}
          />
        </div>
      </div>

      {/* Donation Status Banner when returning from PayOS */}
      {donationStatusQuery.data ? (
        <SupportStatusBanner
          data={donationStatusQuery.data}
          isFetching={donationStatusQuery.isFetching}
          onRefetch={() => void donationStatusQuery.refetch()}
        />
      ) : null}

      <div className="grid gap-6 sm:gap-8 lg:grid-cols-12">
        {/* Left Column: Interactive Online PayOS Donation Form */}
        <div className="lg:col-span-7 space-y-6">
          <SupportDonationForm
            amount={amount}
            setAmount={setAmount}
            suggested={suggested}
            minAmount={minAmount}
            maxAmount={maxAmount}
            anonymous={anonymous}
            setAnonymous={setAnonymous}
            authenticated={authenticated}
            isPending={checkoutMutation.isPending}
            error={checkoutMutation.error}
            onSubmit={() =>
              checkoutMutation.mutate({ amount_minor: amount, anonymous })
            }
          />
        </div>

        {/* Right Column: Manual Bank Transfer & QR Code */}
        <div className="lg:col-span-5 space-y-6">
          <SupportManualTransfer
            support={support}
            copiedField={copiedField}
            onCopy={handleCopy}
          />
        </div>
      </div>

      {/* Interactive PayOS Payment Modal */}
      <SupportCheckoutModal
        isOpen={isCheckoutModalOpen}
        onOpenChange={setIsCheckoutModalOpen}
        activeCheckout={activeCheckout}
        amount={amount}
        support={support}
        modalStatusQuery={modalStatusQuery}
        copiedField={copiedField}
        onCopy={handleCopy}
        onSuccessClose={() => {
          setIsCheckoutModalOpen(false)
          void queryClient.invalidateQueries({
            queryKey: ['support-donation-status'],
          })
          void donationStatusQuery.refetch()
        }}
      />
    </Page>
  )
}
