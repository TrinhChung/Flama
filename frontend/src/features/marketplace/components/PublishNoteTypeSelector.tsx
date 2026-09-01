import { useMemo, useState } from 'react'
import {
  Code2,
  Layers,
  LockKeyhole,
  Search,
  Shapes,
} from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'

export type PublishNoteTypeOption = {
  id: string
  name: string
  field_count?: number
  field_defs?: Array<{ id?: string; name: string }>
  templates?: Array<{ id?: string; name: string }>
  publish_status?: string
  is_marketplace_install?: boolean
}

export function getNoteTypeBlockInfo(noteType: PublishNoteTypeOption): {
  isBlocked: boolean
  label: string | null
  reason: string | null
} {
  if (noteType.is_marketplace_install) {
    return {
      isBlocked: true,
      label: 'Từ Marketplace',
      reason: 'Mẫu thẻ được tải về từ Marketplace nên không thể chia sẻ lại.',
    }
  }
  if (noteType.publish_status === 'published' || noteType.publish_status === 'unlisted') {
    return {
      isBlocked: true,
      label: 'Đã xuất bản',
      reason: 'Mẫu thẻ này đã được xuất bản lên Marketplace.',
    }
  }
  return {
    isBlocked: false,
    label: null,
    reason: null,
  }
}

export type PublishNoteTypeSelectorProps = {
  noteTypes: PublishNoteTypeOption[]
  selectedNoteTypeId: string
  onSelectNoteType: (noteType: PublishNoteTypeOption) => void
  hasError?: boolean
}

export function PublishNoteTypeSelector({
  noteTypes,
  selectedNoteTypeId,
  onSelectNoteType,
  hasError = false,
}: PublishNoteTypeSelectorProps) {
  const [search, setSearch] = useState('')

  const filteredNoteTypes = useMemo(() => {
    const query = search.trim().toLocaleLowerCase('vi')
    if (!query) return noteTypes
    return noteTypes.filter((nt) => {
      const blockInfo = getNoteTypeBlockInfo(nt)
      const haystack = `${nt.name} ${nt.id} ${blockInfo.label || ''} ${blockInfo.reason || ''}`.toLocaleLowerCase('vi')
      return haystack.includes(query)
    })
  }, [noteTypes, search])

  return (
    <div className="space-y-2.5">
      {noteTypes.length > 3 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Tìm kiếm mẫu thẻ theo tên..."
            className="h-9 rounded-xl pl-9 text-xs"
          />
        </div>
      )}

      <div
        role="listbox"
        aria-label="Danh sách mẫu thẻ nguồn"
        className={`max-h-72 space-y-1.5 overflow-y-auto rounded-2xl border p-2.5 shadow-inner transition-colors ${
          hasError
            ? 'border-destructive/60 bg-destructive/5'
            : 'border-border/80 bg-muted/15'
        }`}
      >
        {filteredNoteTypes.length > 0 ? (
          filteredNoteTypes.map((nt) => {
            const blockInfo = getNoteTypeBlockInfo(nt)
            const isSelected = nt.id === selectedNoteTypeId
            const fieldCount = nt.field_defs?.length ?? nt.field_count ?? 0
            const templateCount = nt.templates?.length ?? 0

            const handleSelect = () => {
              if (!blockInfo.isBlocked) {
                onSelectNoteType(nt)
              }
            }

            return (
              <div
                key={nt.id}
                role="option"
                aria-selected={isSelected}
                aria-disabled={blockInfo.isBlocked}
                tabIndex={blockInfo.isBlocked ? -1 : 0}
                title={blockInfo.reason || `Chọn mẫu thẻ ${nt.name}`}
                onClick={handleSelect}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    handleSelect()
                  }
                }}
                className={`flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-xs transition-all ${
                  blockInfo.isBlocked
                    ? 'cursor-not-allowed border-transparent bg-muted/20 text-muted-foreground opacity-60 select-none hover:bg-muted/20'
                    : isSelected
                      ? 'border-primary/40 bg-primary/10 text-primary shadow-xs ring-1 ring-primary/20 font-semibold cursor-pointer'
                      : 'cursor-pointer border-transparent hover:bg-muted/60 text-foreground'
                }`}
              >
                <div className="flex min-w-0 flex-1 items-center gap-2.5">
                  <div
                    className={`size-7 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                      blockInfo.isBlocked
                        ? 'bg-muted text-muted-foreground'
                        : isSelected
                          ? 'bg-primary/20 text-primary'
                          : 'bg-muted/80 text-muted-foreground'
                    }`}
                  >
                    {templateCount > 1 ? (
                      <Layers className="size-3.5" />
                    ) : (
                      <Shapes className="size-3.5" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold truncate leading-tight">{nt.name}</div>
                    <div className="text-[10px] text-muted-foreground font-mono truncate">
                      ID: {nt.id}
                    </div>
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-1.5 ml-2">
                  {fieldCount > 0 && (
                    <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-medium shrink-0 bg-background/80 border">
                      <Code2 className="size-2.5 mr-1 text-muted-foreground" />
                      {fieldCount} trường
                    </Badge>
                  )}
                  {templateCount > 0 && (
                    <Badge variant="outline" className="px-1.5 py-0 text-[10px] font-medium shrink-0 hidden sm:inline-flex">
                      {templateCount} template
                    </Badge>
                  )}
                  {blockInfo.label && (
                    <Badge
                      variant="outline"
                      className="gap-1 px-1.5 py-0 text-[10px] font-medium shrink-0 max-w-[120px] truncate border-muted-foreground/30 text-muted-foreground bg-muted/40"
                    >
                      <LockKeyhole className="size-2.5 shrink-0 text-muted-foreground" />
                      <span className="truncate">{blockInfo.label}</span>
                    </Badge>
                  )}
                </div>
              </div>
            )
          })
        ) : (
          <div className="py-6 text-center text-xs text-muted-foreground">
            {noteTypes.length === 0
              ? 'Bạn chưa có mẫu thẻ nào. Hãy tạo hoặc chỉnh sửa mẫu thẻ trước khi đăng tải.'
              : 'Không tìm thấy mẫu thẻ phù hợp.'}
          </div>
        )}
      </div>
    </div>
  )
}
