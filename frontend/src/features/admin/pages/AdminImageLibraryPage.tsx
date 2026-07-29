import { useEffect, useState } from 'react'
import {
  Eye,
  Image as ImageIcon,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Upload,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'

type ImageAsset = {
  id: string
  asset_id?: string
  name: string
  description: string | null
  mime_type?: string
  status: 'enabled' | 'disabled' | string
  file_exists?: boolean
  url?: string
  storage_path?: string
  created_at?: string
}

type ImageLibraryResponse = {
  items: ImageAsset[]
  total: number
  page: number
  per_page: number
  pages: number
}

export function AdminImageLibraryPage() {
  const queryClient = useQueryClient()
  const [searchText, setSearchText] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [perPage] = useState(24)

  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingAsset, setEditingAsset] = useState<ImageAsset | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [isEnabled, setIsEnabled] = useState(true)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewModalUrl, setPreviewModalUrl] = useState<string | null>(null)

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSearch(searchText.trim())
      setPage(1)
    }, 250)
    return () => window.clearTimeout(timer)
  }, [searchText])

  const queryKey = ['admin', 'image-library', debouncedSearch, status, page, perPage] as const
  const query = useQuery({
    queryKey,
    queryFn: () =>
      appApi.get<ImageLibraryResponse>('/admin/image-library', {
        q: debouncedSearch,
        status,
        page,
        per_page: perPage,
      }),
  })

  const saveMutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData()
      formData.append('name', name)
      formData.append('description', description)
      formData.append('status', isEnabled ? 'enabled' : 'disabled')
      if (selectedFile) {
        formData.append('image', selectedFile)
      }

      if (editingAsset) {
        return appApi.mutateFormData(`/admin/image-library/${editingAsset.id || editingAsset.asset_id}`, 'PATCH', formData)
      }
      return appApi.mutateFormData('/admin/image-library', 'POST', formData)
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'image-library'] })
      toast.success(editingAsset ? 'Đã cập nhật ảnh.' : 'Đã tải ảnh mới lên.')
      closeModal()
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const openCreateModal = () => {
    setEditingAsset(null)
    setName('')
    setDescription('')
    setIsEnabled(true)
    setSelectedFile(null)
    setIsModalOpen(true)
  }

  const openEditModal = (asset: ImageAsset) => {
    setEditingAsset(asset)
    setName(asset.name)
    setDescription(asset.description || '')
    setIsEnabled(asset.status === 'enabled')
    setSelectedFile(null)
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingAsset(null)
    setSelectedFile(null)
  }

  if (query.isPending) return <PageLoading label="Đang tải thư viện ảnh Admin…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const assets = query.data.items || []
  const totalPages = query.data.pages || 1

  return (
    <Page>
      <div className="space-y-3">
        <Badge variant="outline" className="gap-1 font-bold border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400">
          <ShieldCheck className="size-3.5" /> Admin
        </Badge>
        <PageHeader
          title="Thư viện ảnh dùng chung"
          description="Quản lý và upload các tài nguyên hình ảnh hệ thống."
          actions={
            <Button onClick={openCreateModal} className="gap-2">
              <Plus className="size-4" /> Upload ảnh mới
            </Button>
          }
        />
      </div>

      {/* Filter toolbar */}
      <Card className="shadow-xs">
        <CardContent className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_180px_auto]">
          <div className="relative">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9 pr-9"
              placeholder="Tìm theo tên hoặc mô tả ảnh…"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
            />
            {searchText && (
              <button
                type="button"
                className="absolute top-1/2 right-2.5 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setSearchText('')}
              >
                <X className="size-4" />
              </button>
            )}
          </div>

          <NativeSelect
            value={status}
            onChange={(e) => {
              setStatus(e.target.value)
              setPage(1)
            }}
          >
            <NativeSelectOption value="">Tất cả trạng thái</NativeSelectOption>
            <NativeSelectOption value="enabled">🟢 Enabled</NativeSelectOption>
            <NativeSelectOption value="disabled">🔴 Disabled</NativeSelectOption>
            <NativeSelectOption value="missing_file">⚠️ Missing File</NativeSelectOption>
          </NativeSelect>

          {(searchText || status !== '') && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                setSearchText('')
                setDebouncedSearch('')
                setStatus('')
                setPage(1)
              }}
            >
              <RotateCcw className="size-4" />
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Asset Grid */}
      {!assets.length ? (
        <EmptyState
          title="Không tìm thấy ảnh nào"
          description="Thử đổi từ khóa tìm kiếm hoặc upload ảnh mới."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {assets.map((asset) => {
            const assetId = asset.id || asset.asset_id || ''
            const imageUrl = asset.url || `/media/proxy/${assetId}`
            return (
              <Card key={assetId} className="group relative overflow-hidden flex flex-col justify-between">
                <div className="relative aspect-video w-full overflow-hidden bg-muted">
                  <img
                    src={imageUrl}
                    alt={asset.name}
                    className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    onError={(e) => {
                      ;(e.target as HTMLElement).style.display = 'none'
                    }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100 gap-2">
                    <Button
                      size="icon"
                      variant="secondary"
                      className="size-8 rounded-full"
                      onClick={() => setPreviewModalUrl(imageUrl)}
                    >
                      <Eye className="size-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="secondary"
                      className="size-8 rounded-full"
                      onClick={() => openEditModal(asset)}
                    >
                      <ImageIcon className="size-4" />
                    </Button>
                  </div>
                </div>

                <div className="p-3 space-y-1.5 flex-1 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="font-semibold text-sm line-clamp-1">{asset.name}</h4>
                      <Badge
                        variant={asset.status === 'enabled' ? 'default' : 'secondary'}
                        className="text-[10px]"
                      >
                        {asset.status}
                      </Badge>
                    </div>
                    {asset.description && (
                      <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                        {asset.description}
                      </p>
                    )}
                  </div>
                  <div className="pt-2 text-[10px] text-muted-foreground flex justify-between">
                    <span>ID: #{assetId}</span>
                    <span>{asset.mime_type || 'image'}</span>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t pt-4 text-xs">
          <span>Trang {page} / {totalPages}</span>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
            >
              Trước
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
            >
              Sau
            </Button>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      <Dialog open={isModalOpen} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {editingAsset ? 'Chỉnh sửa tài nguyên ảnh' : 'Upload ảnh mới'}
            </DialogTitle>
            <DialogDescription>
              {editingAsset
                ? 'Cập nhật tên, mô tả hoặc thay thế tập tin ảnh.'
                : 'Chọn tập tin ảnh và khai báo thông tin hình ảnh.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="asset-name">Tên hiển thị</Label>
              <Input
                id="asset-name"
                placeholder="Ví dụ: Banner JLPT N3"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="asset-desc">Mô tả ngắn</Label>
              <Textarea
                id="asset-desc"
                rows={3}
                placeholder="Mô tả mục đích sử dụng ảnh…"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="asset-file">
                {editingAsset ? 'Thay đổi File ảnh (Không bắt buộc)' : 'Tập tin ảnh (PNG/JPG/WEBP/SVG)'}
              </Label>
              <Input
                id="asset-file"
                type="file"
                accept="image/*"
                onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label className="text-sm font-semibold">Trạng thái Kích hoạt</Label>
                <p className="text-xs text-muted-foreground">Bật để ảnh hiển thị công khai</p>
              </div>
              <Switch checked={isEnabled} onCheckedChange={setIsEnabled} />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={closeModal}>
              Hủy
            </Button>
            <Button
              disabled={(!editingAsset && !selectedFile) || !name.trim() || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              <Upload className="mr-1.5 size-4" />
              {editingAsset ? 'Cập nhật' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Modal */}
      <Dialog open={Boolean(previewModalUrl)} onOpenChange={() => setPreviewModalUrl(null)}>
        <DialogContent className="sm:max-w-xl p-2">
          {previewModalUrl && (
            <div className="flex items-center justify-center p-2">
              <img src={previewModalUrl} alt="Preview" className="max-h-[70vh] rounded-md object-contain" />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
