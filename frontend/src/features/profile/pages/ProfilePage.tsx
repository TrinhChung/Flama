import { useState } from 'react'
import { BookOpen, GitPullRequest, Shapes } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { profileApi } from '../api/profileApi'
import { BadgesList } from '../components/BadgesList'
import { ContributionsTab } from '../components/ContributionsTab'
import { CreatorStatsOverview } from '../components/CreatorStatsOverview'
import { ProfileHeroCard } from '../components/ProfileHeroCard'
import { PublishedDecksTab } from '../components/PublishedDecksTab'
import { PublishedNoteTypesTab } from '../components/PublishedNoteTypesTab'

export function ProfilePage() {
  const { username } = useParams<{ username?: string }>()
  const [activeTab, setActiveTab] = useState<'decks' | 'noteTypes' | 'contributions'>('decks')

  // If username param is provided, fetch public profile
  // If not, fetch authenticated private profile first, then public details
  const isPublicRoute = Boolean(username)

  const publicQuery = useQuery({
    queryKey: ['public-profile', username],
    queryFn: () => profileApi.getPublicProfile(username!),
    enabled: isPublicRoute,
  })

  const privateQuery = useQuery({
    queryKey: ['profile'],
    queryFn: () => profileApi.getProfile(),
    enabled: !isPublicRoute,
  })

  // When on own profile (/profile), fetch own public portfolio content using current username
  const ownUsername = privateQuery.data?.user?.username
  const ownPortfolioQuery = useQuery({
    queryKey: ['public-profile', ownUsername],
    queryFn: () => profileApi.getPublicProfile(ownUsername!),
    enabled: !isPublicRoute && Boolean(ownUsername),
  })

  const isPending = isPublicRoute
    ? publicQuery.isPending
    : privateQuery.isPending || (Boolean(ownUsername) && ownPortfolioQuery.isPending)

  const error = isPublicRoute
    ? publicQuery.error
    : privateQuery.error || ownPortfolioQuery.error

  if (isPending) {
    return <PageLoading label="Đang tải hồ sơ và thông tin đóng góp…" />
  }

  if (error) {
    return (
      <Page>
        <PageError error={error} />
      </Page>
    )
  }

  const profileData = isPublicRoute
    ? publicQuery.data!
    : ownPortfolioQuery.data || {
        user: privateQuery.data!.user,
        stats: privateQuery.data!.creator_stats,
        badges: privateQuery.data!.badges,
        published_decks: [],
        published_note_types: [],
        contributions: [],
        is_own_profile: true,
      }

  const user = profileData.user
  const stats = profileData.stats || {
    created_decks_count: profileData.published_decks?.length || 0,
    created_note_types_count: profileData.published_note_types?.length || 0,
    total_installs_count: 0,
    rating_count: 0,
    rating_avg: 0,
    contributions_merged_count: profileData.contributions?.length || 0,
    total_contributions_count: 0,
  }
  const badges = profileData.badges || []
  const publishedDecks = profileData.published_decks || []
  const publishedNoteTypes = profileData.published_note_types || []
  const contributions = profileData.contributions || []
  const isOwnProfile = isPublicRoute ? profileData.is_own_profile : true

  return (
    <Page>
      <PageHeader
        title={isOwnProfile ? 'Hồ sơ cá nhân & Đóng góp' : `Hồ sơ Creator: ${user.display_name || user.username}`}
        description=""
      />

      <div className="space-y-6">
        {/* Main Hero Header */}
        <ProfileHeroCard user={user} isOwnProfile={isOwnProfile} />

        {/* Creator Stats Overview */}
        <CreatorStatsOverview stats={stats} />

        {/* Badges / Milestones */}
        <BadgesList badges={badges} />

        {/* Portfolio Tabs Header */}
        <div className="space-y-4 pt-2">
          <div className="flex border-b border-border/60">
            <button
              type="button"
              onClick={() => setActiveTab('decks')}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition cursor-pointer ${
                activeTab === 'decks'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <BookOpen className="size-3.5" />
              <span>Học liệu đã tạo ({publishedDecks.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('noteTypes')}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition cursor-pointer ${
                activeTab === 'noteTypes'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Shapes className="size-3.5" />
              <span>Loại thẻ ({publishedNoteTypes.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('contributions')}
              className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition cursor-pointer ${
                activeTab === 'contributions'
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <GitPullRequest className="size-3.5" />
              <span>Đóng góp cộng đồng ({contributions.length})</span>
            </button>
          </div>

          {/* Portfolio Tabs Content */}
          <div className="pt-2">
            {activeTab === 'decks' ? (
              <PublishedDecksTab
                decks={publishedDecks}
                authorUsername={user.username}
              />
            ) : null}

            {activeTab === 'noteTypes' ? (
              <PublishedNoteTypesTab noteTypes={publishedNoteTypes} />
            ) : null}

            {activeTab === 'contributions' ? (
              <ContributionsTab contributions={contributions} />
            ) : null}
          </div>
        </div>
      </div>
    </Page>
  )
}
