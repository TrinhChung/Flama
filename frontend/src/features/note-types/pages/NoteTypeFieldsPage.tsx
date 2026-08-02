import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Check,
  Code2,
  GripVertical,
  Info,
  LoaderCircle,
  Plus,
  Trash2,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { NativeSelect, NativeSelectOption } from '@/components/ui/native-select'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'

type FieldDefItem = {
  id: string
  name: string
  field_type: string
  required: boolean
  position: number
  identity_role: 'primary' | null
}

type NoteTypeDetail = {
  id: string
  name: string
  field_defs?: FieldDefItem[]
}

const FIELD_TYPES = ['text', 'richtext', 'markdown', 'image', 'audio', 'diagram']

export function NoteTypeFieldsPage() {
  const { id: noteTypeId } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null)
  const [isAddingField, setIsAddingField] = useState(false)

  // Edit Field State
  const [editName, setEditName] = useState('')
  const [editType, setEditType] = useState('text')
  const [editRequired, setEditRequired] = useState(false)
  const [editIdentity, setEditIdentity] = useState(false)

  // New Field State
  const [newName, setNewName] = useState('')
  const [newType, setNewType] = useState('text')

  // Drag & Drop State
  const [draggedId, setDraggedId] = useState<string | null>(null)

  const query = useQuery({
    queryKey: ['note-type-fields', noteTypeId],
    queryFn: () => appApi.get<{ items: FieldDefItem[] }>(`/note-types/${noteTypeId}/fields`),
    enabled: Boolean(noteTypeId),
  })

  const detailQuery = useQuery({
    queryKey: ['note-type-detail', noteTypeId],
    queryFn: () => appApi.get<NoteTypeDetail>(`/note-types/${noteTypeId}`),
    enabled: Boolean(noteTypeId),
  })

  const fields = (query.data?.items || []).slice().sort((a, b) => a.position - b.position)
  const selectedField = fields.find((f) => f.id === selectedFieldId) || null

  // Auto-select first field when data loads if none selected
  useEffect(() => {
    if (fields.length && !selectedFieldId && !isAddingField) {
      setSelectedFieldId(fields[0].id)
    }
  }, [fields, selectedFieldId, isAddingField])

  // Sync edit form when selected field changes
  useEffect(() => {
    if (selectedField) {
      setEditName(selectedField.name)
      setEditType(selectedField.field_type)
      setEditRequired(selectedField.required)
      setEditIdentity(selectedField.identity_role === 'primary')
    }
  }, [selectedField])

  // Create Field Mutation
  const createMutation = useMutation({
    mutationFn: (payload: { name: string; field_type: string; required: boolean; identity_role: 'primary' | null }) =>
      appApi.mutate<FieldDefItem>(`/note-types/${noteTypeId}/fields`, 'POST', payload),
    onSuccess: (newField) => {
      toast.success('Đã thêm trường mới.')
      setIsAddingField(false)
      setSelectedFieldId(newField.id)
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể tạo trường mới', { description: error.message })
    },
  })

  // Patch Field Mutation
  const updateMutation = useMutation({
    mutationFn: (payload: { name: string; field_type: string; required: boolean; identity_role: 'primary' | null }) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/${selectedFieldId}`, 'PATCH', payload),
    onSuccess: () => {
      toast.success('Đã cập nhật trường.')
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể cập nhật trường', { description: error.message })
    },
  })

  // Delete Field Mutation
  const deleteMutation = useMutation({
    mutationFn: (fieldId: string) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/${fieldId}`, 'DELETE'),
    onSuccess: () => {
      toast.success('Đã xóa trường.')
      setSelectedFieldId(null)
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể xóa trường', { description: error.message })
    },
  })

  // Reorder Mutation
  const reorderMutation = useMutation({
    mutationFn: (payload: Array<{ id: string; position: number }>) =>
      appApi.mutate(`/note-types/${noteTypeId}/fields/reorder`, 'POST', payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['note-type-fields', noteTypeId] })
    },
    onError: (error: Error) => {
      toast.error('Không thể sắp xếp lại vị trí', { description: error.message })
    },
  })

  const handleDragStart = (id: string) => {
    setDraggedId(id)
  }

  const handleDrop = (targetId: string) => {
    if (!draggedId || draggedId === targetId) return
    const draggedIndex = fields.findIndex((f) => f.id === draggedId)
    const targetIndex = fields.findIndex((f) => f.id === targetId)
    if (draggedIndex < 0 || targetIndex < 0) return

    const reordered = [...fields]
    const [item] = reordered.splice(draggedIndex, 1)
    reordered.splice(targetIndex, 0, item)

    const payload = reordered.map((f, idx) => ({ id: f.id, position: idx }))
    setDraggedId(null)
    reorderMutation.mutate(payload)
  }

  if (query.isPending) return <PageLoading label="Đang tải danh sách trường…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  const noteTypeName = detailQuery.data?.name || 'NoteType'

  return (
    <Page className="w-full max-w-none px-4 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-5 sm:space-y-6">
      <PageHeader
        title={noteTypeName}
        description="Quản lý và sắp xếp các trường thông tin trong NoteType."
        actions={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" asChild className="h-9 px-3.5 text-xs font-semibold rounded-full">
              <Link to="/flashcards/note-types">
                <ArrowLeft className="size-4 mr-1.5" /> Quay lại
              </Link>
            </Button>
            <Button variant="outline" size="sm" asChild className="h-9 px-3.5 text-xs font-semibold rounded-full">
              <Link to={`/flashcards/note-types/${noteTypeId}`}>
                <Code2 className="size-4 mr-1.5" /> Sửa template
              </Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-6 md:grid-cols-12">
        {/* Left Column: Drag-and-drop Field List */}
        <div className="md:col-span-5">
          <Card className="border-border/80 shadow-md rounded-2xl h-full flex flex-col overflow-hidden">
            <CardHeader className="p-4 sm:p-5 flex flex-row items-center justify-between pb-2 sm:pb-2">
              <CardTitle className="text-sm font-semibold">Danh sách trường</CardTitle>
              <Button
                size="sm"
                variant="outline"
                className="h-8 sm:h-9 px-3 text-xs font-semibold rounded-lg"
                onClick={() => {
                  setIsAddingField(true)
                  setSelectedFieldId(null)
                  setNewName('')
                  setNewType('text')
                }}
              >
                <Plus className="size-4 mr-1" /> Thêm
              </Button>
            </CardHeader>
            <CardContent className="p-4 sm:p-5 pt-0 flex-1 space-y-3">
              <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                <Info className="size-3.5 text-primary" /> Kéo thả để sắp xếp lại vị trí trường
              </p>

              <div className="space-y-2 max-h-[480px] overflow-y-auto pr-1">
                {fields.map((field) => (
                  <div
                    key={field.id}
                    draggable
                    onDragStart={() => handleDragStart(field.id)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={() => handleDrop(field.id)}
                    onClick={() => {
                      setIsAddingField(false)
                      setSelectedFieldId(field.id)
                    }}
                    className={`flex items-center gap-3 p-3.5 rounded-xl border transition-all cursor-grab active:cursor-grabbing ${
                      selectedFieldId === field.id && !isAddingField
                        ? 'border-orange-400 bg-orange-50/70 shadow-xs'
                        : 'border-border/60 bg-card hover:bg-muted/40 hover:border-orange-200'
                    }`}
                  >
                    <GripVertical className="size-4 text-muted-foreground/60 shrink-0" />
                    <span className="flex-1 font-semibold text-sm truncate text-foreground">
                      {field.name}
                    </span>
                    <Badge variant="outline" className="text-[11px] font-semibold lowercase px-2.5 py-0.5 rounded-md">
                      {field.field_type}
                    </Badge>
                    {field.identity_role === 'primary' ? (
                      <Badge className="text-[10px]">identity</Badge>
                    ) : null}
                  </div>
                ))}

                {!fields.length ? (
                  <div className="p-6 text-center text-xs text-muted-foreground border border-dashed rounded-xl">
                    Chưa có trường nào. Bấm Nút Thêm để tạo trường mới.
                  </div>
                ) : null}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Field Property Form / Add Field Form */}
        <div className="md:col-span-7">
          {isAddingField ? (
            /* Add New Field Card */
            <Card className="border-primary/30 bg-card shadow-md rounded-2xl">
              <CardHeader className="p-4 sm:p-5 pb-2">
                <CardTitle className="text-sm font-bold text-primary">Thêm trường mới</CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0">
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    if (!newName.trim()) {
                      toast.error('Tên trường là bắt buộc')
                      return
                    }
                    createMutation.mutate({
                      name: newName.trim(),
                      field_type: newType,
                      required: false,
                      identity_role: null,
                    })
                  }}
                  className="space-y-4"
                >
                  <div className="space-y-1.5">
                    <Label htmlFor="new-field-name">Tên trường</Label>
                    <Input
                      id="new-field-name"
                      placeholder="Ví dụ: PitchAccent, Audio, Sentence…"
                      value={newName}
                      onChange={(e) => setNewName(e.target.value)}
                      className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
                      autoFocus
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="new-field-type">Kiểu dữ liệu</Label>
                    <NativeSelect
                      id="new-field-type"
                      value={newType}
                      onChange={(e) => setNewType(e.target.value)}
                      className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
                    >
                      {FIELD_TYPES.map((t) => (
                        <NativeSelectOption key={t} value={t}>
                          {t}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  </div>

                  <div className="flex justify-end gap-2.5 pt-3 border-t">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setIsAddingField(false)
                        if (fields.length) setSelectedFieldId(fields[0].id)
                      }}
                      className="h-9 sm:h-10 px-4 text-xs sm:text-sm font-bold rounded-xl"
                    >
                      Hủy
                    </Button>
                    <Button
                      type="submit"
                      size="sm"
                      disabled={createMutation.isPending}
                      className="h-9 sm:h-10 px-4 bg-gradient-to-r from-primary to-orange-500 font-bold text-xs sm:text-sm text-primary-foreground rounded-xl shadow-xs"
                    >
                      {createMutation.isPending ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <>
                          <Plus className="size-4 mr-1" />
                          Tạo trường
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : selectedField ? (
            /* Edit Field Property Card */
            <Card className="border-border/80 bg-card shadow-md rounded-2xl">
              <CardHeader className="p-4 sm:p-5 pb-2">
                <CardTitle className="text-sm font-bold">Thuộc tính trường</CardTitle>
              </CardHeader>
              <CardContent className="p-4 sm:p-5 pt-0">
                <form
                  onSubmit={(e) => {
                    e.preventDefault()
                    if (!editName.trim()) {
                      toast.error('Tên trường không được trống')
                      return
                    }
                    updateMutation.mutate({
                      name: editName.trim(),
                      field_type: editIdentity ? 'text' : editType,
                      required: editIdentity ? true : editRequired,
                      identity_role: editIdentity ? 'primary' : null,
                    })
                  }}
                  className="space-y-4"
                >
                  <div className="space-y-1.5">
                    <Label htmlFor="edit-field-name">Tên trường</Label>
                    <Input
                      id="edit-field-name"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="edit-field-type">Kiểu dữ liệu</Label>
                    <NativeSelect
                      id="edit-field-type"
                      value={editType}
                      onChange={(e) => setEditType(e.target.value)}
                      disabled={editIdentity}
                      className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl"
                    >
                      {FIELD_TYPES.map((t) => (
                        <NativeSelectOption key={t} value={t}>
                          {t}
                        </NativeSelectOption>
                      ))}
                    </NativeSelect>
                  </div>

                  <div className="flex items-center space-x-2 pt-1">
                    <Checkbox
                      id="edit-field-required"
                      checked={editRequired}
                      disabled={editIdentity}
                      onCheckedChange={(checked) => setEditRequired(Boolean(checked))}
                    />
                    <Label htmlFor="edit-field-required" className="text-xs font-semibold cursor-pointer">
                      Trường bắt buộc
                    </Label>
                  </div>

                  <div className="flex items-start space-x-2 rounded-xl border border-border/70 bg-muted/20 p-3">
                    <Checkbox
                      id="edit-field-identity"
                      checked={editIdentity}
                      onCheckedChange={(checked) => {
                        const enabled = Boolean(checked)
                        setEditIdentity(enabled)
                        if (enabled) {
                          setEditType('text')
                          setEditRequired(true)
                        }
                      }}
                    />
                    <div className="space-y-1">
                      <Label htmlFor="edit-field-identity" className="text-xs font-semibold cursor-pointer">
                        Trường định danh chính
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        Flama Connect dùng trường này để kiểm tra trùng trong đúng deck đích. Mỗi loại thẻ chỉ có một trường định danh.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t">
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      disabled={deleteMutation.isPending || editIdentity}
                      onClick={() => {
                        if (
                          window.confirm(
                            `Xóa trường "${selectedField.name}"? Dữ liệu tương ứng trong các ghi chú sẽ bị giải phóng.`,
                          )
                        ) {
                          deleteMutation.mutate(selectedField.id)
                        }
                      }}
                      className="h-9 sm:h-10 px-4 text-xs sm:text-sm font-bold rounded-xl"
                    >
                      {deleteMutation.isPending ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <>
                          <Trash2 className="size-4 mr-1" />
                          Xóa trường
                        </>
                      )}
                    </Button>

                    <Button
                      type="submit"
                      size="sm"
                      disabled={updateMutation.isPending}
                      className="h-9 sm:h-10 px-4 bg-gradient-to-r from-primary to-orange-500 font-bold text-xs sm:text-sm text-primary-foreground rounded-xl shadow-xs"
                    >
                      {updateMutation.isPending ? (
                        <LoaderCircle className="size-4 animate-spin" />
                      ) : (
                        <>
                          <Check className="size-4 mr-1" />
                          Lưu thay đổi
                        </>
                      )}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          ) : (
            /* Empty Selection Card */
            <Card className="border-dashed border-border bg-muted/20 h-full flex flex-col items-center justify-center p-10 text-center rounded-2xl">
              <p className="text-sm font-semibold text-muted-foreground">
                Chọn một trường bên trái để chỉnh sửa hoặc bấm "Thêm" để tạo trường mới.
              </p>
            </Card>
          )}
        </div>
      </div>
    </Page>
  )
}
