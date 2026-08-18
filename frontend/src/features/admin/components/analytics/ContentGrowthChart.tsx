import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { BookPlus, DownloadCloud } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ContentGrowthResponse } from '../../types/analytics'

type ContentGrowthChartProps = {
  data: ContentGrowthResponse
}

function formatDateLabel(dateStr: string): string {
  try {
    const parts = dateStr.split('-')
    if (parts.length === 3) {
      return `${parts[2]}/${parts[1]}`
    }
  } catch {
    // fallback
  }
  return dateStr
}

export function ContentGrowthChart({ data }: ContentGrowthChartProps) {
  const chartData = data.data.map((d) => ({
    date: d.date,
    dateLabel: formatDateLabel(d.date),
    newDecks: d.new_decks,
    newNotes: d.new_notes,
    newCards: d.new_cards,
    deckInstalls: d.deck_installs,
    connectImports: d.connect_imports,
  }))

  const totalCards = data.data.reduce((acc, curr) => acc + curr.new_cards, 0)
  const totalImports = data.data.reduce((acc, curr) => acc + curr.connect_imports, 0)

  return (
    <Card className="border-border/80 bg-card shadow-xs">
      <CardHeader className="flex flex-col gap-2 pb-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <BookPlus className="size-4 text-purple-500" />
            Tăng trưởng Nội dung & Thẻ Flashcard
          </CardTitle>
          <p className="text-xs text-muted-foreground mt-0.5">
            Thống kê số lượng bộ thẻ, ghi chú, thẻ mới và phiên nhập từ Yomitan / Anki Sync.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg bg-purple-500/10 px-2.5 py-1 font-medium text-purple-700 dark:text-purple-300">
            <span>+{totalCards.toLocaleString()} thẻ mới</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg bg-teal-500/10 px-2.5 py-1 font-medium text-teal-700 dark:text-teal-300">
            <DownloadCloud className="size-3.5" />
            <span>{totalImports.toLocaleString()} phiên Yomitan/Anki</span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-2">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/50" />
              <XAxis
                dataKey="dateLabel"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
                minTickGap={20}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const item = payload[0].payload
                    return (
                      <div className="rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-md backdrop-blur-xs">
                        <div className="font-semibold text-foreground mb-1.5">{item.date}</div>
                        <div className="space-y-1 text-muted-foreground">
                          <div className="flex items-center justify-between gap-4">
                            <span>Thẻ mới (Cards):</span>
                            <span className="font-semibold text-purple-600 dark:text-purple-400">+{item.newCards}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Ghi chú mới (Notes):</span>
                            <span className="font-semibold text-foreground">+{item.newNotes}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Bộ thẻ mới (Decks):</span>
                            <span className="font-semibold text-foreground">+{item.newDecks}</span>
                          </div>
                          <div className="flex items-center justify-between gap-4">
                            <span>Nhập Yomitan/Anki:</span>
                            <span className="font-semibold text-teal-600 dark:text-teal-400">{item.connectImports}</span>
                          </div>
                        </div>
                      </div>
                    )
                  }
                  return null
                }}
              />
              <Legend
                verticalAlign="top"
                align="right"
                iconType="circle"
                wrapperStyle={{ fontSize: '11px', paddingBottom: '10px' }}
              />
              <Bar dataKey="newCards" name="Thẻ mới" fill="#a855f7" radius={[3, 3, 0, 0]} barSize={10} />
              <Bar dataKey="newNotes" name="Ghi chú mới" fill="#3b82f6" radius={[3, 3, 0, 0]} barSize={10} />
              <Bar dataKey="connectImports" name="Yomitan/Anki" fill="#14b8a6" radius={[3, 3, 0, 0]} barSize={10} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
