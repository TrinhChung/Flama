import { useRef, useState } from 'react'
import { Camera, Image as ImageIcon, LoaderCircle, Trash2, Upload } from 'lucide-react'
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
import { profileApi } from '../api/profileApi'

export function AvatarUploadModal({
  open,
  onOpenChange,
  currentAvatarUrl,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentAvatarUrl?: string | null
}) {
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      toast.error('Vui lòng chọn tệp hình ảnh hợp lệ (PNG, JPG, WebP, GIF).')
      return
    }

    if (file.size > 5 * 1024 * 1024) {
      toast.error('Dung lượng ảnh vượt quá 5MB. Vui lòng chọn ảnh nhỏ hơn.')
      return
    }

    setSelectedFile(file)
    const objectUrl = URL.createObjectURL(file)
    setPreviewUrl(objectUrl)
  }

  const uploadMutation = useMutation({
    mutationFn: (file: File) => profileApi.uploadAvatar(file),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['public-profile'] })
      void queryClient.invalidateQueries({ queryKey: ['bootstrap'] })
      toast.success('Đã cập nhật ảnh đại diện thành công!')
      onOpenChange(false)
      setSelectedFile(null)
      setPreviewUrl(null)
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Không thể tải lên ảnh đại diện.')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: () => profileApi.deleteAvatar(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['profile'] })
      void queryClient.invalidateQueries({ queryKey: ['public-profile'] })
      void queryClient.invalidateQueries({ queryKey: ['bootstrap'] })
      toast.success('Đã gỡ ảnh đại diện.')
      onOpenChange(false)
      setSelectedFile(null)
      setPreviewUrl(null)
    },
    onError: (err: any) => {
      toast.error(err?.message || 'Không thể gỡ ảnh đại diện.')
    },
  })

  const handleClose = (nextOpen: boolean) => {
    if (!nextOpen) {
      setSelectedFile(null)
      setPreviewUrl(null)
    }
    onOpenChange(nextOpen)
  }

  const displayImage = previewUrl || currentAvatarUrl

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[420px] max-h-[90vh] overflow-y-auto p-4 sm:p-6">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base sm:text-lg font-bold">
            <Camera className="size-5 text-primary" />
            Cập nhật ảnh đại diện
          </DialogTitle>
          <DialogDescription className="text-xs sm:text-sm">
            Tải lên ảnh mới (tối đa 5MB, tự động cắt vuông và tối ưu định dạng WebP).
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col items-center justify-center gap-4 py-3 sm:py-4">
          <div className="relative flex size-32 sm:size-36 items-center justify-center overflow-hidden rounded-full border-4 border-muted/80 bg-muted shadow-md ring-2 ring-primary/20">
            {displayImage ? (
              <img
                src={displayImage}
                alt="Avatar preview"
                className="size-full object-cover"
              />
            ) : (
              <ImageIcon className="size-12 sm:size-14 text-muted-foreground/40" />
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            onChange={handleFileChange}
            className="hidden"
          />

          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
              className="gap-1.5 text-xs font-semibold rounded-lg h-9 px-4 active:scale-98 cursor-pointer"
            >
              <Upload className="size-3.5" />
              Chọn ảnh từ máy
            </Button>

            {currentAvatarUrl && !selectedFile ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="gap-1.5 text-xs font-semibold text-destructive hover:bg-destructive/10 hover:text-destructive h-9 px-3 active:scale-98 cursor-pointer"
              >
                {deleteMutation.isPending ? (
                  <LoaderCircle className="size-3.5 animate-spin" />
                ) : (
                  <Trash2 className="size-3.5" />
                )}
                Gỡ ảnh
              </Button>
            ) : null}
          </div>
        </div>

        <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => handleClose(false)}
            disabled={uploadMutation.isPending || deleteMutation.isPending}
            className="w-full sm:w-auto"
          >
            Hủy
          </Button>
          <Button
            type="button"
            disabled={!selectedFile || uploadMutation.isPending}
            onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}
            className="w-full sm:w-auto font-semibold bg-gradient-to-r from-primary to-orange-500 text-primary-foreground hover:opacity-95"
          >
            {uploadMutation.isPending ? (
              <>
                <LoaderCircle className="mr-2 size-4 animate-spin" />
                Đang xử lý…
              </>
            ) : (
              'Lưu ảnh đại diện'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
