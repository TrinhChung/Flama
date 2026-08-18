import { Calendar, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { AnalyticsRangePreset } from '../../types/analytics'

type DateRangeToolbarProps = {
  preset: AnalyticsRangePreset
  onPresetChange: (preset: AnalyticsRangePreset) => void
  startDate: string
  endDate: string
  onStartDateChange: (val: string) => void
  onEndDateChange: (val: string) => void
  onApplyCustom: () => void
  isCustomActive: boolean
  onRefresh: () => void
  isLoading?: boolean
}

const PRESET_OPTIONS: Array<{ value: AnalyticsRangePreset; label: string }> = [
  { value: 'today', label: 'Hôm nay' },
  { value: '7d', label: '7 ngày qua' },
  { value: '30d', label: '30 ngày qua' },
  { value: '90d', label: '90 ngày qua' },
  { value: '12m', label: '12 tháng qua' },
  { value: 'all', label: 'Toàn thời gian' },
]

export function DateRangeToolbar({
  preset,
  onPresetChange,
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onApplyCustom,
  isCustomActive,
  onRefresh,
  isLoading,
}: DateRangeToolbarProps) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border/80 bg-card p-3 shadow-xs md:flex-row md:items-center md:justify-between">
      {/* Preset pills */}
      <div className="flex flex-wrap items-center gap-1.5">
        {PRESET_OPTIONS.map((item) => {
          const active = !isCustomActive && preset === item.value
          return (
            <Button
              key={item.value}
              type="button"
              variant={active ? 'default' : 'outline'}
              size="sm"
              className={`h-8 text-xs font-medium transition-colors ${
                active ? 'bg-primary text-primary-foreground shadow-xs' : 'text-muted-foreground hover:text-foreground'
              }`}
              onClick={() => onPresetChange(item.value)}
            >
              {item.label}
            </Button>
          )
        })}
      </div>

      {/* Custom date range and refresh */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5">
          <Calendar className="size-3.5 text-muted-foreground" />
          <div className="flex items-center gap-1">
            <Label htmlFor="custom-start-date" className="sr-only">
              Ngày bắt đầu
            </Label>
            <Input
              id="custom-start-date"
              type="date"
              value={startDate}
              onChange={(e) => onStartDateChange(e.target.value)}
              className="h-8 w-32 px-2 text-xs"
            />
            <span className="text-xs text-muted-foreground">–</span>
            <Label htmlFor="custom-end-date" className="sr-only">
              Ngày kết thúc
            </Label>
            <Input
              id="custom-end-date"
              type="date"
              value={endDate}
              onChange={(e) => onEndDateChange(e.target.value)}
              className="h-8 w-32 px-2 text-xs"
            />
          </div>
          <Button
            type="button"
            variant={isCustomActive ? 'default' : 'secondary'}
            size="sm"
            className="h-8 text-xs font-medium"
            onClick={onApplyCustom}
          >
            Lọc
          </Button>
        </div>

        <Button
          type="button"
          variant="outline"
          size="icon"
          className="size-8"
          onClick={onRefresh}
          disabled={isLoading}
          title="Làm mới dữ liệu"
        >
          <RefreshCw className={`size-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="sr-only">Làm mới</span>
        </Button>
      </div>
    </div>
  )
}
