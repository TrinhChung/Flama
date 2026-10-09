import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { appApi } from '@/app/api'

export type OrderRow = {
  id: string
  merchant_order_code: string
  title: string
  total_amount_display: string
  status: string
  status_label: string
  status_tone: string
  grant_status?: string
  grant_status_label?: string
  created_at_display: string
  serialized?: any
}

export type OrdersResponse = {
  items: OrderRow[]
  total: number
}

export function useOrders() {
  const { t } = useTranslation('orders')
  const queryClient = useQueryClient()
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null)
  const [syncingOrderId, setSyncingOrderId] = useState<string | null>(null)

  const ordersQuery = useQuery({
    queryKey: ['orders'],
    queryFn: () => appApi.get<OrdersResponse>('/orders'),
  })

  const orderDetailQuery = useQuery({
    queryKey: ['order-detail', selectedOrderId],
    queryFn: () => appApi.get<any>(`/api/payments/orders/${selectedOrderId}`),
    enabled: Boolean(selectedOrderId),
  })

  const handleSyncOrder = async (orderId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation()
    setSyncingOrderId(orderId)
    try {
      await appApi.get(`/api/payments/orders/${orderId}`)
      void queryClient.invalidateQueries({ queryKey: ['orders'] })
      void queryClient.invalidateQueries({ queryKey: ['order-detail', orderId] })
      toast.success(t('toast.status_updated'))
    } catch (err: any) {
      toast.error(t('toast.update_failed'), {
        description: err?.message || t('toast.try_again'),
      })
    } finally {
      setSyncingOrderId(null)
    }
  }

  return {
    ordersQuery,
    selectedOrderId,
    setSelectedOrderId,
    orderDetailQuery,
    syncingOrderId,
    handleSyncOrder,
  }
}
