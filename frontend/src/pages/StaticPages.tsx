import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Copy,
  FileText,
  HelpCircle,
  Info,
  Link2,
  List,
  Printer,
  Scale,
  Shield,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet'
import { useTranslation } from 'react-i18next'
import '@/shared/config/i18n'
import {
  getLegalDocument,
  legalDocuments,
  type LegalDocument,
  type StatutoryCallout,
} from '@/data/legalDocumentsData'
import { cn } from '@/lib/utils'
import { Page } from '@/shared/components/Page'

// CRITICAL REQUIREMENT: PRESERVE ALL RE-EXPORTS
export { SupportPage } from '@/features/support/pages/SupportPage'
export { TtsKeyGuidePage } from '@/features/support/pages/TtsKeyGuidePage'
export { FlamaAudioGuidePage } from '@/features/support/pages/FlamaAudioGuidePage'

const LEGAL_NAV_ITEMS = [
  { id: 'terms', path: '/terms', label: 'Điều khoản dịch vụ' },
  { id: 'privacy', path: '/privacy', label: 'Chính sách bảo mật' },
  {
    id: 'marketplace-guidelines',
    path: '/marketplace-guidelines',
    label: 'Quy chế Marketplace',
  },
  {
    id: 'community-guidelines',
    path: '/community-guidelines',
    label: 'Chuẩn mực cộng đồng',
  },
  { id: 'cookies', path: '/cookies', label: 'Chính sách cookie' },
]

function CalloutBlock({ callout }: { callout: StatutoryCallout }) {
  const isWarning = callout.type === 'warning'
  const isStatutory = callout.type === 'statutory'

  return (
    <aside
      aria-label={callout.label}
      className={cn(
        'my-4 rounded-r-lg border-l-2 py-2.5 pl-4 text-sm transition-colors',
        isWarning
          ? 'border-amber-500/80 bg-amber-500/5 text-amber-950 dark:text-amber-200'
          : isStatutory
            ? 'border-primary/80 bg-primary/5 text-foreground'
            : 'border-sky-500/80 bg-sky-500/5 text-foreground',
      )}
    >
      <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-primary">
        {isWarning ? (
          <AlertTriangle className="size-3.5 shrink-0 text-amber-500" />
        ) : isStatutory ? (
          <Scale className="size-3.5 shrink-0 text-primary" />
        ) : (
          <Info className="size-3.5 shrink-0 text-sky-500" />
        )}
        <span>{callout.label}</span>
      </div>
      <p className="text-xs leading-relaxed font-normal text-foreground/90 sm:text-sm">
        {callout.text}
      </p>
    </aside>
  )
}

function TableOfContentsNav({
  documentData,
  activeClauseId,
  onSelectClause,
}: {
  documentData: LegalDocument
  activeClauseId: string
  onSelectClause: (id: string) => void
}) {
  const { t } = useTranslation('legal')
  return (
    <nav
      className="space-y-1.5 text-xs"
      aria-label={t('toc.aria_label', 'Mục lục điều khoản')}
    >
      {documentData.clauses.map((clause) => {
        const isClauseActive =
          activeClauseId === clause.id ||
          clause.subClauses?.some((sub) => sub.id === activeClauseId)

        return (
          <div key={clause.id} className="space-y-1">
            <button
              type="button"
              onClick={() => onSelectClause(clause.id)}
              className={cn(
                'flex w-full items-start gap-1.5 rounded-md px-2.5 py-1.5 text-left font-medium transition-all',
                isClauseActive
                  ? 'translate-x-0.5 bg-primary/10 font-semibold text-primary'
                  : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground',
              )}
            >
              <span className="shrink-0 font-semibold tabular-nums text-primary/80">
                {clause.clauseNumber}.
              </span>
              <span className="line-clamp-2 leading-tight">{clause.title}</span>
            </button>

            {clause.subClauses && clause.subClauses.length > 0 && (
              <div className="my-0.5 space-y-0.5 border-l border-border/40 pl-2 ml-3">
                {clause.subClauses.map((sub) => {
                  const isSubActive = activeClauseId === sub.id
                  return (
                    <button
                      key={sub.id}
                      type="button"
                      onClick={() => onSelectClause(sub.id)}
                      className={cn(
                        'flex w-full items-start gap-1.5 rounded px-2 py-1 text-left text-[11px] transition-colors',
                        isSubActive
                          ? 'bg-primary/15 font-medium text-primary'
                          : 'text-muted-foreground hover:bg-muted/50 hover:text-foreground',
                      )}
                    >
                      <span className="shrink-0 font-medium tabular-nums text-primary/70">
                        {sub.clauseNumber}
                      </span>
                      <span className="line-clamp-1 leading-snug">{sub.title}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )
}

function LegalDocumentViewer({
  documentData: initialDocumentData,
  documentId,
}: {
  documentData?: LegalDocument
  documentId?: string
}) {
  const { i18n, t } = useTranslation('legal')
  const locale = (i18n.language?.startsWith('en') ? 'en' : 'vi') as 'vi' | 'en'
  const docId = documentId || initialDocumentData?.id || 'terms'
  const documentData =
    getLegalDocument(docId, locale) || initialDocumentData || legalDocuments.terms

  const [activeClauseId, setActiveClauseId] = useState<string>(
    documentData.clauses[0]?.id || '',
  )
  const [copied, setCopied] = useState(false)
  const [mobileTocOpen, setMobileTocOpen] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  // Scrollspy via IntersectionObserver
  useEffect(() => {
    const headings = Array.from(
      document.querySelectorAll<HTMLElement>('[data-clause-id]'),
    )
    if (!headings.length) return

    observerRef.current?.disconnect()

    const observer = new IntersectionObserver(
      (entries) => {
        const intersecting = entries.filter((entry) => entry.isIntersecting)
        if (intersecting.length > 0) {
          // Select topmost intersecting element
          const topmost = intersecting.reduce((prev, curr) =>
            prev.boundingClientRect.top < curr.boundingClientRect.top
              ? prev
              : curr,
          )
          const id = topmost.target.getAttribute('data-clause-id')
          if (id) {
            setActiveClauseId(id)
          }
        }
      },
      {
        rootMargin: '-80px 0px -55% 0px',
        threshold: [0, 0.2, 0.5, 1],
      },
    )

    headings.forEach((heading) => observer.observe(heading))
    observerRef.current = observer

    return () => observer.disconnect()
  }, [documentData])

  // Scroll to hash target on mount/hash change
  useEffect(() => {
    if (window.location.hash) {
      const targetId = window.location.hash.slice(1)
      const el = document.getElementById(targetId)
      if (el) {
        const timeout = setTimeout(() => {
          el.scrollIntoView({ behavior: 'smooth' })
          setActiveClauseId(targetId)
        }, 120)
        return () => clearTimeout(timeout)
      }
    }
  }, [documentData.id])

  const scrollToClause = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' })
      window.history.replaceState(null, '', `#${id}`)
      setActiveClauseId(id)
    }
    setMobileTocOpen(false)
  }

  const handleCopyAnchor = (
    id: string,
    clauseTitle: string,
    e?: React.MouseEvent,
  ) => {
    e?.stopPropagation()
    const url = `${window.location.origin}${window.location.pathname}#${id}`
    navigator.clipboard
      .writeText(url)
      .then(() => {
        window.history.replaceState(null, '', `#${id}`)
        setActiveClauseId(id)
        toast.success(
          t('actions.copied_clause_toast', {
            title: clauseTitle,
            defaultValue: `Đã sao chép liên kết: ${clauseTitle}`,
          }),
        )
      })
      .catch(() => {
        window.history.replaceState(null, '', `#${id}`)
        setActiveClauseId(id)
        toast.success(
          t('actions.selected_clause_toast', {
            title: clauseTitle,
            defaultValue: `Đã chọn: ${clauseTitle}`,
          }),
        )
      })
  }

  const handleCopyDocumentLink = () => {
    const url = `${window.location.origin}${window.location.pathname}`
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true)
      toast.success(t('actions.copied_toast', 'Đã sao chép liên kết văn bản!'))
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handlePrint = () => {
    window.print()
  }

  const navItems = LEGAL_NAV_ITEMS.map((item) => ({
    ...item,
    label: t(
      item.id === 'marketplace-guidelines'
        ? 'nav.marketplace'
        : item.id === 'community-guidelines'
          ? 'nav.community'
          : `nav.${item.id}`,
      item.label,
    ),
  }))

  return (
    <Page className="max-w-6xl pb-20 print:m-0 print:max-w-none print:p-0">
      {/* Comprehensive print style overrides */}
      <style>{`
        @media print {
          body, #root, main, article {
            background: #ffffff !important;
            color: #000000 !important;
          }
          .print-hidden, nav, aside, button, [role="button"] {
            display: none !important;
          }
          .legal-clause {
            break-inside: avoid !important;
            page-break-inside: avoid !important;
            margin-bottom: 2rem !important;
          }
          h1, h2, h3, h4 {
            break-after: avoid !important;
            page-break-after: avoid !important;
            color: #000000 !important;
          }
          p, li {
            color: #111111 !important;
          }
        }
      `}</style>

      {/* Top Document Switcher Tabs */}
      <nav
        aria-label={t('nav.aria_label', 'Chuyển đổi văn bản pháp lý')}
        className="no-scrollbar mb-6 flex items-center gap-1.5 overflow-x-auto border-b border-border/40 pb-2.5 print:hidden"
      >
        {navItems.map((item) => {
          const isCurrent = item.id === documentData.id
          return (
            <Link
              key={item.id}
              to={item.path}
              className={cn(
                'inline-flex items-center whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                isCurrent
                  ? 'bg-primary text-primary-foreground font-semibold shadow-2xs'
                  : 'text-muted-foreground hover:bg-muted/70 hover:text-foreground',
              )}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Document Header & Metadata Bar */}
      <header className="space-y-4 border-b border-border/60 pb-6 pt-1">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge
              variant="outline"
              className="gap-1.5 border-primary/30 bg-primary/5 px-2.5 py-0.5 text-xs font-medium text-primary"
            >
              <Shield className="size-3" /> {documentData.officialBadge}
            </Badge>
            <Badge variant="secondary" className="px-2 py-0.5 text-xs">
              {t('metadata.version', {
                version: documentData.version,
                defaultValue: `Phiên bản ${documentData.version}`,
              })}
            </Badge>
          </div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground print:hidden">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={handleCopyDocumentLink}
              title={t('actions.copy_document_title', 'Sao chép liên kết tài liệu')}
            >
              {copied ? (
                <Check className="size-3.5 text-emerald-600" />
              ) : (
                <Copy className="size-3.5" />
              )}
              <span className="hidden sm:inline">
                {t('actions.copy_document', 'Sao chép')}
              </span>
            </Button>
            <span className="text-border">·</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
              onClick={handlePrint}
              title={t('actions.print_pdf_title', 'In văn bản hoặc xuất PDF')}
            >
              <Printer className="size-3.5" />
              <span className="hidden sm:inline">
                {t('actions.print_pdf', 'In PDF')}
              </span>
            </Button>
          </div>
        </div>

        <h1 className="text-2xl font-extrabold tracking-tight text-foreground sm:text-3xl lg:text-4xl font-heading">
          {documentData.title}
        </h1>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            {t('metadata.effective_date', 'Ngày hiệu lực')}:{' '}
            <strong className="font-medium text-foreground">
              {documentData.effectiveDate}
            </strong>
          </span>
          <span className="text-border">·</span>
          <span>
            {t('metadata.last_updated', 'Cập nhật lần cuối')}:{' '}
            <strong className="font-medium text-foreground">
              {documentData.lastUpdated}
            </strong>
          </span>
          <span className="text-border">·</span>
          <span>
            {t('metadata.read_time', {
              minutes: documentData.readTimeMinutes,
              defaultValue: `~${documentData.readTimeMinutes} phút đọc tiêu chuẩn`,
            })}
          </span>
        </div>

        {/* Executive Summary Editorial Callout (Clean paper quote style, zero box-in-box) */}
        <div className="my-4 rounded-r-lg border-l-2 border-primary/50 bg-muted/20 py-2.5 pl-4 pr-3">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            <Info className="size-3.5 text-primary" />{' '}
            {t('metadata.executive_summary', 'Tóm tắt điều hành')}
          </div>
          <p className="text-sm leading-relaxed font-medium text-foreground/90 sm:text-base">
            {documentData.executiveSummary}
          </p>
        </div>
      </header>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 gap-8 pt-6 lg:grid-cols-12 lg:gap-12">
        {/* Left Column: Continuous Prose Flow (Reading measure max-w-3xl, zero UI-ification) */}
        <article className="max-w-3xl space-y-12 lg:col-span-8 print:max-w-none print:col-span-12">
          {documentData.clauses.map((clause) => (
            <section
              key={clause.id}
              id={clause.id}
              data-clause-id={clause.id}
              className="legal-clause scroll-mt-24 space-y-4"
            >
              {/* Clause Heading (H2) with Hover Anchor Copy */}
              <div className="group flex items-start justify-between gap-3 pt-2">
                <h2 className="text-xl font-bold tracking-tight text-foreground sm:text-2xl">
                  <span className="mr-2 font-semibold tabular-nums text-primary">
                    {clause.clauseNumber}.
                  </span>
                  {clause.title}
                </h2>
                <button
                  type="button"
                  onClick={(e) =>
                    handleCopyAnchor(
                      clause.id,
                      `${clause.clauseNumber} - ${clause.title}`,
                      e,
                    )
                  }
                  className="shrink-0 rounded-md p-1.5 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-primary focus:opacity-100 group-hover:opacity-100 print:hidden"
                  title={t('actions.copy_anchor', 'Sao chép liên kết điều khoản')}
                  aria-label={t('actions.copy_anchor_aria', {
                    number: clause.clauseNumber,
                    defaultValue: `Sao chép liên kết ${clause.clauseNumber}`,
                  })}
                >
                  <Link2 className="size-4" />
                </button>
              </div>

              {/* Clause Summary */}
              {clause.summary && (
                <p className="text-sm font-medium italic text-foreground/80 sm:text-base">
                  {clause.summary}
                </p>
              )}

              {/* Clause Opening Paragraphs */}
              {clause.content?.map((paragraph, pIdx) => (
                <p
                  key={pIdx}
                  className="text-sm leading-relaxed font-normal text-foreground/90 sm:text-base"
                >
                  {paragraph}
                </p>
              ))}

              {/* Bullets if any */}
              {clause.bullets && clause.bullets.length > 0 && (
                <ul className="space-y-2 pl-5 list-disc text-sm leading-relaxed text-foreground/85 marker:text-primary sm:text-base">
                  {clause.bullets.map((bullet, bIdx) => (
                    <li key={bIdx} className="pl-1">
                      {bullet}
                    </li>
                  ))}
                </ul>
              )}

              {/* Statutory Callout */}
              {clause.callout && <CalloutBlock callout={clause.callout} />}

              {/* Subclauses (H3) */}
              {clause.subClauses && clause.subClauses.length > 0 && (
                <div className="space-y-6 pt-2">
                  {clause.subClauses.map((subClause) => (
                    <div
                      key={subClause.id}
                      id={subClause.id}
                      data-clause-id={subClause.id}
                      className="scroll-mt-24 space-y-2.5 pt-2"
                    >
                      <div className="group/sub flex items-start justify-between gap-2">
                        <h3 className="text-base font-semibold tracking-tight text-foreground sm:text-lg">
                          <span className="mr-2 font-medium tabular-nums text-primary/90">
                            {subClause.clauseNumber}
                          </span>
                          {subClause.title}
                        </h3>
                        <button
                          type="button"
                          onClick={(e) =>
                            handleCopyAnchor(
                              subClause.id,
                              `${subClause.clauseNumber} - ${subClause.title}`,
                              e,
                            )
                          }
                          className="shrink-0 rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-primary focus:opacity-100 group-hover/sub:opacity-100 print:hidden"
                          title={t('actions.copy_subclause', 'Sao chép liên kết tiểu mục')}
                          aria-label={t('actions.copy_anchor_aria', {
                            number: subClause.clauseNumber,
                            defaultValue: `Sao chép liên kết ${subClause.clauseNumber}`,
                          })}
                        >
                          <Link2 className="size-3.5" />
                        </button>
                      </div>

                      {subClause.content.map((subParagraph, spIdx) => (
                        <p
                          key={spIdx}
                          className="text-sm leading-relaxed font-normal text-foreground/90 sm:text-base"
                        >
                          {subParagraph}
                        </p>
                      ))}

                      {subClause.bullets && subClause.bullets.length > 0 && (
                        <ul className="space-y-1.5 pl-5 list-disc text-sm leading-relaxed text-foreground/85 marker:text-primary/70 sm:text-base">
                          {subClause.bullets.map((bullet, sbIdx) => (
                            <li key={sbIdx} className="pl-1">
                              {bullet}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </section>
          ))}

          {/* Editorial Support & Dispute Resolution Note */}
          <footer className="mt-14 space-y-3 border-t border-border/60 pt-8 print:hidden">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <HelpCircle className="size-4 text-primary" />{' '}
              {t(
                'support.title',
                'Bạn có thắc mắc hoặc cần giải quyết tranh chấp pháp lý?',
              )}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground sm:text-sm">
              {t(
                'support.body',
                'Nếu bạn cần làm rõ bất kỳ điều khoản nào, báo cáo vi phạm bản quyền theo quy trình Notice & Takedown, hoặc có yêu cầu liên quan đến quyền riêng tư và dữ liệu cá nhân theo Nghị định 13/2023/NĐ-CP, đội ngũ Pháp chế Flama luôn sẵn sàng tiếp nhận và phản hồi trong 24–48 giờ.',
              )}
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button asChild size="sm" variant="outline" className="gap-1.5 text-xs">
                <Link to="/support">
                  {t('support.button', 'Gửi yêu cầu hỗ trợ')}{' '}
                  <ChevronRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          </footer>
        </article>

        {/* Right Column: Sticky Table of Contents (Desktop Only) */}
        <aside className="hidden lg:col-span-4 lg:block print:hidden">
          <div className="sticky top-20 flex max-h-[calc(100vh-6rem)] flex-col space-y-4">
            {/* Table of Contents Container */}
            <div className="flex max-h-[calc(100vh-14rem)] flex-col rounded-xl border border-border/60 bg-card/40 p-4 shadow-2xs backdrop-blur-xs">
              <div className="mb-3 flex items-center justify-between gap-2 border-b border-border/40 pb-2.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <List className="size-3.5 text-primary" /> {t('toc.title', 'Mục lục văn bản')}
                </span>
                <span className="text-[11px] font-normal lowercase">
                  {t('toc.clause_count', {
                    count: documentData.clauses.length,
                    defaultValue: `${documentData.clauses.length} điều khoản`,
                  })}
                </span>
              </div>

              <ScrollArea className="flex-1 pr-2">
                <TableOfContentsNav
                  documentData={documentData}
                  activeClauseId={activeClauseId}
                  onSelectClause={scrollToClause}
                />
              </ScrollArea>
            </div>

            {/* Related Policies Nav Box */}
            <div className="rounded-xl border border-border/60 bg-card/30 p-3.5 space-y-2">
              <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                {t('toc.related_policies', 'Văn bản pháp lý liên quan')}
              </div>
              <div className="space-y-1">
                {navItems
                  .filter((item) => item.id !== documentData.id)
                  .map((link) => (
                    <Link
                      key={link.id}
                      to={link.path}
                      className="flex items-center justify-between rounded-lg px-2 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted/50 hover:text-primary"
                    >
                      <span className="flex items-center gap-2">
                        <FileText className="size-3.5 text-primary/70" /> {link.label}
                      </span>
                      <ChevronRight className="size-3 opacity-60" />
                    </Link>
                  ))}
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* Floating Mobile TOC Drawer Button */}
      <div className="fixed bottom-6 right-6 z-40 lg:hidden print:hidden">
        <Sheet open={mobileTocOpen} onOpenChange={setMobileTocOpen}>
          <SheetTrigger asChild>
            <Button
              variant="default"
              size="sm"
              className="gap-2 rounded-full border border-primary/20 px-4 py-2.5 text-xs font-semibold shadow-lg shadow-primary/25"
            >
              <List className="size-4" />
              <span>
                {t('toc.mobile_button', {
                  count: documentData.clauses.length,
                  defaultValue: `Mục lục (${documentData.clauses.length} điều)`,
                })}
              </span>
            </Button>
          </SheetTrigger>
          <SheetContent
            side="right"
            className="flex w-[85vw] max-w-sm flex-col p-0"
          >
            <SheetHeader className="border-b border-border/40 p-4">
              <SheetTitle className="flex items-center gap-2 text-sm font-bold">
                <List className="size-4 text-primary" /> {t('toc.title', 'Mục lục văn bản')}
              </SheetTitle>
            </SheetHeader>
            <ScrollArea className="flex-1 p-4">
              <TableOfContentsNav
                documentData={documentData}
                activeClauseId={activeClauseId}
                onSelectClause={scrollToClause}
              />
            </ScrollArea>
          </SheetContent>
        </Sheet>
      </div>
    </Page>
  )
}

export function TermsPage() {
  return (
    <LegalDocumentViewer
      documentId="terms"
      documentData={legalDocuments.terms}
    />
  )
}

export function PrivacyPage() {
  return (
    <LegalDocumentViewer
      documentId="privacy"
      documentData={legalDocuments.privacy}
    />
  )
}

export function MarketplaceGuidelinesPage() {
  return (
    <LegalDocumentViewer
      documentId="marketplace-guidelines"
      documentData={legalDocuments['marketplace-guidelines']}
    />
  )
}

export function CommunityGuidelinesPage() {
  return (
    <LegalDocumentViewer
      documentId="community-guidelines"
      documentData={legalDocuments['community-guidelines']}
    />
  )
}

export function CookiesPage() {
  return (
    <LegalDocumentViewer
      documentId="cookies"
      documentData={legalDocuments.cookies}
    />
  )
}
