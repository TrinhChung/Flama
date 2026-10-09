import { useRef, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export type TemplateEditorTab = 'front' | 'back' | 'css'

export type TemplateCodeEditorProps = {
  title?: string
  headerActions?: ReactNode
  fields: Array<{ id: string; name: string }>
  activeTab: TemplateEditorTab
  onActiveTabChange: (tab: TemplateEditorTab) => void
  frontHtml: string
  backHtml: string
  sharedCss: string
  onFrontHtmlChange: (value: string) => void
  onBackHtmlChange: (value: string) => void
  onSharedCssChange: (value: string) => void
  footer?: ReactNode
  readOnly?: boolean
}

export function TemplateCodeEditor({
  title = 'Trình Soạn Thảo Template',
  headerActions,
  fields,
  activeTab,
  onActiveTabChange,
  frontHtml,
  backHtml,
  sharedCss,
  onFrontHtmlChange,
  onBackHtmlChange,
  onSharedCssChange,
  footer,
  readOnly = false,
}: TemplateCodeEditorProps) {
  const activeTextareaRef = useRef<HTMLTextAreaElement | null>(null)

  const insertPlaceholder = (fieldName: string) => {
    if (readOnly) return
    const placeholder = `{{${fieldName}}}`
    const textarea = activeTextareaRef.current

    if (activeTab === 'front') {
      if (textarea) {
        const start = textarea.selectionStart || 0
        const end = textarea.selectionEnd || 0
        onFrontHtmlChange(frontHtml.slice(0, start) + placeholder + frontHtml.slice(end))
      } else {
        onFrontHtmlChange(frontHtml + placeholder)
      }
    } else if (activeTab === 'back') {
      if (textarea) {
        const start = textarea.selectionStart || 0
        const end = textarea.selectionEnd || 0
        onBackHtmlChange(backHtml.slice(0, start) + placeholder + backHtml.slice(end))
      } else {
        onBackHtmlChange(backHtml + placeholder)
      }
    } else {
      onSharedCssChange(sharedCss + `/* ${placeholder} */`)
    }
  }

  return (
    <Card className="p-4 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl bg-card">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 mb-3">
        <h3 className="text-sm font-bold text-foreground">{title}</h3>
        <div className="flex items-center gap-1.5 sm:gap-2 w-full sm:w-auto overflow-x-auto pb-0.5">
          {headerActions}
        </div>
      </div>

      {/* Placeholder Toolbar with Horizontal Touch Scroll & Wrap */}
      <div className="mb-3 space-y-1.5">
        <div className="flex items-center justify-between text-xs font-semibold text-muted-foreground">
          <span>Chèn trường dữ liệu (Placeholders):</span>
          <span className="text-[10px] font-normal sm:hidden text-muted-foreground">(Chạm để chèn)</span>
        </div>
        <div
          className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none touch-pan-x overscroll-x-contain sm:flex-wrap"
          style={{ WebkitOverflowScrolling: 'touch' }}
        >
          {!readOnly &&
            fields.map((field) => (
              <Button
                key={field.id}
                type="button"
                variant="outline"
                size="sm"
                onClick={() => insertPlaceholder(field.name)}
                className="shrink-0 h-7 px-2.5 text-xs font-mono text-foreground hover:bg-primary/10 hover:border-primary/40 hover:text-primary transition-all cursor-pointer rounded-lg border-border/80"
              >
                {`{{${field.name}}}`}
              </Button>
            ))}
          {!readOnly && !fields.length ? (
            <span className="text-xs text-muted-foreground italic">Chưa có trường nào</span>
          ) : null}
        </div>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(val) => onActiveTabChange(val as TemplateEditorTab)}
        className="flex-1 flex flex-col"
      >
        <TabsList className="grid grid-cols-3 w-full h-9 p-1 mb-2 rounded-xl">
          <TabsTrigger value="front" className="text-xs font-semibold py-1 rounded-lg">
            Front HTML
          </TabsTrigger>
          <TabsTrigger value="back" className="text-xs font-semibold py-1 rounded-lg">
            Back HTML
          </TabsTrigger>
          <TabsTrigger value="css" className="text-xs font-semibold py-1 rounded-lg">
            Shared CSS
          </TabsTrigger>
        </TabsList>

        <TabsContent value="front" className="flex-1 mt-0">
          <textarea
            ref={(el) => {
              if (activeTab === 'front') activeTextareaRef.current = el
            }}
            value={frontHtml}
            onChange={(e) => onFrontHtmlChange(e.target.value)}
            className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
            placeholder="<h2>{{Word}}</h2>"
            {...(readOnly ? { readOnly: true } : {})}
          />
        </TabsContent>

        <TabsContent value="back" className="flex-1 mt-0">
          <textarea
            ref={(el) => {
              if (activeTab === 'back') activeTextareaRef.current = el
            }}
            value={backHtml}
            onChange={(e) => onBackHtmlChange(e.target.value)}
            className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
            placeholder="<h2>{{Word}}</h2><hr/><p>{{Meaning}}</p>"
            {...(readOnly ? { readOnly: true } : {})}
          />
        </TabsContent>

        <TabsContent value="css" className="flex-1 mt-0">
          <textarea
            ref={(el) => {
              if (activeTab === 'css') activeTextareaRef.current = el
            }}
            value={sharedCss}
            onChange={(e) => onSharedCssChange(e.target.value)}
            className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 min-h-[12rem] sm:min-h-[20rem] h-[clamp(14rem,40vh,30rem)] resize-y overflow-auto overscroll-contain"
            placeholder=".card { text-align: center; color: #333; }"
            {...(readOnly ? { readOnly: true } : {})}
          />
        </TabsContent>
      </Tabs>

      <div className="pt-3 flex justify-start border-t mt-3">
        {footer}
      </div>
    </Card>
  )
}
