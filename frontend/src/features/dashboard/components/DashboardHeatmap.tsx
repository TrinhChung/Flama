import { StudyHeatmap } from '@/shared/components/StudyHeatmap'
import type { DashboardOverview } from '../types'

export type DashboardHeatmapProps = {
  overview?: DashboardOverview
  loading: boolean
  year: number
  onYearChange: (year: number) => void
}

export function DashboardHeatmap(props: DashboardHeatmapProps) {
  return <StudyHeatmap {...props} />
}
