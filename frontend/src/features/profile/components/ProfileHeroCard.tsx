import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Award,
  Calendar,
  Camera,
  CheckCircle2,
  Clock,
  Edit3,
  ExternalLink,
  Globe,
  GraduationCap,
  Mail,
  MessageSquare,
  Shield,
  ShieldAlert,
  User as UserIcon,
} from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { resolveMediaUrl } from '@/shared/config/env'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { AvatarUploadModal } from './AvatarUploadModal'
import { EmailVerificationDialog } from './EmailVerificationDialog'
import { ProfileEditDialog } from './ProfileEditDialog'
import type { ProfileUser, SocialLink } from '../types/profile'

function SocialIcon({ type }: { type: string }) {
  const t = type.toLowerCase()
  if (t === 'github') return <span className="font-bold">GH</span>
  if (t === 'youtube') return <span className="font-bold text-red-500">YT</span>
  if (t === 'facebook') return <span className="font-bold text-blue-600">FB</span>
  if (t === 'x' || t === 'twitter') return <span className="font-bold">𝕏</span>
  if (t === 'linkedin') return <span className="font-bold text-blue-700">IN</span>
  if (t === 'discord') return <MessageSquare className="size-3.5" />
  return <Globe className="size-3.5 text-primary" />
}

export function ProfileHeroCard({
  user,
  isOwnProfile = false,
}: {
  user: ProfileUser
  isOwnProfile?: boolean
}) {
  const { t, i18n } = useTranslation('profile')
  const [editOpen, setEditOpen] = useState(false)
  const [avatarOpen, setAvatarOpen] = useState(false)
  const [verifyOpen, setVerifyOpen] = useState(false)

  const displayName = user.display_name || user.username
  const initials = (displayName || 'U').slice(0, 2).toUpperCase()

  const formattedDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString(i18n.language === 'en' ? 'en-US' : 'vi-VN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : t('hero.new_member')

  const isVerifiedStudent = Boolean(user.is_verified_student)
  const isEmailVerified = Boolean(user.email_verified)
  const isEdu = Boolean(
    user.is_edu_email ||
      (user.email && user.email.toLowerCase().endsWith('.edu.vn'))
  )

  const socialLinks: SocialLink[] = Array.isArray(user.social_links)
    ? user.social_links
    : []

  return (
    <>
      <Card className="relative overflow-hidden border-border/60 bg-gradient-to-br from-background via-muted/20 to-background shadow-xs">
        <div className="absolute top-0 right-0 h-40 w-80 bg-radial from-primary/10 via-amber-500/5 to-transparent blur-2xl pointer-events-none" />
        <CardContent className="p-4 sm:p-6 md:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:gap-5">
              {/* Avatar with Upload trigger */}
              <div className="relative group self-center sm:self-start">
                <Avatar className="size-20 sm:size-24 border-2 border-primary/30 shadow-md ring-4 ring-primary/10">
                  {user.avatar_url ? (
                    <AvatarImage
                      src={resolveMediaUrl(user.avatar_url)}
                      alt={displayName}
                      className="object-cover"
                    />
                  ) : null}
                  <AvatarFallback className="bg-gradient-to-tr from-primary via-orange-500 to-amber-500 text-2xl sm:text-3xl font-bold text-primary-foreground">
                    {initials}
                  </AvatarFallback>
                </Avatar>

                {isOwnProfile ? (
                  <>
                    {/* Desktop hover overlay */}
                    <button
                      type="button"
                      onClick={() => setAvatarOpen(true)}
                      title={t('hero.change_avatar')}
                      className="absolute inset-0 hidden sm:flex items-center justify-center rounded-full bg-black/50 text-white opacity-0 transition-opacity group-hover:opacity-100 cursor-pointer"
                      aria-label={t('hero.change_avatar')}
                    >
                      <Camera className="size-6" />
                    </button>
                    {/* Mobile touch camera badge */}
                    <button
                      type="button"
                      onClick={() => setAvatarOpen(true)}
                      title={t('hero.change_avatar')}
                      className="absolute -bottom-1 -right-1 flex sm:hidden size-7 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-md ring-2 ring-background active:scale-95 cursor-pointer z-10"
                      aria-label={t('hero.change_avatar')}
                    >
                      <Camera className="size-3.5" />
                    </button>
                  </>
                ) : null}

                {/* Role / Creator Badge Tag on Avatar */}
                {user.is_admin ? (
                  <span
                    title={t('hero.admin_badge_title')}
                    className="absolute -right-1 -top-1 sm:-bottom-1 sm:top-auto flex size-6 items-center justify-center rounded-full bg-amber-500 text-amber-950 shadow-xs ring-2 ring-background"
                  >
                    <Shield className="size-3.5 fill-current" />
                  </span>
                ) : user.role?.code === 'creator' ? (
                  <span
                    title={t('hero.creator_badge_title')}
                    className="absolute -right-1 -top-1 sm:-bottom-1 sm:top-auto flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xs ring-2 ring-background"
                  >
                    <Award className="size-3.5 fill-current" />
                  </span>
                ) : null}
              </div>

              {/* User Information */}
              <div className="space-y-2 text-center sm:text-left flex-1 min-w-0">
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2">
                  <h1 className="text-xl sm:text-2xl lg:text-3xl font-extrabold tracking-tight text-foreground truncate max-w-full">
                    {displayName}
                  </h1>
                  {user.display_name && user.display_name !== user.username ? (
                    <span className="text-xs sm:text-sm font-medium text-muted-foreground truncate">
                      @{user.username}
                    </span>
                  ) : null}

                  {user.is_admin ? (
                    <Badge className="bg-amber-500/15 text-amber-600 border-amber-500/30 dark:text-amber-400">
                      <Shield className="mr-1 size-3" />
                      {t('hero.role_admin')}
                    </Badge>
                  ) : user.role?.code === 'creator' ? (
                    <Badge variant="outline" className="bg-muted text-foreground border-border/80">
                      <Award className="mr-1 size-3" />
                      {t('hero.role_creator')}
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-muted-foreground">
                      <UserIcon className="mr-1 size-3" />
                      {user.role?.name || t('hero.role_student_fallback')}
                    </Badge>
                  )}

                  {isVerifiedStudent ? (
                    <Badge className="bg-blue-500/15 text-blue-700 border-blue-500/30 dark:text-blue-400 font-semibold shadow-xs">
                      <GraduationCap className="mr-1 size-3.5 text-blue-600 dark:text-blue-400" />
                      {t('hero.verified_student')}
                    </Badge>
                  ) : isOwnProfile && isEmailVerified ? (
                    <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-400 font-semibold">
                      <CheckCircle2 className="mr-1 size-3 text-emerald-600 dark:text-emerald-400" />
                      {t('hero.verified_email')}
                    </Badge>
                  ) : isOwnProfile ? (
                    <div className="inline-flex items-center gap-1.5">
                      <Badge
                        variant="outline"
                        className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs font-semibold"
                      >
                        <ShieldAlert className="mr-1 size-3 text-amber-600 dark:text-amber-400" />
                        {isEdu ? t('hero.unverified_student') : t('hero.unverified_email')}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setVerifyOpen(true)}
                        className="h-6 px-2 text-[11px] font-bold text-primary hover:bg-primary/10 hover:text-primary rounded-md cursor-pointer"
                      >
                        {t('hero.verify_now')}
                      </Button>
                    </div>
                  ) : null}
                </div>

                {/* Bio paragraph */}
                {user.bio ? (
                  <p className="text-sm text-muted-foreground leading-relaxed max-w-2xl">
                    {user.bio}
                  </p>
                ) : isOwnProfile ? (
                  <p className="text-xs text-muted-foreground/70 italic">
                    {t('hero.empty_bio')}
                  </p>
                ) : null}

                {/* Social Links row */}
                {socialLinks.length > 0 ? (
                  <div className="flex flex-wrap items-center justify-center sm:justify-start gap-2 pt-1">
                    {socialLinks.map((link, idx) => (
                      <a
                        key={idx}
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/80 px-2.5 py-1 text-xs font-medium text-foreground/80 hover:bg-muted hover:text-primary transition-colors"
                      >
                        <SocialIcon type={link.type} />
                        <span>{link.label || link.type}</span>
                        <ExternalLink className="size-3 text-muted-foreground" />
                      </a>
                    ))}
                  </div>
                ) : null}

                {/* Meta details */}
                <div className="flex flex-wrap items-center justify-center sm:justify-start gap-x-4 gap-y-1.5 text-xs text-muted-foreground pt-1">
                  {isOwnProfile && user.email ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Mail className="size-3.5" />
                      {user.email}
                    </span>
                  ) : null}
                  {isOwnProfile && user.timezone ? (
                    <span className="inline-flex items-center gap-1.5">
                      <Clock className="size-3.5" />
                      {user.timezone}
                    </span>
                  ) : null}
                  <span className="inline-flex items-center gap-1.5">
                    <Calendar className="size-3.5" />
                    {t('hero.joined_date', { date: formattedDate })}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions for Profile Owner */}
            {isOwnProfile ? (
              <div className="flex w-full sm:w-auto items-center justify-center sm:justify-end gap-2 self-stretch sm:self-start pt-2 sm:pt-0">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setEditOpen(true)}
                  className="w-full sm:w-auto gap-1.5 rounded-full px-5 py-2 text-xs font-semibold shadow-2xs hover:bg-muted/80 active:scale-98 cursor-pointer"
                >
                  <Edit3 className="size-3.5" />
                  {t('hero.edit_profile')}
                </Button>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {isOwnProfile ? (
        <>
          <ProfileEditDialog
            user={user}
            open={editOpen}
            onOpenChange={setEditOpen}
          />

          <AvatarUploadModal
            open={avatarOpen}
            onOpenChange={setAvatarOpen}
            currentAvatarUrl={resolveMediaUrl(user.avatar_url)}
          />

          <EmailVerificationDialog
            user={user}
            open={verifyOpen}
            onOpenChange={setVerifyOpen}
          />
        </>
      ) : null}
    </>
  )
}
