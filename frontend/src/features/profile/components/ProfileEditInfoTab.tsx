import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import type { ProfileUser } from '../types/profile'

const COMMON_TIMEZONES = [
  'Asia/Ho_Chi_Minh',
  'Asia/Tokyo',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Seoul',
  'UTC',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Paris',
]

export interface ProfileEditInfoTabProps {
  user: ProfileUser
  isPending: boolean
  onCancel: () => void
  onSave: (payload: {
    display_name?: string
    bio?: string
    email?: string
    timezone?: string
  }) => void
}

export function ProfileEditInfoTab({
  user,
  isPending,
  onCancel,
  onSave,
}: ProfileEditInfoTabProps) {
  const { t } = useTranslation('profile')

  const [displayName, setDisplayName] = useState(user.display_name || user.username || '')
  const [bio, setBio] = useState(user.bio || '')
  const [email, setEmail] = useState(user.email || '')
  const [timezone, setTimezone] = useState(user.timezone || 'Asia/Ho_Chi_Minh')

  useEffect(() => {
    setDisplayName(user.display_name || user.username || '')
    setBio(user.bio || '')
    setEmail(user.email || '')
    setTimezone(user.timezone || 'Asia/Ho_Chi_Minh')
  }, [user])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const payload: {
      display_name?: string
      bio?: string
      email?: string
      timezone?: string
    } = {
      display_name: displayName.trim(),
      bio: bio.trim(),
      timezone,
    }
    if (email.trim() && email.trim().toLowerCase() !== (user.email || '').toLowerCase()) {
      payload.email = email.trim().toLowerCase()
    }
    onSave(payload)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 pt-2">
      <div className="space-y-1.5">
        <Label htmlFor="profile-display-name" className="text-xs">
          {t('edit.info.display_name_label')}
        </Label>
        <Input
          id="profile-display-name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder={t('edit.info.display_name_placeholder')}
          maxLength={80}
        />
        <p className="text-[11px] text-muted-foreground">
          {t('edit.info.display_name_help')}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="profile-email" className="text-xs">
          {t('edit.info.email_label')}
        </Label>
        <Input
          id="profile-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder={t('edit.info.email_placeholder')}
        />
        <p className="text-[11px] text-muted-foreground">
          {user.is_verified_student ? (
            <span className="text-blue-600 dark:text-blue-400 font-medium">
              {t('edit.info.email_student_active', { email: user.email })}
            </span>
          ) : user.email_verified ? (
            <span>
              {t('edit.info.email_reverify_notice')}
            </span>
          ) : (
            <span>
              {t('edit.info.email_general_notice')}
            </span>
          )}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="profile-bio" className="text-xs">
          {t('edit.info.bio_label')}
        </Label>
        <Textarea
          id="profile-bio"
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          placeholder={t('edit.info.bio_placeholder')}
          rows={3}
          maxLength={500}
        />
        <div className="flex justify-between text-[11px] text-muted-foreground">
          <span>{t('edit.info.bio_max_chars')}</span>
          <span>{bio.length}/500</span>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="profile-timezone" className="text-xs">
          {t('edit.info.timezone_label')}
        </Label>
        <NativeSelect
          id="profile-timezone"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
        >
          {COMMON_TIMEZONES.map((tz) => (
            <NativeSelectOption key={tz} value={tz}>
              {tz}
            </NativeSelectOption>
          ))}
        </NativeSelect>
      </div>

      <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
        <Button
          type="button"
          variant="outline"
          onClick={onCancel}
          disabled={isPending}
          className="w-full sm:w-auto"
        >
          {t('edit.btn_cancel')}
        </Button>
        <Button type="submit" disabled={isPending} className="w-full sm:w-auto">
          {isPending ? (
            <>
              <LoaderCircle className="mr-2 size-4 animate-spin" />
              {t('edit.btn_saving')}
            </>
          ) : (
            t('edit.info.btn_save')
          )}
        </Button>
      </DialogFooter>
    </form>
  )
}
