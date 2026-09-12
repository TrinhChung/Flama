import { useState } from 'react'
import { ExternalLink, Heart, QrCode, Save, ShieldCheck } from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader, StatCard } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type SupportConfig = {
  title?: string
  description?: string
  account_name?: string
  account_number?: string
  thank_you_message?: string
  qr_image_storage_path?: string
  updated_at?: string
}

type SupportConfigResponse = {
  item: SupportConfig | null
}

export function AdminSupportConfigPage() {
  const queryClient = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [removeQr, setRemoveQr] = useState(false)

  const queryKey = ['admin', 'support-config'] as const
  const query = useQuery({
    queryKey,
    queryFn: () => appApi.get<SupportConfigResponse>('/admin/support-donation'),
  })

  const [formState, setFormState] = useState<SupportConfig>({})
  const [isFormInitialized, setIsFormInitialized] = useState(false)

  if (query.data && !isFormInitialized) {
    const item = query.data.item || {}
    setFormState({
      title: item.title || 'Ủng hộ duy trì hệ thống Flama',
      description: item.description || 'Hệ thống được phát triển phi lợi nhuận. Mọi sự đóng góp của bạn đều giúp hệ thống duy trì máy chủ.',
      account_name: item.account_name || '',
      account_number: item.account_number || '',
      thank_you_message: item.thank_you_message || 'Cảm ơn sự đóng góp quý báu của bạn dành cho dự án!',
      qr_image_storage_path: item.qr_image_storage_path || '',
      updated_at: item.updated_at,
    })
    setIsFormInitialized(true)
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData()
      formData.append('title', formState.title || '')
      formData.append('description', formState.description || '')
      formData.append('account_name', formState.account_name || '')
      formData.append('account_number', formState.account_number || '')
      formData.append('thank_you_message', formState.thank_you_message || '')
      if (removeQr) {
        formData.append('remove_qr_image', '1')
      }
      if (selectedFile) {
        formData.append('qr_image', selectedFile)
      }

      return appApi.mutateFormData<{ item: SupportConfig }>('/admin/support-donation', 'PUT', formData)
    },
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey })
      if (data.item) {
        setFormState(data.item)
      }
      setSelectedFile(null)
      setRemoveQr(false)
      toast.success('Đã lưu thông tin cấu hình Ủng hộ / Tài trợ thành công.')
    },
    onError: (error: Error) => toast.error(error.message),
  })

  if (query.isPending) return <PageLoading label="Đang tải cấu hình Ủng hộ / Tài trợ…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const config = query.data.item

  return (
    <Page>
      <div className="space-y-3">
        <Badge variant="outline" className="gap-1 font-bold border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Cấu hình Ủng hộ / Tài trợ"
          description="Quản lý thông tin tài khoản quyên góp và ảnh mã QR hiển thị ở trang public."
          actions={
            <Button variant="outline" asChild className="gap-1.5">
              <Link to="/support" target="_blank">
                <ExternalLink className="size-4" /> Xem trang public
              </Link>
            </Button>
          }
        />
      </div>

      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Trạng thái cấu hình"
          value={config ? 'Đã cấu hình' : 'Chưa cấu hình'}
          hint="Cấu hình trang quyên góp"
          tone={config ? 'success' : 'warning'}
        />
        <StatCard
          label="Ảnh mã QR"
          value={config?.qr_image_storage_path ? 'Đã có ảnh' : 'Chưa có ảnh'}
          hint="Ảnh QR ngân hàng"
          tone={config?.qr_image_storage_path ? 'primary' : 'default'}
        />
        <StatCard
          label="Cập nhật gần nhất"
          value={config?.updated_at ? new Date(config.updated_at).toLocaleDateString('vi-VN') : 'Chưa có'}
          hint="Thời gian cập nhật"
          tone="default"
        />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          saveMutation.mutate()
        }}
      >
        <Card className="shadow-xs">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Heart className="size-5 text-rose-500" /> Thông tin trang Ủng hộ
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="md:col-span-2 space-y-2">
                <Label htmlFor="support-title">Tiêu đề trang</Label>
                <Input
                  id="support-title"
                  value={formState.title || ''}
                  onChange={(e) => setFormState((prev) => ({ ...prev, title: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="qr-file">Tải lên / Thay ảnh QR mới (tối đa 2MB)</Label>
                <Input
                  id="qr-file"
                  type="file"
                  accept="image/*"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file && file.size > 2 * 1024 * 1024) {
                      toast.error('Dung lượng ảnh QR vượt quá 2MB. Vui lòng chọn ảnh nhỏ hơn.')
                      e.target.value = ''
                      setSelectedFile(null)
                      return
                    }
                    setSelectedFile(file || null)
                  }}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="support-desc">Nội dung mô tả / Lời kêu gọi</Label>
              <Textarea
                id="support-desc"
                rows={4}
                value={formState.description || ''}
                onChange={(e) => setFormState((prev) => ({ ...prev, description: e.target.value }))}
                required
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="acc-name">Tên chủ tài khoản</Label>
                <Input
                  id="acc-name"
                  placeholder="Ví dụ: NGUYEN VAN A"
                  value={formState.account_name || ''}
                  onChange={(e) => setFormState((prev) => ({ ...prev, account_name: e.target.value }))}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="acc-number">Số tài khoản ngân hàng</Label>
                <Input
                  id="acc-number"
                  placeholder="Ví dụ: 0123456789"
                  value={formState.account_number || ''}
                  onChange={(e) => setFormState((prev) => ({ ...prev, account_number: e.target.value }))}
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="thank-msg">Lời cảm ơn người quyên góp</Label>
              <Textarea
                id="thank-msg"
                rows={3}
                value={formState.thank_you_message || ''}
                onChange={(e) => setFormState((prev) => ({ ...prev, thank_you_message: e.target.value }))}
                required
              />
            </div>

            {/* Current QR Preview */}
            {config?.qr_image_storage_path && (
              <div className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 font-semibold text-sm">
                    <QrCode className="size-4 text-primary" /> Ảnh QR hiện tại
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id="remove-qr"
                      checked={removeQr}
                      onCheckedChange={(c) => setRemoveQr(Boolean(c))}
                    />
                    <Label htmlFor="remove-qr" className="text-xs text-rose-600 font-semibold cursor-pointer">
                      Xóa ảnh QR hiện tại khi lưu
                    </Label>
                  </div>
                </div>
                <div className="h-44 w-44 rounded-md border p-2 bg-white flex items-center justify-center">
                  <img
                    src="/support-donation/qr"
                    alt="QR hiện tại"
                    className="max-h-full max-w-full object-contain"
                  />
                </div>
              </div>
            )}

            <div className="pt-2">
              <Button type="submit" className="gap-2" disabled={saveMutation.isPending}>
                <Save className="size-4" /> Lưu cấu hình Ủng hộ
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </Page>
  )
}
