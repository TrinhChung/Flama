import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Check,
  ChevronRight,
  Copy,
  FileText,
  HelpCircle,
  Info,
  List,
  Printer,
  Shield,
} from 'lucide-react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Page } from '@/shared/components/Page'

export { SupportPage } from '@/features/support/pages/SupportPage'
export { TtsKeyGuidePage } from '@/features/support/pages/TtsKeyGuidePage'
export { FlamaAudioGuidePage } from '@/features/support/pages/FlamaAudioGuidePage'

type LegalSection = {
  title: string
  paragraphs?: string[]
  items?: string[]
}

const LEGAL_NAV_LINKS = [
  { path: '/terms', label: 'Điều khoản sử dụng' },
  { path: '/privacy', label: 'Chính sách bảo mật' },
  { path: '/cookies', label: 'Chính sách cookie' },
]

function LegalPage({
  title,
  summary,
  sections,
}: {
  title: string
  summary: string
  sections: LegalSection[]
}) {
  const [activeSection, setActiveSection] = useState<number>(0)
  const [copied, setCopied] = useState(false)

  const handleCopyLink = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopied(true)
      toast.success('Đã sao chép liên kết trang!')
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const handlePrint = () => {
    window.print()
  }

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY + 140
      sections.forEach((_, idx) => {
        const el = document.getElementById(`legal-sec-${idx}`)
        if (el) {
          const top = el.offsetTop
          const height = el.offsetHeight
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(idx)
          }
        }
      })
    }

    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [sections])

  return (
    <Page className="max-w-5xl">
      {/* Editorial Header & Meta Bar */}
      <header className="space-y-4 border-b border-border/70 pb-6 pt-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Badge variant="outline" className="gap-1.5 font-medium text-xs px-2.5 py-0.5 border-primary/30 text-primary bg-primary/5">
            <Shield className="size-3" /> Văn bản pháp lý Flama
          </Badge>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>Cập nhật lần cuối: <strong className="font-semibold text-foreground">26/07/2026</strong></span>
            <span className="text-border">·</span>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground gap-1"
              onClick={handleCopyLink}
              title="Sao chép liên kết"
            >
              {copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}
              <span className="hidden sm:inline">Sao chép</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground gap-1"
              onClick={handlePrint}
              title="In tài liệu"
            >
              <Printer className="size-3.5" />
              <span className="hidden sm:inline">In</span>
            </Button>
          </div>
        </div>

        <h1 className="text-3xl font-extrabold tracking-tight text-foreground sm:text-4xl">
          {title}
        </h1>

        {/* Editorial Summary Callout (Clean subtle border & warm backdrop) */}
        <div className="rounded-xl border border-border/80 bg-muted/30 px-4 py-3.5 sm:px-5 sm:py-4">
          <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            <Info className="size-3.5" /> Tóm tắt cốt lõi
          </div>
          <p className="text-sm sm:text-base leading-relaxed text-foreground/90 font-medium">
            {summary}
          </p>
        </div>
      </header>

      {/* Main Two-Column Editorial Layout */}
      <div className="grid grid-cols-1 gap-8 pt-4 lg:grid-cols-12 lg:gap-12">
        {/* Left Column: Continuous Prose Flow (No nested cards) */}
        <article className="lg:col-span-8 space-y-10">
          {sections.map((section, idx) => (
            <section
              key={section.title}
              id={`legal-sec-${idx}`}
              className="scroll-mt-24 space-y-3.5"
            >
              <h2 className="text-xl font-bold tracking-tight text-foreground border-b border-border/40 pb-2">
                {section.title}
              </h2>

              {section.paragraphs?.map((paragraph, pIdx) => (
                <p key={pIdx} className="text-sm sm:text-base leading-relaxed text-muted-foreground">
                  {paragraph}
                </p>
              ))}

              {section.items?.length ? (
                <ul className="space-y-2.5 pl-5 list-disc text-sm sm:text-base leading-relaxed text-muted-foreground marker:text-primary">
                  {section.items.map((item, itemIdx) => (
                    <li key={itemIdx} className="pl-1">
                      {item}
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}

          {/* Editorial Footer Note & Support Action */}
          <div className="rounded-2xl border border-border/80 bg-muted/20 p-5 sm:p-6 space-y-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <HelpCircle className="size-4 text-primary" /> Bạn có thắc mắc về chính sách này?
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
              Nếu bạn cần làm rõ bất kỳ điều khoản nào hoặc có yêu cầu liên quan đến quyền riêng tư và dữ liệu cá nhân, đội ngũ Flama luôn sẵn sàng hỗ trợ.
            </p>
            <div className="pt-1">
              <Button asChild size="sm" variant="outline" className="text-xs gap-1.5">
                <Link to="/support">
                  Gửi yêu cầu hỗ trợ <ChevronRight className="size-3.5" />
                </Link>
              </Button>
            </div>
          </div>
        </article>

        {/* Right Column: Sticky Table of Contents (Desktop Only) */}
        <aside className="hidden lg:col-span-4 lg:block">
          <div className="sticky top-20 space-y-6">
            {/* Table of Contents Box */}
            <div className="rounded-xl border border-border/60 bg-card/50 p-4 shadow-2xs backdrop-blur-xs">
              <div className="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                <List className="size-3.5 text-primary" /> Mục lục điều khoản
              </div>
              <nav className="space-y-1">
                {sections.map((section, idx) => {
                  const isActive = activeSection === idx
                  return (
                    <a
                      key={section.title}
                      href={`#legal-sec-${idx}`}
                      onClick={(e) => {
                        e.preventDefault()
                        document.getElementById(`legal-sec-${idx}`)?.scrollIntoView({ behavior: 'smooth' })
                        setActiveSection(idx)
                      }}
                      className={`block rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all ${
                        isActive
                          ? 'bg-primary/10 text-primary font-semibold translate-x-1'
                          : 'text-muted-foreground hover:bg-muted/60 hover:text-foreground'
                      }`}
                    >
                      {section.title}
                    </a>
                  )
                })}
              </nav>
            </div>

            {/* Related Policies Box */}
            <div className="rounded-xl border border-border/60 bg-card/30 p-4 space-y-2.5">
              <div className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Chính sách liên quan
              </div>
              <div className="space-y-1.5">
                {LEGAL_NAV_LINKS.map((link) => (
                  <Link
                    key={link.path}
                    to={link.path}
                    className="flex items-center justify-between rounded-lg px-2 py-1.5 text-xs text-muted-foreground hover:bg-muted/50 hover:text-primary transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <FileText className="size-3.5" /> {link.label}
                    </span>
                    <ChevronRight className="size-3 opacity-60" />
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </Page>
  )
}

export function TermsPage() {
  return (
    <LegalPage
      title="Điều khoản sử dụng"
      summary="Các nguyên tắc sử dụng tài khoản, học liệu và marketplace Flama."
      sections={[
        {
          title: '1. Sự đồng ý và phạm vi dịch vụ',
          paragraphs: ['Khi sử dụng Flama, bạn đồng ý tuân thủ các điều khoản này. Flama cung cấp flashcard, quản lý từ vựng và lịch học lặp lại ngắt quãng.'],
        },
        {
          title: '2. Quyền sở hữu nội dung',
          paragraphs: ['Bạn sở hữu học liệu do mình tạo. Bạn cho phép Flama lưu trữ, xử lý, hiển thị, sao lưu và khôi phục nội dung đó để vận hành dịch vụ.'],
          items: ['Không sao chép hoặc phân phối trái phép tài sản, thương hiệu và mã nguồn Flama.', 'Không đăng nội dung vi phạm bản quyền hoặc quyền riêng tư của người khác.'],
        },
        {
          title: '3. Hành vi bị cấm',
          items: ['Tấn công, phá hoại, khai thác lỗ hổng hoặc đưa mã độc vào hệ thống.', 'Dùng bot, crawler hoặc tải dữ liệu hàng loạt trái phép.', 'Gian lận, giả mạo, spam, quấy rối hoặc sử dụng dịch vụ cho mục đích bất hợp pháp.'],
        },
        {
          title: '4. Tài khoản và chấm dứt dịch vụ',
          paragraphs: ['Bạn chịu trách nhiệm bảo vệ mật khẩu và hoạt động trên tài khoản. Flama có thể đình chỉ tài khoản vi phạm; bạn có thể yêu cầu xóa tài khoản và dữ liệu theo chính sách hiện hành.'],
        },
        {
          title: '5. Giới hạn trách nhiệm và thay đổi',
          paragraphs: ['Flama không chịu trách nhiệm cho thiệt hại gián tiếp, lỗi thiết bị hoặc nội dung của người dùng khác. Điều khoản có thể được cập nhật và ngày cập nhật sẽ được công bố trên trang này.'],
        },
      ]}
    />
  )
}

export function PrivacyPage() {
  return (
    <LegalPage
      title="Chính sách bảo mật"
      summary="Cách Flama thu thập, sử dụng và bảo vệ dữ liệu của người học."
      sections={[
        {
          title: '1. Dữ liệu được thu thập',
          items: ['Thông tin tài khoản như email, tên đăng nhập và mật khẩu đã băm.', 'Học liệu, tiến độ, lịch sử ôn tập và lựa chọn cấu hình.', 'Thông tin kỹ thuật cần thiết cho bảo mật và vận hành dịch vụ.'],
        },
        {
          title: '2. Mục đích sử dụng',
          items: ['Cung cấp, đồng bộ và cải thiện trải nghiệm học tập.', 'Bảo vệ tài khoản, phát hiện lạm dụng và hỗ trợ người dùng.', 'Đáp ứng nghĩa vụ pháp lý hợp lệ.'],
        },
        {
          title: '3. Chia sẻ và bảo vệ dữ liệu',
          paragraphs: ['Flama không bán dữ liệu người dùng. Dữ liệu chỉ được chia sẻ khi có sự đồng ý, yêu cầu pháp lý hợp lệ hoặc với nhà cung cấp cần thiết để vận hành dịch vụ theo nghĩa vụ bảo mật.'],
        },
        {
          title: '4. Quyền và thời gian lưu giữ',
          paragraphs: ['Bạn có thể yêu cầu truy cập, sửa, xuất hoặc xóa dữ liệu. Dữ liệu được giữ khi tài khoản hoạt động và có thể được giữ tạm thời trong bản sao lưu hoặc log bảo mật trước khi xóa theo chu kỳ vận hành.'],
        },
      ]}
    />
  )
}

export function CookiesPage() {
  return (
    <LegalPage
      title="Chính sách cookie"
      summary="Cookie phiên đăng nhập, CSRF và các lựa chọn cần thiết để ứng dụng hoạt động."
      sections={[
        {
          title: '1. Cookie thiết yếu',
          paragraphs: ['Flama dùng cookie phiên để duy trì đăng nhập và token CSRF để bảo vệ các thao tác thay đổi dữ liệu. Các cookie này cần thiết để ứng dụng hoạt động an toàn.'],
        },
        {
          title: '2. Lưu trữ cục bộ',
          paragraphs: ['Ứng dụng có thể lưu tùy chọn giao diện và trạng thái tạm thời trên trình duyệt. Không lưu mật khẩu hoặc khóa thanh toán trong local storage.'],
        },
        {
          title: '3. Kiểm soát của bạn',
          paragraphs: ['Bạn có thể xóa hoặc chặn cookie trong trình duyệt, nhưng đăng nhập và một số tính năng bảo mật có thể không hoạt động.'],
        },
      ]}
    />
  )
}
