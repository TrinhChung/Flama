import { useEffect, useState } from 'react'
import { Eye, EyeOff, KeyRound, LoaderCircle, Settings2 } from 'lucide-react'
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
import { profileApi } from '../api/profileApi'
import {
  type PasswordFieldErrors,
  mapApiErrorToFieldErrors,
  validateChangePasswordForm,
} from '../schemas'
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
  const [activeTab, setActiveTab] = useState<'info' | 'password'>('info')
  const [timezone, setTimezone] = useState(user.timezone || 'Asia/Ho_Chi_Minh')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [fieldErrors, setFieldErrors] = useState<PasswordFieldErrors>({})
  const [hasAttemptedSubmit, setHasAttemptedSubmit] = useState(false)

  const resetPasswordState = () => {
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setShowCurrentPassword(false)
    setShowNewPassword(false)
    setShowConfirmPassword(false)
    setFieldErrors({})
    setHasAttemptedSubmit(false)
  }

  // Clear credentials and errors whenever the dialog closes/reopens
  useEffect(() => {
    if (!open) {
      resetPasswordState()
    }
  }, [open])

  const mutation = useMutation({
    mutationFn: (payload: {
      timezone?: string
      current_password?: string
      new_password?: string
      confirm_password?: string
    }) => profileApi.updateProfile(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['bootstrap'] })
      toast.success(
        activeTab === 'password'
          ? 'Mật khẩu đã được thay đổi thành công.'
          : 'Đã cập nhật thông tin cá nhân thành công!',
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
    mutation.mutate({ timezone })
  }

  const isFormValid = validateChangePasswordForm({
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

  const handleTabChange = (tab: 'info' | 'password') => {
    setActiveTab(tab)
    if (tab === 'info') {
      resetPasswordState()
    }
  }

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      resetPasswordState()
    }
    onOpenChange(nextOpen)
  }

  const handleCurrentPasswordChange = (val: string) => {
    setCurrentPassword(val)
    if (fieldErrors.current_password) {
      setFieldErrors((prev) => ({ ...prev, current_password: undefined }))
    }
  }

  const handleNewPasswordChange = (val: string) => {
    setNewPassword(val)
    if (fieldErrors.new_password) {
      setFieldErrors((prev) => ({ ...prev, new_password: undefined }))
    }
  }

  const handleConfirmPasswordChange = (val: string) => {
    setConfirmPassword(val)
    if (fieldErrors.confirm_password) {
      setFieldErrors((prev) => ({ ...prev, confirm_password: undefined }))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[480px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings2 className="size-5 text-primary" />
            Chỉnh sửa thông tin cá nhân
          </DialogTitle>
          <DialogDescription>
            Cập nhật múi giờ hiển thị hoặc đổi mật khẩu đăng nhập của bạn.
          </DialogDescription>
        </DialogHeader>

        <div className="flex border-b border-border/60">
          <button
            type="button"
            onClick={() => handleTabChange('info')}
            className={`border-b-2 px-4 py-2 text-xs font-semibold transition ${
              activeTab === 'info'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            Thông tin & Múi giờ
          </button>
          <button
            type="button"
            onClick={() => handleTabChange('password')}
            className={`border-b-2 px-4 py-2 text-xs font-semibold transition ${
              activeTab === 'password'
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            Đổi mật khẩu
          </button>
        </div>

        {activeTab === 'info' ? (
          <form onSubmit={handleSaveInfo} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="profile-username" className="text-xs">
                Tên người dùng
              </Label>
              <Input
                id="profile-username"
                value={user.username}
                disabled
                className="bg-muted/40 text-muted-foreground"
              />
              <p className="text-[11px] text-muted-foreground">
                Tên đăng nhập không thể thay đổi sau khi đăng ký.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-email" className="text-xs">
                Địa chỉ Email
              </Label>
              <Input
                id="profile-email"
                value={user.email}
                disabled
                className="bg-muted/40 text-muted-foreground"
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-timezone" className="text-xs">
                Múi giờ hoạt động
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

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={mutation.isPending}
              >
                Hủy
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    Đang lưu…
                  </>
                ) : (
                  'Lưu thay đổi'
                )}
              </Button>
            </DialogFooter>
          </form>
        ) : user.has_password === false ? (
          <div className="space-y-4 pt-2">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-900 dark:text-amber-200">
              <div className="flex items-start gap-2.5">
                <KeyRound className="mt-0.5 size-4 text-amber-600 shrink-0 dark:text-amber-400" />
                <div className="space-y-1">
                  <p className="font-semibold">Tài khoản đăng nhập qua dịch vụ liên kết</p>
                  <p className="text-muted-foreground text-xs leading-relaxed">
                    Tài khoản này được đăng ký qua Google hoặc OAuth và chưa thiết lập mật khẩu trực tiếp. Để tạo mật khẩu mới cho tài khoản, bạn có thể sử dụng chức năng <span className="font-medium text-foreground">Quên mật khẩu</span> khi đăng xuất.
                  </p>
                </div>
              </div>
            </div>
            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
                Đóng
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <form noValidate onSubmit={handleSavePassword} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="profile-cur-pw" className="text-xs">
                Mật khẩu hiện tại <span className="text-destructive">*</span>
              </Label>
              <div className="relative">
                <Input
                  id="profile-cur-pw"
                  type={showCurrentPassword ? 'text' : 'password'}
                  value={currentPassword}
                  onChange={(e) => handleCurrentPasswordChange(e.target.value)}
                  placeholder="Nhập mật khẩu hiện tại để xác thực"
                  aria-invalid={Boolean(fieldErrors.current_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword((prev) => !prev)}
                  className="absolute right-0 top-0 flex h-full items-center px-3 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showCurrentPassword ? 'Ẩn mật khẩu hiện tại' : 'Hiện mật khẩu hiện tại'}
                >
                  {showCurrentPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
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
                  type={showNewPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => handleNewPasswordChange(e.target.value)}
                  placeholder="Ít nhất 8 ký tự"
                  aria-invalid={Boolean(fieldErrors.new_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword((prev) => !prev)}
                  className="absolute right-0 top-0 flex h-full items-center px-3 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showNewPassword ? 'Ẩn mật khẩu mới' : 'Hiện mật khẩu mới'}
                >
                  {showNewPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
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
                  type={showConfirmPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => handleConfirmPasswordChange(e.target.value)}
                  placeholder="Nhập lại mật khẩu mới"
                  aria-invalid={Boolean(fieldErrors.confirm_password)}
                  className="pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  className="absolute right-0 top-0 flex h-full items-center px-3 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showConfirmPassword ? 'Ẩn xác nhận mật khẩu' : 'Hiện xác nhận mật khẩu'}
                >
                  {showConfirmPassword ? (
                    <EyeOff className="size-4" />
                  ) : (
                    <Eye className="size-4" />
                  )}
                </button>
              </div>
              {fieldErrors.confirm_password ? (
                <p className="text-[11px] font-medium text-destructive">
                  {fieldErrors.confirm_password}
                </p>
              ) : null}
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleOpenChange(false)}
                disabled={mutation.isPending}
              >
                Hủy
              </Button>
              <Button
                type="submit"
                disabled={
                  mutation.isPending || (hasAttemptedSubmit && !isFormValid)
                }
                className="bg-gradient-to-r from-primary to-orange-500 font-semibold text-primary-foreground hover:opacity-95"
              >
                {mutation.isPending ? (
                  <>
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                    Đang đổi mật khẩu…
                  </>
                ) : (
                  <>
                    <KeyRound className="mr-1.5 size-4" />
                    Cập nhật mật khẩu
                  </>
                )}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  )
}

