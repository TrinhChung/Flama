import { useState } from 'react'
import {
  Code2,
  Plus,
  Share2,
  SlidersHorizontal,
  Trash2,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  created_at?: string
  updated_at?: string
}

type NoteTypesResponse = {
  items: NoteTypeItem[]
}

export function NoteTypeManagerPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [name, setName] = useState('')

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

  const deleteMutation = useMutation({
    mutationFn: (id: string) => appApi.mutate(`/note-types/${id}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa NoteType.')
      void queryClient.invalidateQueries({ queryKey: ['note-types'] })
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

                    <Button variant="secondary" size="sm" asChild className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg">
                      <a href={`/flashcards/share-note-type/${item.id}`}>
                        <Share2 className="size-3.5 mr-1 text-orange-600" />
                        Chia sẻ
                      </a>
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 sm:h-9 px-2.5 text-xs text-destructive hover:text-destructive hover:bg-destructive/10 rounded-lg"
                      onClick={() => {
                        if (window.confirm(`Xóa NoteType "${item.name}"?`)) {
                          deleteMutation.mutate(item.id)
                        }
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
    </Page>
  )
}
