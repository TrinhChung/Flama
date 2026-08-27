import { useEffect, useState } from 'react'
import {
  Eye,
  Image as ImageIcon,
  Link as LinkIcon,
  Plus,
  RotateCcw,
  Search,
  ShieldCheck,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { resolveBackendUrl } from '@/config/env'
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
  image_key?: string
  description: string | null
  mime_type?: string
  status: 'enabled' | 'disabled' | string
  file_exists?: boolean
  url?: string
  source_url?: string | null
  tags?: string[]
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
  const [tagsInput, setTagsInput] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [isEnabled, setIsEnabled] = useState(true)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewModalUrl, setPreviewModalUrl] = useState<string | null>(null)
  const [deleteConfirmAsset, setDeleteConfirmAsset] = useState<ImageAsset | null>(null)

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
      formData.append('tags', tagsInput)
      formData.append('status', isEnabled ? 'enabled' : 'disabled')
      if (sourceUrl.trim()) {
        formData.append('source_url', sourceUrl.trim())
      }
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

  const deleteMutation = useMutation({
    mutationFn: async (assetId: string) => {
      return appApi.mutate(`/admin/image-library/${assetId}`, 'DELETE')
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['admin', 'image-library'] })
      toast.success('Đã xóa hình ảnh khỏi thư viện.')
      setDeleteConfirmAsset(null)
    },
    onError: (error: Error) => toast.error(error.message),
  })

  const openCreateModal = () => {
    setEditingAsset(null)
    setName('')
    setDescription('')
    setTagsInput('')
    setSourceUrl('')
    setIsEnabled(true)
    setSelectedFile(null)
    setIsModalOpen(true)
  }

  const openEditModal = (asset: ImageAsset) => {
    setEditingAsset(asset)
    setName(asset.name || asset.image_key || '')
    setDescription(asset.description || '')
    setTagsInput((asset.tags || []).join(', '))
    setSourceUrl(asset.source_url || '')
    setIsEnabled(asset.status === 'enabled')
    setSelectedFile(null)
    setIsModalOpen(true)
  }

  const closeModal = () => {
    setIsModalOpen(false)
    setEditingAsset(null)
    setSelectedFile(null)
    setTagsInput('')
    setSourceUrl('')
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
          description="Quản lý, upload và gắn thẻ tiếng Anh cho các tài nguyên hình ảnh hệ thống."
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
              placeholder="Tìm theo tên, tag tiếng Anh, hoặc mô tả ảnh…"
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
            const rawUrl =
              asset.url ||
              (asset.image_key || asset.name
                ? `/media/library/${asset.image_key || asset.name}`
                : `/media/proxy/${assetId}`)
            const imageUrl = resolveBackendUrl(rawUrl)
            return (
              <Card key={assetId} className="group relative overflow-hidden flex flex-col justify-between">
                <div className="relative aspect-video w-full overflow-hidden bg-muted">
                  <img
                    src={imageUrl}
                    alt={asset.name}
                    className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105"
                    loading="lazy"
                    onError={(e) => {
                      const target = e.target as HTMLImageElement
                      target.onerror = null
                      target.src = resolveBackendUrl('/static/images/image-library-fallback.svg')
                    }}
                  />
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100 gap-2">
                    <Button
                      size="icon"
                      variant="secondary"
                      className="size-8 rounded-full"
                      onClick={() => setPreviewModalUrl(imageUrl)}
                      title="Xem ảnh"
                    >
                      <Eye className="size-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="secondary"
                      className="size-8 rounded-full"
                      onClick={() => openEditModal(asset)}
                      title="Chỉnh sửa"
                    >
                      <ImageIcon className="size-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="destructive"
                      className="size-8 rounded-full"
                      onClick={() => setDeleteConfirmAsset(asset)}
                      title="Xóa ảnh"
                    >
                      <Trash2 className="size-4" />
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
                    {asset.tags && asset.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1.5">
                        {asset.tags.map((t) => (
                          <Badge
                            key={t}
                            variant="outline"
                            className="text-[10px] px-1.5 py-0 font-normal bg-muted/40 cursor-pointer hover:bg-primary/10 hover:text-primary transition-colors"
                            onClick={() => setSearchText(t)}
                          >
                            #{t}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="pt-2 text-[10px] text-muted-foreground flex justify-between items-center">
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
          <Badge variant="outline" className="h-8 px-3 text-xs font-mono font-bold bg-primary/10 text-primary border-primary/30">
            {page} / {totalPages}
          </Badge>
          <div className="flex items-center gap-1.5">
            <Button
              size="sm"
              variant="outline"
              className="h-8 text-xs px-2.5"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
            >
              Trước
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-8 text-xs px-2.5"
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
                ? 'Cập nhật tên, tags tiếng Anh, mô tả hoặc thay thế tập tin ảnh.'
                : 'Chọn tập tin ảnh hoặc link URL và khai báo tags tiếng Anh.'}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="asset-name">Tên hiển thị (Key)</Label>
              <Input
                id="asset-name"
                placeholder="Ví dụ: red_apple hoặc Banner JLPT N3"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="asset-tags">Tags tiếng Anh (phân cách bằng dấu phẩy)</Label>
              <Input
                id="asset-tags"
                placeholder="Ví dụ: apple, red apple, fruit, fresh food"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
              />
              <p className="text-[11px] text-muted-foreground">
                Tags giúp AI và người dùng tìm kiếm và tái sử dụng ảnh nhanh chóng.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="asset-desc">Mô tả ngắn</Label>
              <Textarea
                id="asset-desc"
                rows={2}
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

            <div className="space-y-2">
              <Label htmlFor="asset-url">
                <span className="flex items-center gap-1.5">
                  <LinkIcon className="size-3.5 text-muted-foreground" />
                  Hoặc Link hình ảnh (URL từ Internet)
                </span>
              </Label>
              <Input
                id="asset-url"
                type="url"
                placeholder="https://images.example.com/photo.jpg"
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                disabled={Boolean(selectedFile)}
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
              disabled={(!editingAsset && !selectedFile && !sourceUrl.trim()) || !name.trim() || saveMutation.isPending}
              onClick={() => saveMutation.mutate()}
            >
              <Upload className="mr-1.5 size-4" />
              {editingAsset ? 'Cập nhật' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <Dialog open={Boolean(deleteConfirmAsset)} onOpenChange={(open) => !open && setDeleteConfirmAsset(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-destructive flex items-center gap-2">
              <Trash2 className="size-5" /> Xác nhận xóa ảnh
            </DialogTitle>
            <DialogDescription>
              Bạn có chắc chắn muốn xóa ảnh <strong>“{deleteConfirmAsset?.name}”</strong> (ID: #{deleteConfirmAsset?.id})? Thao tác này sẽ xóa vĩnh viễn tệp ảnh khỏi hệ thống.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmAsset(null)}>
              Hủy
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deleteConfirmAsset && deleteMutation.mutate(deleteConfirmAsset.id || deleteConfirmAsset.asset_id || '')}
            >
              <Trash2 className="mr-1.5 size-4" /> Xóa vĩnh viễn
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview Modal */}
      <Dialog open={Boolean(previewModalUrl)} onOpenChange={() => setPreviewModalUrl(null)}>
        <DialogContent className="sm:max-w-xl p-2">
          {previewModalUrl && (
            <div className="flex items-center justify-center p-2">
              <img
                src={previewModalUrl}
                alt="Preview"
                className="max-h-[70vh] rounded-md object-contain"
                onError={(e) => {
                  const target = e.target as HTMLImageElement
                  target.onerror = null
                  target.src = resolveBackendUrl('/static/images/image-library-fallback.svg')
                }}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}
