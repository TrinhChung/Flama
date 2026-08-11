import { useState } from 'react'
import {
  AlertCircle,
  CheckCircle,
  Code2,
  LoaderCircle,
  Plus,
  Share2,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type NoteTypeItem = {
  id: string
  name: string
  field_defs?: Array<{ id: string; name: string }>
  templates?: Array<{ id: string; name: string }>
  publish_status?: string
  created_at?: string
  updated_at?: string
}

type NoteTypesResponse = {
  items: NoteTypeItem[]
}

export function NoteTypeManagerPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const bootstrapQuery = useBootstrap()
  const isAdmin = Boolean(bootstrapQuery.data?.user?.is_admin)
  const [name, setName] = useState('')
  const [noteTypeToDelete, setNoteTypeToDelete] = useState<NoteTypeItem | null>(null)
  const [purgeNoteType, setPurgeNoteType] = useState(false)

  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<NoteTypesResponse>('/note-types'),
  })

  const createMutation = useMutation({
    mutationFn: (newTypeName: string) =>
      appApi.mutate<NoteTypeItem>('/note-types', 'POST', { name: newTypeName }),
    onSuccess: (data) => {
      toast.success('Đã tạo NoteType mới.')
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
      navigate(`/flashcards/note-types/${data.id}/fields`)
    },
    onError: (error: Error) => {
      toast.error('Không thể tạo NoteType', { description: error.message })
    },
  })

  const deleteMutation = useMutation<unknown, Error, { id: string; purge?: boolean }>({
    mutationFn: ({ id, purge }) => {
      const suffix = purge ? '?purge=true' : ''
      return appApi.mutate(`/note-types/${id}${suffix}`, 'DELETE')
    },
    onSuccess: () => {
      toast.success('Thao tác xóa NoteType đã hoàn tất.')
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
      setNoteTypeToDelete(null)
      setPurgeNoteType(false)
    },
    onError: (error: Error) => {
      toast.error('Không thể xóa NoteType', { description: error.message })
    },
  })

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) {
      toast.error('Vui lòng nhập tên NoteType')
      return
    }
    createMutation.mutate(trimmed)
  }

  if (query.isPending) return <PageLoading label="Đang tải danh sách NoteTypes…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const noteTypes = query.data?.items || []

  return (
    <Page className="w-full max-w-none px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5 sm:space-y-6">
      <PageHeader
        title="Quản lý Loại thẻ (NoteType Manager)"
        description="Định nghĩa cấu trúc các trường dữ liệu và mẫu hiển thị flashcard của bạn."
      />

      {/* Create NoteType Card Form */}
      <Card className="border-border/80 shadow-xs rounded-2xl">
        <CardHeader className="p-4 sm:p-5 pb-2 sm:pb-2">
          <CardTitle className="text-sm font-semibold">Tạo NoteType mới</CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0">
          <form onSubmit={handleCreate} className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 space-y-1">
              <Label htmlFor="note-type-name" className="sr-only">
                Tên NoteType
              </Label>
              <Input
                id="note-type-name"
                placeholder="Ví dụ: Từ vựng Tiếng Nhật, Ngữ pháp JLPT N2…"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
              />
            </div>
            <Button
              type="submit"
              disabled={createMutation.isPending}
              className="h-9 sm:h-10 px-4 bg-gradient-to-r from-primary to-orange-500 font-bold text-xs sm:text-sm text-primary-foreground shadow-xs shrink-0 rounded-xl"
            >
              <Plus className="size-4 mr-1.5" />
              Tạo NoteType
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* NoteTypes Table */}
      <Card className="overflow-hidden border-border/80 shadow-md rounded-2xl">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30">
              <TableHead className="font-bold">Tên NoteType</TableHead>
              <TableHead className="font-bold">Trường dữ liệu</TableHead>
              <TableHead className="font-bold">Templates</TableHead>
              <TableHead className="text-right font-bold">Thao tác</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {noteTypes.map((item) => (
              <TableRow key={item.id} className="hover:bg-muted/40 transition-colors">
                <TableCell className="font-bold text-foreground">
                  <Link
                    to={`/flashcards/note-types/${item.id}/fields`}
                    className="hover:text-primary transition-colors"
                  >
                    {item.name}
                  </Link>
                </TableCell>
                <TableCell>{item.field_defs?.length ?? 0} trường</TableCell>
                <TableCell>{item.templates?.length ?? 0} template</TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
                      <Link to={`/flashcards/note-types/${item.id}/fields`}>
                        <SlidersHorizontal className="size-3.5 mr-1" />
                        Trường
                      </Link>
                    </Button>

                    <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
                      <Link to={`/flashcards/note-types/${item.id}`}>
                        <Code2 className="size-3.5 mr-1" />
                        Templates
                      </Link>
                    </Button>

                    {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
                      <Button variant="outline" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg border-emerald-500/40 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10">
                        <Link to={`/marketplace/note-types/${item.id}`}>
                          <CheckCircle className="size-3.5 mr-1 text-emerald-500" />
                          Đã chia sẻ
                        </Link>
                      </Button>
                    ) : (
                      <Button variant="secondary" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
                        <Link to={`/marketplace/note-types/publish?id=${item.id}`}>
                          <Share2 className="size-3.5 mr-1 text-orange-600" />
                          Chia sẻ
                        </Link>
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 sm:h-9 px-2.5 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 rounded-lg"
                      onClick={() => {
                        setPurgeNoteType(false)
                        setNoteTypeToDelete(item)
                      }}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}

            {!noteTypes.length ? (
              <TableRow>
                <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                  Chưa có NoteType nào. Hãy nhập tên ở trên để tạo NoteType đầu tiên.
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </Card>

      {noteTypeToDelete && (
        <Dialog open onOpenChange={(open) => !open && setNoteTypeToDelete(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Xác nhận xóa NoteType</DialogTitle>
              <DialogDescription>
                Xóa NoteType “{noteTypeToDelete.name}”? Hành động này có thể không hoàn tác được.
              </DialogDescription>
            </DialogHeader>

            {isAdmin && (
              <div className="space-y-3 p-3 rounded-lg border border-destructive/20 bg-destructive/5 dark:bg-destructive/10">
                <div className="flex items-center gap-2">
                  <input
                    id="purge-notetype-checkbox"
                    type="checkbox"
                    checked={purgeNoteType}
                    onChange={(e) => setPurgeNoteType(e.target.checked)}
                    className="size-4 rounded border-input text-destructive focus:ring-destructive accent-destructive cursor-pointer"
                  />
                  <Label htmlFor="purge-notetype-checkbox" className="font-bold text-destructive cursor-pointer select-none">
                    Xóa sạch hoàn toàn dữ liệu (Purge)
                  </Label>
                </div>
                {purgeNoteType && (
                  <Alert variant="destructive" className="border-none bg-transparent p-0 flex items-start">
                    <AlertCircle className="size-4 mt-0.5 text-destructive shrink-0" />
                    <AlertDescription className="text-xs text-destructive/90 font-medium ml-2 leading-relaxed">
                      Cảnh báo: Chức năng này chỉ dùng để xóa các bộ note type lỗi trong quá trình phát triển. Nó sẽ xóa sạch toàn bộ note type cùng với các trường (fields), templates, note/card, tiến trình học và các thay đổi liên quan khỏi hệ thống và không thể hoàn tác.
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setNoteTypeToDelete(null)}>
                Hủy
              </Button>
              <Button
                variant="destructive"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate({ id: noteTypeToDelete.id, purge: purgeNoteType })}
              >
                {deleteMutation.isPending ? <LoaderCircle className="animate-spin mr-1.5 size-4" /> : null}
                {purgeNoteType ? 'Xóa sạch dữ liệu' : 'Xóa NoteType'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </Page>
  )
}
