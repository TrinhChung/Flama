import { useTranslation } from 'react-i18next'
import {
  Award,
  GitPullRequest,
  GraduationCap,
  Shield,
  Star,
  Trophy,
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ProfileBadge } from '../types/profile'

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  Shield,
  Star,
  Award,
  GitPullRequest,
  GraduationCap,
  Trophy,
}

export function BadgesList({ badges }: { badges: ProfileBadge[] }) {
  const { t } = useTranslation('profile')
  if (!badges || badges.length === 0) return null

  return (
    <Card className="border-border/60 bg-gradient-to-r from-background via-muted/20 to-background shadow-xs">
      <CardHeader className="pb-2.5 pt-3.5 px-4 sm:px-5">
        <CardTitle className="flex items-center gap-2 text-xs sm:text-sm font-bold tracking-tight text-foreground">
          <Trophy className="size-4 text-amber-500" />
          {t('badges.title')}
        </CardTitle>
      </CardHeader>
      <CardContent className="px-4 sm:px-5 pb-4">
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
          {badges.map((b) => {
            const IconComp = ICON_MAP[b.icon] || Award

            let badgeStyle = 'border-border/60 bg-muted/40 text-foreground'
            let iconStyle = 'bg-primary/10 text-primary'

            if (b.tier === 'system') {
              badgeStyle = 'border-amber-500/30 bg-amber-500/10 text-amber-900 dark:text-amber-300'
              iconStyle = 'bg-amber-500 text-amber-950'
            } else if (b.tier === 'creator') {
              badgeStyle = 'border-primary/30 bg-primary/10 text-primary'
              iconStyle = 'bg-primary text-primary-foreground'
            } else if (b.tier === 'highlight') {
              badgeStyle = 'border-orange-500/30 bg-orange-500/10 text-orange-800 dark:text-orange-300'
              iconStyle = 'bg-orange-500 text-white'
            } else if (b.tier === 'community') {
              badgeStyle = 'border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300'
              iconStyle = 'bg-emerald-500 text-white'
            } else if (b.tier === 'verified') {
              badgeStyle = 'border-blue-500/30 bg-blue-500/10 text-blue-800 dark:text-blue-300'
              iconStyle = 'bg-blue-500 text-white'
            }

            return (
              <div
                key={b.id}
                className={`flex items-start gap-3 rounded-xl border p-3 shadow-2xs transition hover:scale-[1.01] ${badgeStyle}`}
              >
                <div
                  className={`flex size-8 shrink-0 items-center justify-center rounded-lg shadow-2xs ${iconStyle}`}
                >
                  <IconComp className="size-4" />
                </div>
                <div className="space-y-0.5 min-w-0">
                  <h4 className="text-xs font-bold truncate leading-snug">
                    {b.name}
                  </h4>
                  <p className="text-[11px] text-muted-foreground line-clamp-2 leading-tight">
                    {b.description}
                  </p>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
