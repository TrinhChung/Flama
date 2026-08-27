import { useState } from 'react'
import { KeyRound, LoaderCircle, Settings2 } from 'lucide-react'
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
      toast.success('Đã cập nhật thông tin cá nhân thành công!')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      onOpenChange(false)
    },
    onError: (err: any) => {
      toast.error('Không thể cập nhật thông tin', {
        description: err?.message || 'Vui lòng kiểm tra lại dữ liệu nhập vào.',
      })
    },
  })

  const handleSaveInfo = (e: React.FormEvent) => {
    e.preventDefault()
    mutation.mutate({ timezone })
  }

  const handleSavePassword = (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentPassword) {
      toast.error('Vui lòng nhập mật khẩu hiện tại.')
      return
    }
    if (newPassword.length < 6) {
      toast.error('Mật khẩu mới phải có ít nhất 6 ký tự.')
      return
    }
    if (newPassword !== confirmPassword) {
      toast.error('Xác nhận mật khẩu mới không khớp.')
      return
    }
    mutation.mutate({
      current_password: currentPassword,
      new_password: newPassword,
      confirm_password: confirmPassword,
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
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
            onClick={() => setActiveTab('info')}
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
            onClick={() => setActiveTab('password')}
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
                onClick={() => onOpenChange(false)}
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
        ) : (
          <form onSubmit={handleSavePassword} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <Label htmlFor="profile-cur-pw" className="text-xs">
                Mật khẩu hiện tại <span className="text-destructive">*</span>
              </Label>
              <Input
                id="profile-cur-pw"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Nhập mật khẩu hiện tại để xác thực"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-new-pw" className="text-xs">
                Mật khẩu mới <span className="text-destructive">*</span>
              </Label>
              <Input
                id="profile-new-pw"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Ít nhất 6 ký tự"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="profile-conf-pw" className="text-xs">
                Xác nhận mật khẩu mới <span className="text-destructive">*</span>
              </Label>
              <Input
                id="profile-conf-pw"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Nhập lại mật khẩu mới"
                required
              />
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                Hủy
              </Button>
              <Button
                type="submit"
                disabled={mutation.isPending}
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
