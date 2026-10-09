import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import type { TicketItem } from '../types'

export function useMyTickets(enabled: boolean) {
  const { t } = useTranslation('support')
  const [ticketSearch, setTicketSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [copiedTicketCode, setCopiedTicketCode] = useState<string | null>(null)

  const myTicketsQuery = useQuery({
    queryKey: ['user', 'my-tickets'],
    queryFn: () => appApi.get<{ items: TicketItem[] }>('/tickets/my'),
    enabled,
  })

  const handleCopyCode = (e: React.MouseEvent, code: string) => {
    e.stopPropagation()
    void navigator.clipboard.writeText(code)
    setCopiedTicketCode(code)
    toast.success(t('toast.copied', { name: `[${code}]` }))
    setTimeout(() => {
      setCopiedTicketCode((prev) => (prev === code ? null : prev))
    }, 2000)
  }

  const clearFilters = () => {
    setTicketSearch('')
    setStatusFilter('all')
    setCategoryFilter('all')
  }

  const filteredTickets = useMemo(() => {
    const items = myTicketsQuery.data?.items || []
    return items.filter((ticket) => {
      if (ticketSearch.trim()) {
        const query = ticketSearch.toLowerCase()
        const matchCode = ticket.ticket_code?.toLowerCase().includes(query)
        const matchTitle = ticket.title?.toLowerCase().includes(query)
        const matchDesc = ticket.description?.toLowerCase().includes(query)
        if (!matchCode && !matchTitle && !matchDesc) return false
      }
      if (statusFilter !== 'all' && ticket.status !== statusFilter) {
        return false
      }
      if (categoryFilter !== 'all' && ticket.category !== categoryFilter) {
        return false
      }
      return true
    })
  }, [myTicketsQuery.data?.items, ticketSearch, statusFilter, categoryFilter])

  return {
    ticketSearch,
    setTicketSearch,
    statusFilter,
    setStatusFilter,
    categoryFilter,
    setCategoryFilter,
    copiedTicketCode,
    myTicketsQuery,
    filteredTickets,
    handleCopyCode,
    clearFilters,
  }
}
