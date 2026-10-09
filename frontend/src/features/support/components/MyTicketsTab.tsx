import { Plus, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState } from '@/shared/components/PageState'
import { useMyTickets } from '../hooks/useMyTickets'
import { TicketCard } from './TicketCard'

interface MyTicketsTabProps {
  myTickets: ReturnType<typeof useMyTickets>
  onCreateClick: () => void
}

export function MyTicketsTab({ myTickets, onCreateClick }: MyTicketsTabProps) {
  const { t } = useTranslation('support')
  const {
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
  } = myTickets

  return (
    <div className="space-y-4">
      {/* Search & Filter Bar */}
      <Card className="shadow-2xs border-border/80 bg-card rounded-xl">
        <CardContent className="p-3.5 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder={t('feedback.search_placeholder')}
              value={ticketSearch}
              onChange={(e) => setTicketSearch(e.target.value)}
              className="pl-9 bg-card border-border/80 rounded-xl text-xs h-9 shadow-2xs text-foreground"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <NativeSelect
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-36 rounded-xl text-xs h-9 bg-card border-border/80 text-foreground shadow-2xs"
            >
              <NativeSelectOption value="all">{t('feedback.all_statuses')}</NativeSelectOption>
              <NativeSelectOption value="open">{t('status.open')}</NativeSelectOption>
              <NativeSelectOption value="in_progress">{t('status.in_progress')}</NativeSelectOption>
              <NativeSelectOption value="resolved">{t('status.resolved')}</NativeSelectOption>
              <NativeSelectOption value="closed">{t('status.closed')}</NativeSelectOption>
              <NativeSelectOption value="rejected">{t('status.rejected')}</NativeSelectOption>
            </NativeSelect>

            <NativeSelect
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="w-36 rounded-xl text-xs h-9 bg-card border-border/80 text-foreground shadow-2xs"
            >
              <NativeSelectOption value="all">{t('feedback.all_categories')}</NativeSelectOption>
              <NativeSelectOption value="bug">{t('category.bug.title')}</NativeSelectOption>
              <NativeSelectOption value="feature">{t('category.feature.title')}</NativeSelectOption>
              <NativeSelectOption value="ui">{t('category.ui.title')}</NativeSelectOption>
              <NativeSelectOption value="other">{t('category.other.title')}</NativeSelectOption>
            </NativeSelect>

            {(ticketSearch || statusFilter !== 'all' || categoryFilter !== 'all') && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="text-xs text-muted-foreground h-9 px-3"
              >
                {t('feedback.clear_filters')}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* List or Loading / Empty */}
      {myTicketsQuery.isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((n) => (
            <Card key={n} className="p-4 border-border/80 bg-card rounded-xl shadow-2xs">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-24 rounded-full" />
                  <Skeleton className="h-5 w-48 rounded-lg" />
                </div>
                <Skeleton className="h-4 w-full rounded-md" />
                <div className="flex gap-3 pt-1">
                  <Skeleton className="h-4 w-32 rounded-md" />
                  <Skeleton className="h-4 w-24 rounded-md" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : !myTicketsQuery.data?.items || myTicketsQuery.data.items.length === 0 ? (
        <EmptyState
          title={t('feedback.empty_tickets_title')}
          description={t('feedback.empty_tickets_desc')}
          action={
            <Button
              size="sm"
              onClick={onCreateClick}
              className="rounded-full font-bold px-6"
            >
              <Plus className="mr-1.5 size-4" /> {t('feedback.create_first_ticket')}
            </Button>
          }
        />
      ) : filteredTickets.length === 0 ? (
        <EmptyState
          title={t('feedback.empty_search_title')}
          description={t('feedback.empty_search_desc')}
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={clearFilters}
              className="rounded-full text-xs"
            >
              {t('feedback.clear_search_filters')}
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredTickets.map((ticket) => (
            <TicketCard
              key={ticket.id}
              ticket={ticket}
              isCopied={copiedTicketCode === ticket.ticket_code}
              onCopyCode={handleCopyCode}
            />
          ))}
        </div>
      )}
    </div>
  )
}
