import type { ChangeEvent } from 'react'
import { Button } from '@/shared/ui'
import { useEditCardModal, type EditCardModalProps } from '../hooks/useEditCardModal'

const EMPTY_FIELDS: NonNullable<EditCardModalProps['fieldDefs']> = []
const EMPTY_VALUES: Record<string, string> = {}
const EMPTY_TAGS: string[] = []

function parseInlineMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Images: ![alt](src)
  html = html.replace(
    /!\[([^\]]*)\]\(([^)\s]+)\)/g,
    '<img src="$2" alt="$1" class="max-h-40 rounded-lg border border-border my-2 block shadow-sm" />'
  )

  // Links: [label](url)
  html = html.replace(
    /\[([^\]]+)\]\(([^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noreferrer" class="text-primary underline font-semibold">$1</a>'
  )

  // Inline code: `code`
  html = html.replace(
    /`([^`]+)`/g,
    '<code class="bg-muted px-1.5 py-0.5 rounded font-mono text-[11px] text-primary">$1</code>'
  )

  // Bold & Italic & Strikethrough
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold text-foreground">$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>')
  html = html.replace(/~~([^~]+)~~/g, '<s class="line-through text-muted-foreground">$1</s>')

  return html
}

function parseMarkdownToHtml(md: string): string {
  if (!md || !md.trim()) return '<em class="text-muted-foreground italic">Nội dung trống</em>'

  const lines = md.split('\n')
  const blocks: string[] = []
  let inCodeBlock = false
  let codeBuffer: string[] = []
  let inList = false
  let listBuffer: string[] = []

  const flushList = () => {
    if (inList && listBuffer.length > 0) {
      blocks.push(`<ul class="list-disc pl-5 my-2 space-y-1 text-xs">${listBuffer.join('')}</ul>`)
      listBuffer = []
      inList = false
    }
  }

  const flushCode = () => {
    if (inCodeBlock && codeBuffer.length > 0) {
      const codeText = codeBuffer.join('\n').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      blocks.push(
        `<pre class="bg-muted p-2.5 rounded-lg font-mono text-xs overflow-x-auto my-2 border border-border"><code>${codeText}</code></pre>`
      )
      codeBuffer = []
      inCodeBlock = false
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        flushCode()
      } else {
        flushList()
        inCodeBlock = true
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      continue
    }

    const trimmed = line.trim()
    if (!trimmed) {
      flushList()
      continue
    }

    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      inList = true
      const content = parseInlineMarkdown(trimmed.slice(2))
      listBuffer.push(`<li>${content}</li>`)
      continue
    } else {
      flushList()
    }

    if (trimmed.startsWith('### ')) {
      blocks.push(
        `<h3 class="text-sm font-bold text-foreground mt-2 mb-1">${parseInlineMarkdown(
          trimmed.slice(4)
        )}</h3>`
      )
      continue
    }
    if (trimmed.startsWith('## ')) {
      blocks.push(
        `<h2 class="text-base font-bold text-foreground mt-2.5 mb-1">${parseInlineMarkdown(
          trimmed.slice(3)
        )}</h2>`
      )
      continue
    }
    if (trimmed.startsWith('# ')) {
      blocks.push(
        `<h1 class="text-lg font-bold text-foreground mt-3 mb-1">${parseInlineMarkdown(
          trimmed.slice(2)
        )}</h1>`
      )
      continue
    }

    if (trimmed.startsWith('> ')) {
      blocks.push(
        `<blockquote class="border-l-4 border-primary/60 pl-3 py-1 text-muted-foreground italic my-2 bg-muted/30 rounded-r-lg">${parseInlineMarkdown(
          trimmed.slice(2)
        )}</blockquote>`
      )
      continue
    }

    blocks.push(`<p class="my-1 text-xs leading-relaxed text-foreground">${parseInlineMarkdown(line)}</p>`)
  }

  flushList()
  flushCode()

  return blocks.join('')
}

export function EditCardModal({
  opened,
  onClose,
  cardId,
  noteId,
  saveUrl,
  fieldDefs = EMPTY_FIELDS,
  initialFieldValues = EMPTY_VALUES,
  initialDeckId,
  initialTags = EMPTY_TAGS,
  decks = [],
  onSaved,
  onDeleted,
}: EditCardModalProps) {
  const {
    fieldValues, setFieldValues, deckId, setDeckId, tagsStr, setTagsStr, saving,
    uploadingField, error, activeFieldName, setActiveFieldName, fieldModes,
    globalPreview, setGlobalPreview, targetFieldName, insertMarkdownSyntax,
    handleMediaUpload, handleSave, handleDelete, toggleFieldMode,
  } = useEditCardModal({
    opened, onClose, cardId, noteId, saveUrl, fieldDefs, initialFieldValues,
    initialDeckId, initialTags, onSaved, onDeleted,
  })
  if (!opened) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-2xl rounded-2xl border border-border bg-card p-6 shadow-xl max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between border-b pb-3 mb-4">
          <div>
            <h3 className="text-lg font-bold text-foreground">Sửa thẻ hiện tại</h3>
            {noteId ? (
              <span className="text-xs text-muted-foreground">Note ID: {noteId}</span>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground text-xl font-bold px-2"
            aria-label="Đóng"
          >
            &times;
          </button>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg bg-destructive/10 p-3 text-xs text-destructive font-medium">
            {error}
          </div>
        ) : null}

        <div className="flex-1 overflow-y-auto space-y-4 pr-1">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pb-2 border-b">
            <div>
              <label className="text-xs font-bold text-foreground block mb-1">Deck</label>
              <select
                className="w-full rounded-lg border border-input bg-background p-2 text-xs text-foreground focus:ring-2 focus:ring-primary focus:outline-none"
                value={deckId ?? ''}
                onChange={(e) => setDeckId(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Không chọn</option>
                {decks.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-bold text-foreground block mb-1">
                Tags <span className="font-normal text-muted-foreground">(phẩy phân cách)</span>
              </label>
              <input
                type="text"
                className="w-full rounded-lg border border-input bg-background p-2 text-xs text-foreground focus:ring-2 focus:ring-primary focus:outline-none"
                placeholder="JLPT-N1, Kanji..."
                value={tagsStr}
                onChange={(e) => setTagsStr(e.target.value)}
              />
            </div>
          </div>

          {/* Unified Sticky Markdown Toolbar */}
          <div className="sticky top-0 z-10 bg-muted/90 backdrop-blur-md rounded-xl p-2 border border-border shadow-sm flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 overflow-x-auto text-xs">
              <span className="text-[10px] font-bold uppercase tracking-wider text-primary bg-primary/10 px-2 py-0.5 rounded-full whitespace-nowrap">
                {targetFieldName ? `Field: ${targetFieldName}` : 'Markdown Toolbar'}
              </span>
              <div className="h-4 w-px bg-border my-auto mx-0.5" />
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent font-bold text-foreground transition-colors"
                title="In đậm (**text**)"
                onClick={() => insertMarkdownSyntax('**', '**')}
              >
                B
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent italic text-foreground transition-colors"
                title="In nghiêng (*text*)"
                onClick={() => insertMarkdownSyntax('*', '*')}
              >
                I
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent font-mono text-foreground transition-colors"
                title="Tiêu đề (## Text)"
                onClick={() => insertMarkdownSyntax('## ')}
              >
                H2
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent font-mono text-foreground transition-colors"
                title="Danh sách (- item)"
                onClick={() => insertMarkdownSyntax('- ')}
              >
                • List
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent font-mono text-foreground transition-colors"
                title="Trích dẫn (> quote)"
                onClick={() => insertMarkdownSyntax('> ')}
              >
                &rdquo; Quote
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent font-mono text-foreground transition-colors"
                title="Inline Code (`code`)"
                onClick={() => insertMarkdownSyntax('`', '`')}
              >
                Code
              </button>
              <button
                type="button"
                className="px-2 py-1 rounded-md bg-background hover:bg-accent text-foreground transition-colors"
                title="Chèn Link ([text](url))"
                onClick={() => insertMarkdownSyntax('[', '](https://)')}
              >
                Link
              </button>
            </div>

            <div className="flex items-center gap-1 bg-background p-0.5 rounded-lg border text-xs">
              <button
                type="button"
                className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all ${
                  !globalPreview
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => {
                  setGlobalPreview(false)
                  if (targetFieldName) toggleFieldMode(targetFieldName, 'edit')
                }}
              >
                Soạn thảo (Edit)
              </button>
              <button
                type="button"
                className={`px-2.5 py-1 text-[10px] font-bold rounded-md transition-all ${
                  globalPreview
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
                onClick={() => {
                  setGlobalPreview(true)
                  if (targetFieldName) toggleFieldMode(targetFieldName, 'preview')
                }}
              >
                Xem trước (Preview)
              </button>
            </div>
          </div>

          {fieldDefs.length ? (
            fieldDefs.map((field) => {
              const fieldType = field.field_type.toLowerCase()
              const isMedia = ['image', 'audio', 'diagram'].includes(fieldType)
              const isMarkdownCapable =
                fieldType === 'markdown' || fieldType === 'text' || fieldType === 'richtext'
              const val = fieldValues[field.name] || ''
              const isPreviewMode = globalPreview || fieldModes[field.name] === 'preview'
              const isFocused = activeFieldName === field.name

              return (
                <div
                  key={field.name}
                  className={`space-y-1.5 p-2.5 rounded-xl border transition-colors ${
                    isFocused
                      ? 'bg-accent/20 border-primary/40 shadow-sm'
                      : 'border-border/60 bg-background/50'
                  }`}
                  onClick={() => setActiveFieldName(field.name)}
                >
                  <div className="flex items-center justify-between text-xs font-bold text-foreground">
                    <span className="flex items-center gap-1.5">
                      {field.name}
                      {field.required ? (
                        <span className="text-destructive ml-0.5">*</span>
                      ) : null}
                      {isFocused ? (
                        <span className="text-[9px] font-bold text-primary bg-primary/10 px-1.5 py-0.2 rounded">
                          Active
                        </span>
                      ) : null}
                    </span>

                    <div className="flex items-center gap-2">
                      {isMarkdownCapable ? (
                        <div className="flex items-center gap-0.5 bg-muted p-0.5 rounded-md text-[10px]">
                          <button
                            type="button"
                            className={`px-2 py-0.5 rounded font-semibold transition-colors ${
                              !isPreviewMode
                                ? 'bg-background text-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleFieldMode(field.name, 'edit')
                              if (globalPreview) setGlobalPreview(false)
                            }}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className={`px-2 py-0.5 rounded font-semibold transition-colors ${
                              isPreviewMode
                                ? 'bg-primary text-primary-foreground shadow-sm'
                                : 'text-muted-foreground hover:text-foreground'
                            }`}
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleFieldMode(field.name, 'preview')
                            }}
                          >
                            Preview
                          </button>
                        </div>
                      ) : (
                        <span className="text-[10px] font-semibold text-muted-foreground uppercase">
                          {field.field_type}
                        </span>
                      )}
                    </div>
                  </div>

                  {isPreviewMode && isMarkdownCapable ? (
                    <div
                      className="w-full min-h-[72px] rounded-lg border border-input bg-muted/30 p-3 text-xs text-foreground leading-relaxed overflow-x-auto"
                      dangerouslySetInnerHTML={{ __html: parseMarkdownToHtml(val) }}
                    />
                  ) : isMedia ? (
                    <div className="space-y-2">
                      {val ? (
                        <div className="flex items-center gap-2">
                          {fieldType === 'audio' ? (
                            <audio controls src={val} className="h-8 flex-1" />
                          ) : (
                            <img
                              src={val}
                              alt={field.name}
                              className="max-h-24 rounded-lg border border-border"
                            />
                          )}
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() =>
                              setFieldValues((prev) => ({ ...prev, [field.name]: '' }))
                            }
                          >
                            Xóa
                          </Button>
                        </div>
                      ) : null}
                      <input
                        type="file"
                        accept={fieldType === 'audio' ? 'audio/*' : 'image/*'}
                        className="text-xs text-muted-foreground file:mr-2 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-secondary file:text-secondary-foreground hover:file:bg-secondary/80"
                        onChange={(e: ChangeEvent<HTMLInputElement>) => {
                          const file = e.target.files?.[0]
                          if (file) handleMediaUpload(field.name, file)
                        }}
                        disabled={uploadingField === field.name}
                      />
                      {uploadingField === field.name ? (
                        <span className="text-[10px] text-primary font-medium">
                          Đang tải media…
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <textarea
                      data-field-name={field.name}
                      rows={isMarkdownCapable ? 3 : 2}
                      className="w-full rounded-lg border border-input bg-background p-2.5 text-xs text-foreground focus:ring-2 focus:ring-primary focus:outline-none font-mono transition-shadow"
                      value={val}
                      onFocus={() => setActiveFieldName(field.name)}
                      onChange={(e) =>
                        setFieldValues((prev) => ({
                          ...prev,
                          [field.name]: e.target.value,
                        }))
                      }
                    />
                  )}
                </div>
              )
            })
          ) : (
            <p className="text-xs text-muted-foreground italic">
              Không tìm thấy thông tin trường của thẻ này.
            </p>
          )}
        </div>

        <div className="flex items-center justify-between border-t pt-4 mt-4">
          {noteId ? (
            <Button variant="destructive" size="sm" onClick={handleDelete} disabled={saving}>
              Xóa Note
            </Button>
          ) : (
            <div />
          )}
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={onClose} disabled={saving}>
              Hủy
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={saving || Boolean(uploadingField)}
              className="bg-primary font-bold text-primary-foreground"
            >
              {saving ? 'Đang lưu…' : 'Lưu thay đổi'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
