import { useEffect, useState } from 'react'
import {
  Eye,
  EyeOff,
  KeyRound,
  Link2,
  LoaderCircle,
  Plus,
  Settings2,
  Trash2,
} from 'lucide-react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Textarea } from '@/components/ui/textarea'
import { profileApi } from '../api/profileApi'
import { bootstrapQueryKey } from '@/shared/api/bootstrap'
import {
  type PasswordFieldErrors,
  mapApiErrorToFieldErrors,
  validateChangePasswordForm,
} from '../schemas'
import type { ProfileUser, SocialLink } from '../types/profile'

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

const SOCIAL_PLATFORMS = [
  { value: 'website', label: 'Website cá nhân' },
  { value: 'github', label: 'GitHub' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'x', label: 'X (Twitter)' },
  { value: 'linkedin', label: 'LinkedIn' },
  { value: 'discord', label: 'Discord' },
  { value: 'other', label: 'Khác' },
]

export function ProfileEditDialog({
  user,
  open,
  onOpenChange,
}: {
  user: ProfileUser
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'info' | 'links' | 'password'>('info')

  // Form states
  const [displayName, setDisplayName] = useState(user.display_name || user.username || '')
  const [bio, setBio] = useState(user.bio || '')
  const [email, setEmail] = useState(user.email || '')
  const [timezone, setTimezone] = useState(user.timezone || 'Asia/Ho_Chi_Minh')
  const [socialLinks, setSocialLinks] = useState<SocialLink[]>(
    Array.isArray(user.social_links) ? [...user.social_links] : []
  )

  // Password change states
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPw, setShowCurrentPw] = useState(false)
  const [showNewPw, setShowNewPw] = useState(false)
  const [showConfirmPw, setShowConfirmPw] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({})
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false)

  // Sync state whenever dialog opens
  useEffect(() => {
    if (open) {
      setDisplayName(user.display_name || user.username || '')
      setBio(user.bio || '')
      setEmail(user.email || '')
      setTimezone(user.timezone || 'Asia/Ho_Chi_Minh')
      setSocialLinks(Array.isArray(user.social_links) ? [...user.social_links] : [])
      resetPasswordState()
    }
  }, [open, user])

  const resetPasswordState = () => {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setShowCurrentPw(false)
    setShowNewPw(false)
    setShowConfirmPw(false)
    setFieldErrors({})
    setHasAttemptedSubmit(false)
  }

  const mutation = useMutation({
    mutationFn: (payload: {
      display_name?: string
      bio?: string
      email?: string
      social_links?: SocialLink[]
      timezone?: string
      current_password?: string
      new_password?: string
      confirm_password?: string
    }) => profileApi.updateProfile(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['public-profile'] })
      void queryClient.invalidateQueries({ queryKey: bootstrapQueryKey })
      toast.success(
        activeTab === 'password'
          ? 'Mật khẩu đã được thay đổi thành công.'
          : 'Đã cập nhật hồ sơ cá nhân thành công!'
      )
      resetPasswordState()
      onOpenChange(false)
    },
    onError: (err: unknown) => {
      const { fieldErrors: apiFieldErrors, unscopedMessage } =
        mapApiErrorToFieldErrors(err)

      if (Object.keys(apiFieldErrors).length > 0) {
        setFieldErrors((prev) => ({ ...prev, ...apiFieldErrors }))
      }

      if (unscopedMessage) {
        toast.error('Không thể cập nhật thông tin', {
          description: unscopedMessage,
        })
      }
    },
  })

  const handleSaveInfo = (e: React.FormEvent) => {
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
    mutation.mutate(payload)
  }

  const handleSaveLinks = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      social_links: socialLinks.filter((l) => Boolean(l.url.trim())),
    })
  }

  const handleAddSocialLink = () => {
    if (socialLinks.length >= 10) {
      toast.warning('Tối đa 10 liên kết mạng xã hội.')
      return
    }
    setSocialLinks((prev) => [
      ...prev,
      { type: 'website', url: '', label: '' },
    ])
  }

  const handleUpdateSocialLink = (
    index: number,
    field: keyof SocialLink,
    value: string
  ) => {
    setSocialLinks((prev) => {
      const copy = [...prev]
      copy[index] = { ...copy[index], [field]: value }
      return copy
    })
  }

  const handleRemoveSocialLink = (index: number) => {
    setSocialLinks((prev) => prev.filter((_, i) => i !== index))
  }

  const isPasswordFormValid = validateChangePasswordForm({
    current_password: currentPassword,
    new_password: newPassword,
    confirm_password: confirmPassword,
  }).success

  const handleSavePassword = (e: React.FormEvent) => {
    e.preventDefault()
    setHasAttemptedSubmit(true)

    const validation = validateChangePasswordForm({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })

    if (!validation.success) {
      setFieldErrors(validation.errors)
      return
    }

    setFieldErrors({})
    mutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })
  }

  const handleTabChange = (tab: 'info' | 'links' | 'password') => {
    setActiveTab(tab)
    if (tab !== 'password') {
      resetPasswordState()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[540px] max-h-[90vh] overflow-y-auto p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold">
            <Settings2 className="size-5 text-primary" />
            Chỉnh sửa hồ sơ cá nhân
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            Cập nhật tên hiển thị, bio giới thiệu, liên kết và cài đặt tài khoản của bạn.
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
            Thông tin & Bio
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
            Liên kết ({socialLinks.length})
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
            Đổi mật khẩu
          </button>
        </div>

        {/* Tab 1: Info & Bio */}
        {activeTab === 'info' ? (
          <form onSubmit={handleSaveInfo} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="profile-display-name" className="text-xs">
                Tên hiển thị (Display Name)
              </Label>
              <Input
                id="profile-display-name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Tên bạn muốn hiển thị"
                maxLength={80}
              />
              <p className="text-[11px] text-muted-foreground">
                Tên này sẽ hiển thị trên trang cá nhân và các bài đăng marketplace.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-email" className="text-xs">
                Địa chỉ Email
              </Label>
              <Input
                id="profile-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
              />
              <p className="text-[11px] text-muted-foreground">
                {user.is_verified_student ? (
                  <span className="text-blue-600 dark:text-blue-400 font-medium">
                    Email sinh viên ({user.email}) đã được kích hoạt ưu đãi.
                  </span>
                ) : user.email_verified ? (
                  <span>
                    Thay đổi địa chỉ email sẽ yêu cầu bạn xác thực lại email mới.
                  </span>
                ) : (
                  <span>
                    Email dùng để nhận thông báo và xác thực tài khoản.
                  </span>
                )}
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-bio" className="text-xs">
                Giới thiệu bản thân (Bio)
              </Label>
              <Textarea
                id="profile-bio"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="Chia sẻ đôi nét về bạn, mục tiêu học tiếng Nhật hoặc các bộ thẻ bạn tạo..."
                rows={3}
                maxLength={500}
              />
              <div className="flex justify-between text-[11px] text-muted-foreground">
                <span>Tối đa 500 ký tự</span>
                <span>{bio.length}/500</span>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-timezone" className="text-xs">
                Múi giờ học tập
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
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
                className="w-full sm:w-auto"
              >
                Hủy
              </Button>
              <Button type="submit" disabled={mutation.isPending} className="w-full sm:w-auto">
                {mutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    Đang lưu…
                  </>
                ) : (
                  'Lưu thông tin'
                )}
              </Button>
            </DialogFooter>
          </form>
        ) : null}

        {/* Tab 2: Social Links */}
        {activeTab === 'links' ? (
          <form onSubmit={handleSaveLinks} className="space-y-4 pt-2">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Thêm các liên kết website, kênh YouTube, trang GitHub hoặc trang cá nhân của bạn.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddSocialLink}
                className="h-8 gap-1 text-xs font-semibold self-start sm:self-auto shrink-0 cursor-pointer"
              >
                <Plus className="size-3.5" />
                Thêm link
              </Button>
            </div>

            {socialLinks.length === 0 ? (
              <div className="py-8 text-center rounded-xl border border-dashed border-border/80">
                <Link2 className="size-8 mx-auto text-muted-foreground/40 mb-2" />
                <p className="text-xs text-muted-foreground">
                  Chưa có liên kết nào. Nhấn 'Thêm link' để bổ sung liên kết mạng xã hội.
                </p>
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[300px] overflow-y-auto pr-1">
                {socialLinks.map((link, idx) => (
                  <div
                    key={idx}
                    className="flex flex-col sm:flex-row sm:items-center gap-2 rounded-lg border border-border/60 p-2.5 bg-muted/20"
                  >
                    <div className="flex items-center gap-2 w-full sm:w-auto">
                      <NativeSelect
                        value={link.type}
                        onChange={(e) =>
                          handleUpdateSocialLink(idx, 'type', e.target.value)
                        }
                        className="w-full sm:w-32 shrink-0 text-xs"
                      >
                        {SOCIAL_PLATFORMS.map((p) => (
                          <NativeSelectOption key={p.value} value={p.value}>
                            {p.label}
                          </NativeSelectOption>
                        ))}
                      </NativeSelect>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveSocialLink(idx)}
                        className="size-8 p-0 text-destructive hover:bg-destructive/10 shrink-0 sm:hidden cursor-pointer"
                        title="Xóa link"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>

                    <Input
                      value={link.url}
                      onChange={(e) =>
                        handleUpdateSocialLink(idx, 'url', e.target.value)
                      }
                      placeholder="https://..."
                      className="text-xs flex-1"
                    />

                    <Input
                      value={link.label || ''}
                      onChange={(e) =>
                        handleUpdateSocialLink(idx, 'label', e.target.value)
                      }
                      placeholder="Nhãn (tùy chọn)"
                      className="w-full sm:w-28 shrink-0 text-xs"
                    />

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRemoveSocialLink(idx)}
                      className="size-8 p-0 text-destructive hover:bg-destructive/10 shrink-0 hidden sm:flex cursor-pointer"
                      title="Xóa link"
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}

            <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
                className="w-full sm:w-auto"
              >
                Hủy
              </Button>
              <Button type="submit" disabled={mutation.isPending} className="w-full sm:w-auto">
                {mutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    Đang lưu…
                  </>
                ) : (
                  'Lưu liên kết'
                )}
              </Button>
            </DialogFooter>
          </form>
        ) : null}

        {/* Tab 3: Password Change */}
        {activeTab === 'password' ? (
          <form noValidate onSubmit={handleSavePassword} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="profile-cur-pw" className="text-xs">
                Mật khẩu hiện tại <span className="text-destructive">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="profile-cur-pw"
                  type={showCurrentPw ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => {
                    setCurrentPassword(e.target.value)
                    if (fieldErrors.current_password) {
                      setFieldErrors((prev) => ({ ...prev, current_password: undefined }))
                    }
                  }}
                  placeholder="Nhập mật khẩu hiện tại để xác thực"
                  aria-invalid={Boolean(fieldErrors.current_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPw(!showCurrentPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
                  tabIndex={-1}
                  aria-label={showCurrentPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showCurrentPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldErrors.current_password ? (
                <p className="text-[11px] font-medium text-destructive">
                  {fieldErrors.current_password}
                </p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-new-pw" className="text-xs">
                Mật khẩu mới <span className="text-destructive">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="profile-new-pw"
                  type={showNewPw ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => {
                    setNewPassword(e.target.value)
                    if (fieldErrors.new_password) {
                      setFieldErrors((prev) => ({ ...prev, new_password: undefined }))
                    }
                  }}
                  placeholder="Ít nhất 8 ký tự"
                  aria-invalid={Boolean(fieldErrors.new_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNewPw(!showNewPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
                  tabIndex={-1}
                  aria-label={showNewPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showNewPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldErrors.new_password ? (
                <p className="text-[11px] font-medium text-destructive">
                  {fieldErrors.new_password}
                </p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-conf-pw" className="text-xs">
                Xác nhận mật khẩu mới <span className="text-destructive">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="profile-conf-pw"
                  type={showConfirmPw ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value)
                    if (fieldErrors.confirm_password) {
                      setFieldErrors((prev) => ({ ...prev, confirm_password: undefined }))
                    }
                  }}
                  placeholder="Nhập lại mật khẩu mới"
                  aria-invalid={Boolean(fieldErrors.confirm_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPw(!showConfirmPw)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground p-1 rounded-md cursor-pointer transition-colors"
                  tabIndex={-1}
                  aria-label={showConfirmPw ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showConfirmPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
              {fieldErrors.confirm_password ? (
                <p className="text-[11px] font-medium text-destructive">
                  {fieldErrors.confirm_password}
                </p>
              ) : null}
            </div>

            <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
                className="w-full sm:w-auto"
              >
                Hủy
              </Button>
              <Button
                type="submit"
                disabled={
                  mutation.isPending || (hasAttemptedSubmit && !isPasswordFormValid)
                }
                className="w-full sm:w-auto bg-gradient-to-r from-primary to-orange-500 font-semibold text-primary-foreground hover:opacity-95"
              >
                {mutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    Đang đổi mật khẩu…
                  </>
                ) : (
                  <>
                    <KeyRound className="mr-1.5 size-4" />
                    Đổi mật khẩu
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
