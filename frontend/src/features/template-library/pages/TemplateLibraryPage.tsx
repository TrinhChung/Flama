import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { cardTemplateQueryKeys, fetchTemplateLibrary, type TemplateLibraryGroup, type TemplateLibraryParams } from '@/entities/card-template'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'
import { PageError, PageLoading } from '@/shared/components/PageState'
import { SearchInput, FilterPillGroup } from '@/shared/ui'
import { CreateTemplateDialog } from '../components/CreateTemplateDialog'

const filters: { value: TemplateLibraryGroup; label: string }[] = [
  { value: 'all', label: 'Tất cả' }, { value: 'mine', label: 'Của tôi' }, { value: 'market', label: 'Marketplace' },
  { value: 'standalone', label: 'Mẫu độc lập' }, { value: 'in_use', label: 'Đang dùng' },
]
export function TemplateLibraryPage() {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [composing, setComposing] = useState(false)
  const [group, setGroup] = useState<TemplateLibraryGroup>('all')
  const [createOpen, setCreateOpen] = useState(false)
  const [includeArchived, setIncludeArchived] = useState(false)
  useEffect(() => {
    if (composing) return
    const timer = setTimeout(() => setQuery(search), 300)
    return () => clearTimeout(timer)
  }, [search, composing])
  const params = useMemo<TemplateLibraryParams>(() => ({ ...(query ? { q: query } : {}), ...(group !== 'all' ? { group } : {}), ...(includeArchived ? { include_archived: true } : {}) }), [query, group, includeArchived])
  const library = useQuery({ queryKey: cardTemplateQueryKeys.library(params), queryFn: ({ signal }) => fetchTemplateLibrary(params, signal) })
  return <Page className="w-full max-w-7xl px-3 sm:px-6 lg:px-8 py-4 sm:py-6 space-y-6">
    <PageHeader title="Mẫu thẻ" description="Thư viện template dùng lại cho nhiều loại thẻ." actions={<Button className="rounded-xl gap-2" onClick={() => setCreateOpen(true)}><Plus className="size-4" />Tạo mẫu mới</Button>} />
    <div className="space-y-3"><SearchInput aria-label="Tìm mẫu thẻ" placeholder="Tìm mẫu thẻ…" value={search} onChange={(event) => setSearch(event.target.value)} onCompositionStart={() => setComposing(true)} onCompositionEnd={(event) => { setSearch(event.currentTarget.value); setComposing(false) }} /><FilterPillGroup options={filters} value={group} onChange={setGroup} aria-label="Nhóm mẫu thẻ" /><label className="flex items-center gap-2 text-sm text-muted-foreground"><input type="checkbox" checked={includeArchived} onChange={(event) => setIncludeArchived(event.target.checked)} />Hiện mẫu lưu trữ</label></div>
    {library.isPending ? <PageLoading label="Đang tải mẫu thẻ…" /> : library.error ? <div className="space-y-3"><PageError error={library.error} /><Button variant="outline" onClick={() => void library.refetch()}>Thử lại</Button></div> : !library.data?.items.length ? <p className="rounded-xl border border-dashed p-8 text-center text-muted-foreground">Chưa có mẫu thẻ nào.</p> :
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{library.data.items.map((template) => <Link key={template.id} to={`/card-templates/${encodeURIComponent(template.id)}`} className="rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <Card className="h-full p-4 space-y-3 rounded-2xl border-border/80 hover:border-primary/40 transition-colors">
          <div className="space-y-1"><h2 className="font-semibold line-clamp-2 break-words">{template.name}</h2>{template.description && <p className="text-sm text-muted-foreground line-clamp-2 break-words">{template.description}</p>}</div>
          <Badge variant="secondary">{template.origin === 'market_copy' ? 'Bản nhận' : 'Của tôi'}</Badge>
          {template.archived_at && <Badge variant="outline">Đã lưu trữ</Badge>}
          <p className="text-xs text-muted-foreground">{template.note_type_count ? `Dùng ở ${template.note_type_count} loại thẻ` : 'Chưa dùng'}{template.application_count > template.note_type_count && ` · ${template.application_count} lần gắn`}</p>
          <div className="flex flex-wrap gap-1.5">{template.input_schema.slice(0, 4).map((input) => <code key={input.key} className="rounded-md bg-muted px-1.5 py-0.5 text-xs break-all">{`{{${input.key}}}`}</code>)}{template.input_schema.length > 4 && <span className="text-xs text-muted-foreground">+{template.input_schema.length - 4}</span>}</div>
        </Card>
      </Link>)}</div>}
    <CreateTemplateDialog open={createOpen} onOpenChange={setCreateOpen} />
  </Page>
}
