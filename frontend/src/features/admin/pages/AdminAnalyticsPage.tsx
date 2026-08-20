import { useState } from 'react'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import {
  useAnalyticsOverview,
  useContentGrowth,
  useRetentionCohorts,
  useStudyTime,
  useUserGrowth,
  type AnalyticsQueryParams,
} from '../api/analyticsApi'
import { AnalyticsKpiCards } from '../components/analytics/AnalyticsKpiCards'
import { CohortRetentionTable } from '../components/analytics/CohortRetentionTable'
import { ContentGrowthChart } from '../components/analytics/ContentGrowthChart'
import { DateRangeToolbar } from '../components/analytics/DateRangeToolbar'
import { HourlyDistributionChart } from '../components/analytics/HourlyDistributionChart'
import { StudyTimeChart } from '../components/analytics/StudyTimeChart'
import { TopLearnersTable } from '../components/analytics/TopLearnersTable'
import { UserGrowthChart } from '../components/analytics/UserGrowthChart'
import type { AnalyticsRangePreset } from '../types/analytics'

export function AdminAnalyticsPage() {
  const [preset, setPreset] = useState<AnalyticsRangePreset>('7d')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [isCustomActive, setIsCustomActive] = useState<boolean>(false)

  const queryParams: AnalyticsQueryParams = isCustomActive
    ? { startDate, endDate }
    : { range: preset }

  const overviewQuery = useAnalyticsOverview(queryParams)
  const userGrowthQuery = useUserGrowth(queryParams)
  const studyTimeQuery = useStudyTime(queryParams)
  const contentGrowthQuery = useContentGrowth(queryParams)
  const retentionCohortsQuery = useRetentionCohorts(8)

  const handlePresetChange = (newPreset: AnalyticsRangePreset) => {
    setIsCustomActive(false)
    setPreset(newPreset)
  }

  const handleApplyCustom = () => {
    if (startDate && endDate) {
      setIsCustomActive(true)
    }
  }

  const handleRefresh = () => {
    void overviewQuery.refetch()
    void userGrowthQuery.refetch()
    void studyTimeQuery.refetch()
    void contentGrowthQuery.refetch()
    void retentionCohortsQuery.refetch()
  }

  const isInitialLoading =
    overviewQuery.isPending ||
    userGrowthQuery.isPending ||
    studyTimeQuery.isPending ||
    contentGrowthQuery.isPending

  const error =
    overviewQuery.error ||
    userGrowthQuery.error ||
    studyTimeQuery.error ||
    contentGrowthQuery.error

  if (isInitialLoading) {
    return <PageLoading label="Đang tải dữ liệu phân tích và tăng trưởng hệ thống…" />
  }

  if (error) {
    return (
      <Page>
        <PageError error={error} />
      </Page>
    )
  }

  const overviewData = overviewQuery.data
  const userGrowthData = userGrowthQuery.data
  const studyTimeData = studyTimeQuery.data
  const contentGrowthData = contentGrowthQuery.data
  const cohortsData = retentionCohortsQuery.data

  return (
    <Page>
      <PageHeader
        title="Tổng quan & Tăng trưởng Quản trị"
        description="Theo dõi thời gian học trung bình, lịch sử tăng trưởng người dùng, tải nội dung và sức khỏe hệ sinh thái Flama."
      />

      {/* Date Range Selector Toolbar */}
      <DateRangeToolbar
        preset={preset}
        onPresetChange={handlePresetChange}
        startDate={startDate}
        endDate={endDate}
        onStartDateChange={setStartDate}
        onEndDateChange={setEndDate}
        onApplyCustom={handleApplyCustom}
        isCustomActive={isCustomActive}
        onRefresh={handleRefresh}
        isLoading={overviewQuery.isFetching}
      />

      {/* High-level KPI Summary Cards */}
      {overviewData ? <AnalyticsKpiCards data={overviewData} /> : null}

      {/* Row 1: Study Time & 24h Hourly Distribution */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {studyTimeData ? <StudyTimeChart data={studyTimeData} /> : null}
        </div>
        <div>
          {studyTimeData ? (
            <HourlyDistributionChart data={studyTimeData.hourly_distribution} />
          ) : null}
        </div>
      </div>

      {/* Row 2: User Growth & Content Growth */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {userGrowthData ? <UserGrowthChart data={userGrowthData} /> : null}
        </div>
        <div>
          {contentGrowthData ? <ContentGrowthChart data={contentGrowthData} /> : null}
        </div>
      </div>

      {/* Row 3: Cohort Retention Table */}
      {cohortsData ? <CohortRetentionTable cohorts={cohortsData.cohorts} /> : null}

      {/* Row 4: Top Active Learners Leaderboard */}
      {overviewData?.top_learners ? (
        <TopLearnersTable learners={overviewData.top_learners} />
      ) : null}
    </Page>
  )
}
export default AdminAnalyticsPage
