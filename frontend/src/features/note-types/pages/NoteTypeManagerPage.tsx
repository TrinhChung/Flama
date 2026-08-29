import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  Bot,
  CheckCircle,
  Code2,
  ExternalLink,
  HelpCircle,
  Layers,
  LoaderCircle,
  Plus,
  Share2,
  SlidersHorizontal,
  Store,
  Trash2,
} from 'lucide-react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { appApi } from '@/app/api'
import { useBootstrap } from '@/shared/api/bootstrap'
import { AmbientBackground } from '@/components/ambient-background'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
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
import { Page, PageHeader } from '@/shared/components/Page'
import { EmptyState, PageError, PageLoading } from '@/shared/components/PageState'
import { ContextHelpButton } from '@/features/guide'
import { SpotlightTour, type TourStep } from '../components/SpotlightTour'

const TOUR_STORAGE_KEY = 'flama_notetype_spotlight_tour_v1'

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
  const [tourOpen, setTourOpen] = useState(false)

  const query = useQuery({
    queryKey: ['note-types'],
    queryFn: () => appApi.get<NoteTypesResponse>('/note-types'),
  })

  const createMutation = useMutation({
    mutationFn: (newTypeName: string) =>
      appApi.mutate<NoteTypeItem>('/note-types', 'POST', { name: newTypeName }),
    onSuccess: (data) => {
      toast.success('Đã tạo NoteType mới.')
      setName('')
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

  const noteTypes = query.data?.items || []

  const tourSteps: TourStep[] = useMemo(() => {
    const steps: TourStep[] = [
      {
        target: '[data-tour="create-input"]',
        title: '📝 1. Nhập Tên Loại Thẻ Mới',
        content: 'Nhập tên loại thẻ bạn muốn tạo (Ví dụ: Từ vựng N3, Ngữ pháp N2, Kanji Hán Tự) vào ô này.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="create-button"]',
        title: '🚀 2. Bấm Tạo NoteType',
        content: 'Bấm nút này để khởi tạo loại thẻ. Hệ thống sẽ tự động chuyển bạn sang trang Quản lý Trường (Fields) để thêm cột dữ liệu.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="marketplace-btn"]',
        title: '🛍️ 3. Khám Phá Kho NoteType',
        content: 'Bạn cũng có thể khám phá và cài đặt nhanh các mẫu NoteType được chia sẻ sẵn bởi cộng đồng mà không cần tự tạo từ đầu.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="ai-prompt-btn"]',
        title: '🤖 4. Hướng Dẫn & Prompt AI',
        content:
          'Không cần biết lập trình! Bấm nút này để mở trang hướng dẫn và sao chép Master Prompt cho ChatGPT / Claude tự thiết kế mẫu thẻ cho bạn.',
        placement: 'bottom',
      },
    ]

    if (noteTypes.length > 0) {
      steps.push(
        {
          target: '[data-tour="card-first"]',
          title: '📇 5. Thẻ NoteType & Huy Hiệu Thông Số',
          content:
            'Mỗi thẻ hiển thị tên loại thẻ cùng 2 huy hiệu quan trọng: số lượng Template (các mặt thẻ hiển thị) và số lượng Trường dữ liệu hiện có trong bộ thẻ.',
          placement: 'top',
        },
        {
          target: '[data-tour="card-fields-btn"]',
          title: '⚙️ 6. Nút "Trường" (Quản Lý Cột Dữ Liệu)',
          content:
            'Bấm vào đây để thêm các trường như Word, Meaning, Audio, Example, Furigana... định hình cấu trúc dữ liệu lưu trữ cho thẻ.',
          placement: 'top',
        },
        {
          target: '[data-tour="card-template-btn"]',
          title: '🎨 7. Nút "Templates" (Soạn Giao Diện & Xem Trước)',
          content:
            'Bấm vào đây để mở trình soạn thảo HTML/CSS Front & Back, dán mã code tạo bởi AI và xem mô phỏng thẻ mẫu (Live Preview) theo thời gian thực.',
          placement: 'top',
        },
        {
          target: '[data-tour="card-share-btn"]',
          title: '🌐 8. Nút "Chia Sẻ" Lên Kho Cộng Đồng',
          content:
            'Khi đã thiết kế xong mẫu thẻ ưng ý, bạn có thể bấm nút này để xuất bản lên Marketplace cho cộng đồng Flama cùng sử dụng.',
          placement: 'top',
        },
      )
    } else {
      steps.push({
        target: '[data-tour="notetype-grid-area"]',
        title: '📋 5. Khu Vực Danh Sách Loại Thẻ',
        content:
          'Sau khi tạo loại thẻ, các thẻ NoteType sẽ xuất hiện tại đây kèm các nút chức năng: Quản lý Trường (Fields), Tùy chỉnh Template (HTML/CSS), Xem trước Live Preview và Chia sẻ lên Kho Marketplace.',
        placement: 'top',
      })
    }

    return steps
  }, [noteTypes.length])

  // Auto-launch spotlight tour for first-time visitors with no note types
  useEffect(() => {
    if (query.isSuccess) {
      const completed = localStorage.getItem(TOUR_STORAGE_KEY)
      if (!completed && noteTypes.length === 0) {
        // Small delay to ensure DOM is fully rendered
        const timer = setTimeout(() => {
          setTourOpen(true)
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [query.isSuccess, noteTypes.length])

  if (query.isPending) return <PageLoading label="Đang tải danh sách NoteTypes…" />
  if (query.error) return <Page><PageError error={query.error} /></Page>

  return (
    <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
      <AmbientBackground intensity="subtle" />

      <PageHeader
        title="Quản lý Loại Thẻ (Note Types)"
        description="Định nghĩa cấu trúc các trường dữ liệu và tùy chỉnh mẫu hiển thị Flashcard."
        actions={
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto justify-start sm:justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setTourOpen(true)}
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl shrink-0"
            >
              <HelpCircle className="size-3.5 mr-1.5 text-primary shrink-0" />
              <span className="hidden xs:inline">Tour </span>Hướng Dẫn
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild
              data-tour="ai-prompt-btn"
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl border-primary/30 text-primary hover:bg-primary/10 shrink-0"
            >
              <Link to="/flashcards/note-types/guide" target="_blank" rel="noopener noreferrer">
                <Bot className="size-3.5 mr-1.5 text-primary shrink-0" />
                Prompt AI
                <ExternalLink className="size-3 ml-1 opacity-70 shrink-0" />
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              asChild
              data-tour="marketplace-btn"
              className="h-8 sm:h-9 px-2.5 sm:px-3 text-xs font-semibold rounded-xl shrink-0"
            >
              <Link to="/marketplace/note-types">
                <Store className="size-3.5 mr-1.5 text-primary shrink-0" />
                Kho Mẫu
              </Link>
            </Button>
            <ContextHelpButton
              guidePath="/guide/note-types/concept"
              guideTitle="Kiến trúc 1 Note sinh nhiều Cards"
              troubleshootPath="/guide/troubleshooting/import-csv"
              troubleshootTitle="Khắc phục lỗi trường & mẫu thẻ"
              label="Tài liệu"
            />
          </div>
        }
      />

      {/* Compact Create NoteType Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between p-3.5 sm:p-4 rounded-2xl border border-border/80 bg-card shadow-2xs">
        <div className="space-y-0.5 sm:max-w-xs shrink-0">
          <h2 className="text-xs sm:text-sm font-bold text-foreground">Tạo loại thẻ mới</h2>
          <p className="text-[11px] text-muted-foreground">Khởi tạo cấu trúc dữ liệu và template tùy chỉnh.</p>
        </div>
        <form onSubmit={handleCreate} className="flex-1 flex gap-2 items-center">
          <div className="flex-1">
            <Label htmlFor="note-type-name" className="sr-only">
              Tên NoteType
            </Label>
            <Input
              id="note-type-name"
              data-tour="create-input"
              placeholder="Ví dụ: Từ vựng Tiếng Nhật, Ngữ pháp JLPT N2, Kanji Hán Tự…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="h-9 sm:h-10 text-xs sm:text-sm rounded-xl bg-background"
            />
          </div>
          <Button
            type="submit"
            data-tour="create-button"
            disabled={createMutation.isPending}
            className="h-9 sm:h-10 px-4 font-bold text-xs sm:text-sm shadow-xs shrink-0 rounded-xl"
          >
            {createMutation.isPending ? <LoaderCircle className="animate-spin mr-1.5 size-4" /> : <Plus className="size-4 mr-1.5" />}
            Tạo NoteType
          </Button>
        </form>
      </div>

      {/* NoteTypes Card Grid */}
      {!noteTypes.length ? (
        <div data-tour="notetype-grid-area">
          <EmptyState
            title="Chưa có Loại thẻ nào"
            description="Nhập tên ở biểu mẫu trên để tạo NoteType mới hoặc cài đặt mẫu từ Marketplace."
          />
        </div>
      ) : (
        <div className="grid gap-4 sm:gap-5 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {noteTypes.map((item, index) => (
            <Card
              key={item.id}
              data-tour={index === 0 ? 'card-first' : undefined}
              className="group relative flex flex-col justify-between overflow-hidden border-border/80 bg-card p-4 sm:p-5 transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-md rounded-2xl"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <Badge variant="secondary" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                      <Layers className="mr-1 size-3 text-primary" />
                      {item.templates?.length ?? 0} template
                    </Badge>
                    <Badge variant="outline" className="px-2 py-0.5 text-xs font-semibold rounded-md">
                      <SlidersHorizontal className="mr-1 size-3 text-muted-foreground" />
                      {item.field_defs?.length ?? 0} trường
                    </Badge>
                  </div>

                  {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
                    <Badge variant="outline" className="text-xs font-semibold rounded-md border-emerald-500/40 text-emerald-600 dark:text-emerald-400 bg-emerald-500/10">
                      <CheckCircle className="size-3 mr-1 text-emerald-500" />
                      Đã chia sẻ
                    </Badge>
                  ) : null}
                </div>

                <div>
                  <h3 className="text-base font-bold text-foreground group-hover:text-primary transition-colors">
                    <Link to={`/flashcards/note-types/${item.id}/fields`} className="hover:underline">
                      {item.name}
                    </Link>
                  </h3>
                  <p className="text-xs text-muted-foreground mt-1">
                    ID: <span className="font-mono text-[11px]">{item.id}</span>
                  </p>
                </div>
              </div>

              <div className="mt-4 pt-3 border-t border-border/60 flex flex-wrap items-center justify-between gap-1.5 sm:gap-2">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    asChild
                    data-tour={index === 0 ? 'card-fields-btn' : undefined}
                    className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl"
                  >
                    <Link to={`/flashcards/note-types/${item.id}/fields`}>
                      <SlidersHorizontal className="size-3.5 mr-1" />
                      Trường
                    </Link>
                  </Button>

                  <Button
                    variant="outline"
                    size="sm"
                    asChild
                    data-tour={index === 0 ? 'card-template-btn' : undefined}
                    className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl"
                  >
                    <Link to={`/flashcards/note-types/${item.id}`}>
                      <Code2 className="size-3.5 mr-1" />
                      Templates
                    </Link>
                  </Button>

                  {item.publish_status === 'published' || item.publish_status === 'unlisted' ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      asChild
                      data-tour={index === 0 ? 'card-share-btn' : undefined}
                      className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl text-emerald-600 dark:text-emerald-400 hover:bg-emerald-500/10"
                    >
                      <Link to={`/marketplace/note-types/${item.id}`}>
                        <Share2 className="size-3.5 mr-1" />
                        Xem
                      </Link>
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      asChild
                      data-tour={index === 0 ? 'card-share-btn' : undefined}
                      className="h-8 px-2 sm:px-2.5 text-xs font-semibold rounded-xl text-primary hover:text-primary hover:bg-primary/10"
                    >
                      <Link to={`/marketplace/note-types/publish?id=${item.id}`}>
                        <Share2 className="size-3.5 mr-1" />
                        Chia sẻ
                      </Link>
                    </Button>
                  )}
                </div>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 px-2 text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-xl shrink-0"
                  onClick={() => {
                    setPurgeNoteType(false)
                    setNoteTypeToDelete(item)
                  }}
                  title="Xóa NoteType"
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

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

      {/* Interactive Spotlight Onboarding Tour */}
      <SpotlightTour
        steps={tourSteps}
        isOpen={tourOpen}
        onClose={() => {
          localStorage.setItem(TOUR_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
        onComplete={() => {
          localStorage.setItem(TOUR_STORAGE_KEY, 'true')
          setTourOpen(false)
        }}
      />
    </Page>
  )
}
