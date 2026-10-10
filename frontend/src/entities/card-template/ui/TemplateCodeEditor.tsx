import '@/shared/config/i18n'
import { useRef, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

export type TemplateEditorTab = 'front' | 'back' | 'css'
export type TemplateCodeEditorProps = {
  title?: string
  headerActions?: ReactNode
  fields: Array<{ id: string; name: string; label?: string }>
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

export function TemplateCodeEditor({ title, headerActions, fields, activeTab, onActiveTabChange, frontHtml, backHtml, sharedCss, onFrontHtmlChange, onBackHtmlChange, onSharedCssChange, footer, readOnly = false }: TemplateCodeEditorProps) {
  const { t } = useTranslation('card_templates')
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const insert = (name: string) => {
    if (readOnly || activeTab === 'css') return
    const textarea = textareaRef.current
    const source = activeTab === 'front' ? frontHtml : backHtml
    const start = textarea?.selectionStart ?? source.length
    const end = textarea?.selectionEnd ?? source.length
    const token = `{{${name}}}`
    const changed = source.slice(0, start) + token + source.slice(end)
    if (activeTab === 'front') onFrontHtmlChange(changed)
    else onBackHtmlChange(changed)
    setMenuOpen(false)
    requestAnimationFrame(() => { textarea?.focus(); textarea?.setSelectionRange(start + token.length, start + token.length) })
  }
  const sources = { front: frontHtml, back: backHtml, css: sharedCss }
  const changes = { front: onFrontHtmlChange, back: onBackHtmlChange, css: onSharedCssChange }
  // The card fills its parent (workspace pane): the textarea takes the remaining height on
  // large screens and keeps a screen-relative height when panes are stacked on mobile.
  return <Card className="p-4 sm:p-5 border border-border/80 shadow-xs flex-1 flex flex-col rounded-2xl bg-card min-w-0 h-full min-h-0">
    <div className="flex items-center justify-between gap-3 mb-3"><h3 className="text-sm font-bold text-foreground">{title ?? t('setup.design')}</h3>{headerActions}</div>
    <Tabs value={activeTab} onValueChange={(value) => onActiveTabChange(value as TemplateEditorTab)} className="flex-1 flex flex-col min-h-0">
      <TabsList className="grid grid-cols-3 w-full h-9 p-1 mb-2 rounded-xl">{(['front', 'back', 'css'] as const).map((tab) => <TabsTrigger key={tab} value={tab} className="text-xs font-semibold py-1 rounded-lg">{t(`setup.${tab}`)}</TabsTrigger>)}</TabsList>
      <div className="mb-3 flex items-center gap-2 min-h-8">
        <DropdownMenu open={menuOpen} onOpenChange={(open) => { setMenuOpen(open); if (open) setSearch('') }}>
          <DropdownMenuTrigger asChild><Button type="button" variant="outline" size="sm" disabled={readOnly || activeTab === 'css' || !fields.length}><span>{t('setup.insert_input')}</span><ChevronDown className="size-3.5" /></Button></DropdownMenuTrigger>
          <DropdownMenuContent className="w-72 max-w-[calc(100vw-2rem)]" onCloseAutoFocus={(event) => { event.preventDefault(); textareaRef.current?.focus() }}>
            <div className="p-1"><Input autoFocus aria-label={t('setup.search_inputs')} placeholder={t('setup.search_inputs')} value={search} onChange={(event) => setSearch(event.target.value)} onKeyDown={(event) => { if (event.key !== 'Escape' && event.key !== 'Tab') event.stopPropagation() }} /></div>
            <div className="max-h-64 overflow-y-auto">{fields.filter((field) => `${field.name} ${field.label ?? ''}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map((field) => <DropdownMenuItem key={field.id} onSelect={() => insert(field.name)} className="flex items-start flex-col gap-0.5 px-3 py-2"><span>{field.label || field.name}</span><code className="text-xs text-muted-foreground">{`{{${field.name}}}`}</code></DropdownMenuItem>)}</div>
          </DropdownMenuContent>
        </DropdownMenu>
        {activeTab === 'css' && <p className="text-xs text-muted-foreground">{t('setup.css_insert_hint')}</p>}
        {!fields.length && activeTab !== 'css' && <p className="text-xs text-muted-foreground">{t('setup.no_inputs')}</p>}
      </div>
      {(['front', 'back', 'css'] as const).map((tab) => <TabsContent key={tab} value={tab} className="flex-1 mt-0 min-h-0 flex flex-col"><textarea ref={(element) => { if (activeTab === tab) textareaRef.current = element }} aria-label={t(`setup.${tab}`)} value={sources[tab]} onChange={(event) => changes[tab](event.target.value)} readOnly={readOnly} className="w-full font-mono text-xs sm:text-sm p-3 rounded-xl border border-input bg-background focus:outline-none focus:ring-2 focus:ring-primary/20 h-[55svh] min-h-64 resize-y lg:h-auto lg:min-h-0 lg:flex-1 lg:resize-none overflow-auto overscroll-contain" placeholder={tab === 'css' ? '.card { text-align: center; }' : '<h2>{{Word}}</h2>'} /></TabsContent>)}
    </Tabs>
    {footer && <div className="pt-3 flex justify-start border-t mt-3 shrink-0">{footer}</div>}
  </Card>
}
