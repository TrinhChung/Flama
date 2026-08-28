import { useState } from 'react'
import {
  Calendar,
  CheckCircle2,
  Clock,
  Edit3,
  GraduationCap,
  Mail,
  Shield,
  ShieldAlert,
  Sparkles,
  User,
} from 'lucide-react'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { EmailVerificationDialog } from './EmailVerificationDialog'
import { ProfileEditDialog } from './ProfileEditDialog'
import type { ProfileUser } from '../types/profile'

export function ProfileHeroCard({ user }: { user: ProfileUser }) {
  const [editOpen, setEditOpen] = useState(false)
  const [verifyOpen, setVerifyOpen] = useState(false)
  const initials = (user.username || 'U').slice(0, 2).toUpperCase()

  const formattedDate = user.created_at
    ? new Date(user.created_at).toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : 'Thành viên mới'

  const isVerifiedStudent = Boolean(user.is_verified_student)
  const isEmailVerified = Boolean(user.email_verified)
  const isEdu = Boolean(
    user.is_edu_email ||
      (user.email && user.email.toLowerCase().endsWith('.edu.vn'))
  )

  return (
    <>
      <Card className="relative overflow-hidden border-border/60 bg-gradient-to-br from-background via-muted/20 to-background shadow-xs">
        <div className="absolute top-0 right-0 h-32 w-64 bg-radial from-primary/10 via-amber-500/5 to-transparent blur-2xl" />
        <CardContent className="p-6 md:p-8">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-5">
              <div className="relative">
                <Avatar className="size-20 border-2 border-primary/30 shadow-md ring-4 ring-primary/10">
                  <AvatarFallback className="bg-gradient-to-tr from-primary via-orange-500 to-amber-500 text-2xl font-bold text-primary-foreground">
                    {initials}
                  </AvatarFallback>
                </Avatar>
                {user.is_admin ? (
                  <span
                    title="Quản trị viên hệ thống"
                    className="absolute -right-1 -bottom-1 flex size-6 items-center justify-center rounded-full bg-amber-500 text-amber-950 shadow-xs"
                  >
                    <Shield className="size-3.5 fill-current" />
                  </span>
                ) : user.role?.code === 'creator' ? (
                  <span
                    title="Nhà sáng tạo nội dung"
                    className="absolute -right-1 -bottom-1 flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-xs"
                  >
                    <Sparkles className="size-3.5 fill-current" />
                  </span>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center gap-2.5">
                  <h1 className="text-2xl font-bold tracking-tight text-foreground">
                    {user.username}
                  </h1>
                  {user.is_admin ? (
                    <Badge className="bg-amber-500/15 text-amber-600 border-amber-500/30 dark:text-amber-400">
                      <Shield className="mr-1 size-3" />
                      Admin
                    </Badge>
                  ) : user.role?.code === 'creator' ? (
                    <Badge className="bg-primary/15 text-primary border-primary/30">
                      <Sparkles className="mr-1 size-3" />
                      Nhà sáng tạo
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-muted-foreground">
                      <User className="mr-1 size-3" />
                      {user.role?.name || 'Học viên'}
                    </Badge>
                  )}

                  {/* Student / Email Verification Badges */}
                  {isVerifiedStudent ? (
                    <Badge className="bg-emerald-500/15 text-emerald-700 border-emerald-500/30 dark:text-emerald-400 font-semibold shadow-xs">
                      <GraduationCap className="mr-1 size-3.5 text-emerald-600 dark:text-emerald-400" />
                      Sinh viên đã xác thực
                    </Badge>
                  ) : isEmailVerified ? (
                    <Badge className="bg-blue-500/15 text-blue-700 border-blue-500/30 dark:text-blue-400 font-semibold">
                      <CheckCircle2 className="mr-1 size-3 text-blue-600 dark:text-blue-400" />
                      Email đã xác thực
                    </Badge>
                  ) : (
                    <div className="inline-flex items-center gap-1.5">
                      <Badge
                        variant="outline"
                        className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs font-semibold"
                      >
                        <ShieldAlert className="mr-1 size-3 text-amber-600 dark:text-amber-400" />
                        {isEdu ? 'Chưa xác thực SV' : 'Chưa xác thực email'}
                      </Badge>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setVerifyOpen(true)}
                        className="h-6 px-2 text-[11px] font-bold text-primary hover:bg-primary/10 hover:text-primary rounded-md cursor-pointer"
                      >
                        Xác thực ngay
                      </Button>
                    </div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Mail className="size-3.5" />
                    {user.email}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="size-3.5" />
                    {user.timezone || 'UTC'}
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <Calendar className="size-3.5" />
                    Gia nhập {formattedDate}
                  </span>
                </div>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setEditOpen(true)}
              className="self-start sm:self-center gap-1.5 rounded-full px-4 text-xs font-semibold"
            >
              <Edit3 className="size-3.5" />
              Chỉnh sửa hồ sơ
            </Button>
          </div>
        </CardContent>
      </Card>

      <ProfileEditDialog
        user={user}
        open={editOpen}
        onOpenChange={setEditOpen}
      />

      <EmailVerificationDialog
        user={user}
        open={verifyOpen}
        onOpenChange={setVerifyOpen}
      />
    </>
  )
}

