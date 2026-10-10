import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Settings2 } from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { profileApi } from '../api/profileApi'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import {
  type PasswordFieldErrors,
  mapApiErrorToFieldErrors,
} from '../schemas'
import type { ProfileUser } from '../types/profile'
import { ProfileEditInfoTab } from './ProfileEditInfoTab'
import { ProfileEditSocialLinksTab } from './ProfileEditSocialLinksTab'
import { ProfileEditPasswordTab } from './ProfileEditPasswordTab'

export function ProfileEditDialog({
  user,
  open,
  onOpenChange,
}: {
  user: ProfileUser
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { t } = useTranslation('profile')
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'info' | 'links' | 'password'>('info')
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({})

  const socialLinksCount = Array.isArray(user.social_links) ? user.social_links.length : 0

  useEffect(() => {
    if (open) {
      setActiveTab('info')
      setFieldErrors({})
    }
  }, [open])

  const mutation = useMutation({
    mutationFn: (payload: {
      display_name?: string
      bio?: string
      email?: string
      social_links?: any[]
      timezone?: string
      current_password?: string
      new_password?: string
      confirm_password?: string
    }) => profileApi.updateProfile(payload),
    onSuccess: (_response, variables) => {
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['public-profile'] })
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      if (variables.timezone && variables.timezone !== user.timezone) {
        void queryClient.invalidateQueries({ queryKey: ['stats'] })
        void queryClient.invalidateQueries({ queryKey: ['stats-overview'] })
        void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
        void queryClient.invalidateQueries({ queryKey: ['frontend', 'dashboard'] })
        void queryClient.invalidateQueries({ queryKey: ['frontend', 'statistics'] })
      }
      toast.success(
        activeTab === 'password'
          ? t('edit.toast.password_success')
          : t('edit.toast.profile_success')
      )
      setFieldErrors({})
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      const { fieldErrors: apiFieldErrors, unscopedMessage } =
        mapApiErrorToFieldErrors(err, t)

      if (Object.keys(apiFieldErrors).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...apiFieldErrors }))
      }

      if (unscopedMessage) {
        toast.error(t('edit.toast.update_error_title'), {
          description: unscopedMessage,
        })
      }
    },
  })

  const handleTabChange = (tab: 'info' | 'links' | 'password') => {
    setActiveTab(tab)
    if (tab !== 'password') {
      setFieldErrors({})
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px] max-h-[90vh] overflow-y-auto p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold">
            <Settings2 className="size-5 text-primary" />
            {t('edit.dialog_title')}
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            {t('edit.dialog_description')}
          </DialogDescription>
        </DialogHeader>

        {/* Tab navigation */}
        <div className="flex border-b border-border/60 overflow-x-auto scrollbar-none whitespace-nowrap -mx-4 px-4 sm:mx-0 sm:px-0">
          <button
            type="button"
            onClick={() => handleTabChange('info')}
            className={`shrink-0 border-b-2 px-4 py-2 text-xs font-semibold transition cursor-pointer ${
              activeTab === 'info'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t('edit.tabs.info')}
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('links')}
            className={`shrink-0 border-b-2 px-4 py-2 text-xs font-semibold transition cursor-pointer ${
              activeTab === 'links'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t('edit.tabs.links', { count: socialLinksCount })}
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('password')}
            className={`shrink-0 border-b-2 px-4 py-2 text-xs font-semibold transition cursor-pointer ${
              activeTab === 'password'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t('edit.tabs.password')}
          </button>
        </div>

        {/* Tab 1: Info & Bio */}
        {activeTab === 'info' ? (
          <ProfileEditInfoTab
            user={user}
            isPending={mutation.isPending}
            onCancel={() => onOpenChange(false)}
            onSave={(payload) => mutation.mutate(payload)}
          />
        ) : null}

        {/* Tab 2: Social Links */}
        {activeTab === 'links' ? (
          <ProfileEditSocialLinksTab
            initialLinks={Array.isArray(user.social_links) ? [...user.social_links] : []}
            isPending={mutation.isPending}
            onCancel={() => onOpenChange(false)}
            onSave={(links) => mutation.mutate({ social_links: links })}
          />
        ) : null}

        {/* Tab 3: Password Change */}
        {activeTab === 'password' ? (
          <ProfileEditPasswordTab
            isPending={mutation.isPending}
            fieldErrors={fieldErrors}
            setFieldErrors={setFieldErrors}
            onCancel={() => onOpenChange(false)}
            onSave={(passwords) => mutation.mutate(passwords)}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
