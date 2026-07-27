import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Page, PageHeader, SectionCard, StatCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { useStatisticsConfig, useTodayFutureStats } from '../api'
import { FutureDueChart } from '../components/FutureDueChart'
import type { StatisticsFilters } from '../types'

function ChoiceTabs<T extends string>({
  value,
  items,
  onChange,
}: {
  value: T
  items: Array<{ label: string; value: T }>
  onChange: (value: T) => void
}) {
  return (
    <Tabs value={value} onValueChange={(next) => onChange(next as T)}>
      <TabsList className="w-full">
        {items.map((item) => (
          <TabsTrigger className="flex-1" value={item.value} key={item.value}>
            {item.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}

export function StatisticsPage() {
  const configQuery = useStatisticsConfig()
  const [filters, setFilters] = useState<StatisticsFilters>({
    scope: 'deck',
    deckId: null,
    historyRange: '12m',
    futureRange: '30',
    backlog: true,
  })

  useEffect(() => {
    if (configQuery.data && filters.deckId === null) {
      setFilters((current) => ({ ...current, deckId: configQuery.data.initial_deck_id }))
    }
  }, [configQuery.data, filters.deckId])

  const statsQuery = useTodayFutureStats(filters)

  if (configQuery.isPending) return <PageLoading label="Đang tải cấu hình thống kê…" />
  if (configQuery.error) return <Page><PageError error={configQuery.error} /></Page>
  const stats = statsQuery.data

  return (
    <Page>
      <PageHeader
        title="Thống kê học tập"
        description="Theo dõi khối lượng ôn và dự báo thẻ đến hạn theo deck hoặc toàn bộ collection."
      />

      <Card>
        <CardContent className="grid gap-5 p-4 md:grid-cols-3 md:p-6">
          <div className="space-y-2">
            <Label>Phạm vi</Label>
            <ChoiceTabs
              value={filters.scope}
              items={[{ label: 'Theo deck', value: 'deck' }, { label: 'Toàn collection', value: 'collection' }]}
              onChange={(scope) => setFilters((current) => ({ ...current, scope }))}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="statistics-deck">Deck</Label>
            <NativeSelect
              id="statistics-deck"
              className="w-full"
              disabled={filters.scope === 'collection'}
              value={filters.deckId === null ? '' : String(filters.deckId)}
              onChange={(event) => setFilters((current) => ({
                ...current,
                deckId: event.currentTarget.value ? Number(event.currentTarget.value) : null,
              }))}
            >
              <NativeSelectOption value="">Chọn deck</NativeSelectOption>
              {configQuery.data.decks.map((deck) => (
                <NativeSelectOption key={deck.id} value={String(deck.id)}>{deck.id}: {deck.name}</NativeSelectOption>
              ))}
            </NativeSelect>
          </div>
          <div className="space-y-2">
            <Label>Lịch sử</Label>
            <ChoiceTabs
              value={filters.historyRange}
              items={[{ label: '12 tháng', value: '12m' }, { label: 'Tất cả', value: 'all' }]}
              onChange={(historyRange) => setFilters((current) => ({ ...current, historyRange }))}
            />
          </div>
        </CardContent>
      </Card>

      {statsQuery.error ? <PageError error={statsQuery.error} /> : null}
      {statsQuery.isFetching && !stats ? <PageLoading label="Đang tính thống kê…" /> : null}

      {stats ? (
        <>
          <Alert>
            <Activity />
            <AlertTitle>Hôm nay</AlertTitle>
            <AlertDescription>{stats.today.message}</AlertDescription>
          </Alert>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Tổng lượt ôn" value={stats.totals.total_reviews.toLocaleString('vi-VN')} tone="primary" />
            <StatCard label="Trung bình/ngày" value={stats.totals.avg_reviews_per_day.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} />
            <StatCard label="Đến hạn ngày mai" value={stats.totals.due_tomorrow.toLocaleString('vi-VN')} tone="warning" />
            <StatCard label="Tải hằng ngày" value={stats.totals.daily_load.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} tone="success" />
          </div>
          <SectionCard
            title="Thẻ đến hạn trong tương lai"
            description="Biểu đồ dùng shadcn Chart và hiển thị số review theo độ lệch ngày."
            actions={
              <div className="flex items-center gap-2">
                <Switch
                  id="backlog"
                  checked={filters.backlog}
                  onCheckedChange={(backlog) => setFilters((current) => ({ ...current, backlog }))}
                />
                <Label htmlFor="backlog" className="whitespace-nowrap">Tính backlog</Label>
              </div>
            }
          >
            <div className="space-y-5">
              <ChoiceTabs
                value={filters.futureRange}
                items={[
                  { label: '1 tháng', value: '30' },
                  { label: '3 tháng', value: '90' },
                  { label: '1 năm', value: '365' },
                  { label: 'Tất cả', value: 'all' },
                ]}
                onChange={(futureRange) => setFilters((current) => ({ ...current, futureRange }))}
              />
              <FutureDueChart series={stats.future_due.series} />
              <p className="text-right text-xs text-muted-foreground">Múi giờ: {stats.timezone}</p>
            </div>
          </SectionCard>
        </>
      ) : null}
    </Page>
  )
}
