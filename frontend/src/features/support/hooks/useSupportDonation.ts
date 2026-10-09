import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import type {
  CheckoutResult,
  DonationStatusResult,
  SupportDonation,
} from '../types'

export function useSupportDonation() {
  const { t } = useTranslation('support')
  const queryClient = useQueryClient()
  const [searchParams] = useSearchParams()

  const paymentOrderId = (
    searchParams.get('payment_order_id') ||
    searchParams.get('order_id') ||
    ''
  ).trim()

  const supportProviderOrderCode = (
    searchParams.get('support_provider_order_code') ||
    searchParams.get('orderCode') ||
    searchParams.get('order_code') ||
    ''
  ).trim()

  const donationStatusQuery = useQuery({
    queryKey: ['support-donation-status', paymentOrderId, supportProviderOrderCode],
    queryFn: async () => {
      if (paymentOrderId) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          payment_order_id: paymentOrderId,
        })
      }
      if (supportProviderOrderCode) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          support_provider_order_code: supportProviderOrderCode,
        })
      }
      return null
    },
    enabled: Boolean(paymentOrderId || supportProviderOrderCode),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status) return false
      return status === 'pending_payment' || status === 'pending' ? 4000 : false
    },
  })

  const query = useQuery({
    queryKey: ['support-donation'],
    queryFn: () => appApi.get<SupportDonation>('/support-donation'),
  })

  const [amount, setAmount] = useState<number>(100000)
  const [anonymous, setAnonymous] = useState<boolean>(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)
  const [activeCheckout, setActiveCheckout] = useState<CheckoutResult | null>(null)
  const [isCheckoutModalOpen, setIsCheckoutModalOpen] = useState<boolean>(false)

  const checkoutMutation = useMutation({
    mutationFn: (payload: { amount_minor: number; anonymous: boolean }) =>
      appApi.mutate<CheckoutResult>('/support-donation/checkout', 'POST', {
        amount_minor: payload.amount_minor,
        anonymous: payload.anonymous,
        return_url: window.location.href,
        cancel_url: window.location.href,
      }),
    onSuccess: (result) => {
      if (result.checkout || result.checkout_url) {
        setActiveCheckout(result)
        setIsCheckoutModalOpen(true)
        toast.success(t('toast.checkout_created'))
      } else {
        toast.error(result.message || t('toast.checkout_failed'))
      }
    },
    onError: (error: Error) => {
      toast.error(t('toast.checkout_failed'), { description: error.message })
    },
  })

  const modalOrderCode =
    activeCheckout?.provider_order_code ||
    activeCheckout?.checkout?.provider_order_code
  const modalOrderId = activeCheckout?.order?.id

  const modalStatusQuery = useQuery({
    queryKey: ['support-modal-status', modalOrderCode, modalOrderId],
    queryFn: async () => {
      if (modalOrderId) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          payment_order_id: modalOrderId,
        })
      }
      if (modalOrderCode) {
        return appApi.get<DonationStatusResult>('/support-donation/status', {
          support_provider_order_code: modalOrderCode,
        })
      }
      return null
    },
    enabled: Boolean(isCheckoutModalOpen && (modalOrderId || modalOrderCode)),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'paid') {
        void queryClient.invalidateQueries({
          queryKey: ['support-donation-status'],
        })
        return false
      }
      return 3000
    },
  })

  const handleCopy = (text: string, fieldName: string) => {
    void navigator.clipboard.writeText(text)
    setCopiedField(fieldName)
    toast.success(t('toast.copied', { name: fieldName }))
    setTimeout(() => setCopiedField(null), 2000)
  }

  return {
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
  }
}
