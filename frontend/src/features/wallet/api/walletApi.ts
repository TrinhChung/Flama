import { appApi } from '@/app/api'
import type { WalletSummary, WalletTransactionsResponse } from '../types/wallet'

export const walletApi = {
  getWallet(): Promise<WalletSummary> {
    return appApi.get<WalletSummary>('/api/wallet')
  },

  getTransactions(params?: {
    page?: number
    per_page?: number
    type?: string
  }): Promise<WalletTransactionsResponse> {
    const qs = new URLSearchParams()
    if (params?.page) qs.set('page', String(params.page))
    if (params?.per_page) qs.set('per_page', String(params.per_page))
    if (params?.type) qs.set('type', params.type)

    return appApi.get<WalletTransactionsResponse>(
      `/api/wallet/transactions${qs.toString() ? `?${qs.toString()}` : ''}`
    )
  },
}
