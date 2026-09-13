// @vitest-environment jsdom

// Configure React act environment for Vitest + React 19
// @ts-expect-error global declaration
globalThis.IS_REACT_ACT_ENVIRONMENT = true

import { act } from 'react'
import { createRoot, type Root } from 'react-dom/client'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { toast } from 'sonner'
import {
  TermsPage,
  PrivacyPage,
  MarketplaceGuidelinesPage,
  CommunityGuidelinesPage,
  CookiesPage,
  SupportPage,
  TtsKeyGuidePage,
  FlamaAudioGuidePage,
} from './StaticPages'
import { legalDocuments } from '@/data/legalDocumentsData'

// Mock toast notifications from sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

describe('StaticPages Legal Suite (Milestone 3 Verification)', () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let writeTextMock: ReturnType<typeof vi.fn>
  let scrollIntoViewMock: ReturnType<typeof vi.fn>
  let printMock: ReturnType<typeof vi.fn>
  let observeMock: ReturnType<typeof vi.fn>
  let disconnectMock: ReturnType<typeof vi.fn>
  let observerCallback: IntersectionObserverCallback | null = null

  beforeEach(() => {
    vi.clearAllMocks()

    // DOM Container setup
    container = document.createElement('div')
    document.body.appendChild(container)
    root = createRoot(container)

    // Mock navigator.clipboard
    writeTextMock = vi.fn().mockImplementation(() => Promise.resolve())
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: writeTextMock,
      },
      writable: true,
      configurable: true,
    })

    // Mock scrollIntoView
    scrollIntoViewMock = vi.fn()
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock as unknown as typeof Element.prototype.scrollIntoView

    // Mock window.print
    printMock = vi.fn()
    window.print = printMock as unknown as typeof window.print

    // Mock IntersectionObserver
    observeMock = vi.fn()
    disconnectMock = vi.fn()
    observerCallback = null

    class MockIntersectionObserver {
      readonly root: Element | Document | null = null
      readonly rootMargin: string = ''
      readonly scrollMargin: string = ''
      readonly thresholds: ReadonlyArray<number> = []
      observe = observeMock as unknown as (target: Element) => void
      unobserve = vi.fn() as unknown as (target: Element) => void
      disconnect = disconnectMock as unknown as () => void
      takeRecords = vi.fn().mockReturnValue([]) as unknown as () => IntersectionObserverEntry[]

      constructor(callback: IntersectionObserverCallback) {
        observerCallback = callback
      }
    }

    window.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver

    // Clear window hash
    window.location.hash = ''
  })

  afterEach(() => {
    if (root && container) {
      const activeRoot = root
      act(() => {
        activeRoot.unmount()
      })
      container.remove()
    }
    document.body.innerHTML = ''
    container = null
    root = null
    vi.useRealTimers()
  })

  // ---------------------------------------------------------------------------
  // 1. CRITICAL RE-EXPORTS PRESERVATION
  // ---------------------------------------------------------------------------
  describe('Critical Re-exports Preservation', () => {
    it('successfully re-exports SupportPage component', () => {
      expect(SupportPage).toBeDefined()
      expect(typeof SupportPage).toBe('function')
    })

    it('successfully re-exports TtsKeyGuidePage component', () => {
      expect(TtsKeyGuidePage).toBeDefined()
      expect(typeof TtsKeyGuidePage).toBe('function')
    })

    it('successfully re-exports FlamaAudioGuidePage component', () => {
      expect(FlamaAudioGuidePage).toBeDefined()
      expect(typeof FlamaAudioGuidePage).toBe('function')
    })
  })

  // ---------------------------------------------------------------------------
  // 2. RENDERING ALL 5 LEGAL PAGES (METADATA, BADGES, TITLES, READING TIMES)
  // ---------------------------------------------------------------------------
  describe('Page Rendering & Official Metadata', () => {
    it('renders TermsPage with complete metadata and core clauses', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const doc = legalDocuments.terms
      // Document title and badges
      expect(container?.textContent).toContain(doc.title)
      expect(container?.textContent).toContain(doc.officialBadge)
      expect(container?.textContent).toContain(`Phiên bản ${doc.version}`)
      expect(container?.textContent).toContain(`~${doc.readTimeMinutes} phút đọc tiêu chuẩn`)
      expect(container?.textContent).toContain(doc.effectiveDate)
      expect(container?.textContent).toContain(doc.lastUpdated)
      expect(container?.textContent).toContain(doc.executiveSummary)

      // Key domain clauses from PROJECT.md requirements
      expect(container?.textContent).toContain('Phạm vi Áp dụng & Chấp thuận Điều khoản')
      expect(container?.textContent).toContain('Tài khoản Người dùng & Quản lý Phiên Bảo mật')
      expect(container?.textContent).toContain('Tích hợp Thanh toán payOS & Quy chế Giao dịch Tài chính')
      expect(container?.textContent).toContain('Dịch vụ Vệ tinh Flama Connect & Miễn trừ Trách nhiệm Học liệu')
      expect(container?.textContent).toContain('Dịch vụ Vệ tinh Flama Audio & Bản quyền Giọng đọc AI')
      expect(container?.textContent).toContain('Giới hạn Trách nhiệm Pháp lý & Sự kiện Bất khả Kháng')

      // Verification of statutory warning callout in payOS clause
      expect(container?.textContent).toContain('Nghiêm cấm Gian lận Tài chính & Tra soát Bất hợp pháp')

      // Verification of liability cap
      expect(container?.textContent).toContain('500.000 VNĐ')
    })

    it('renders PrivacyPage with Decree 13/2023/NĐ-CP compliance and Spaced Repetition transparency', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/privacy']}>
            <PrivacyPage />
          </MemoryRouter>,
        )
      })

      const doc = legalDocuments.privacy
      expect(container?.textContent).toContain(doc.title)
      expect(container?.textContent).toContain(doc.officialBadge)
      expect(container?.textContent).toContain(`~${doc.readTimeMinutes} phút đọc tiêu chuẩn`)

      // Decree 13 & 11 Data Subject Rights
      expect(container?.textContent).toContain('Nghị định 13/2023/NĐ-CP')
      expect(container?.textContent).toContain('Quyền của Chủ thể Dữ liệu theo Điều 9 Nghị định 13/2023/NĐ-CP')
      expect(container?.textContent).toContain('Quyền được biết')
      expect(container?.textContent).toContain('Quyền xóa dữ liệu (Right to Erasure)')

      // Spaced Repetition / SRS telemetry transparency
      expect(container?.textContent).toContain('Minh bạch Thuật toán Lặp lại Ngắt quãng (Spaced Repetition Telemetry)')
      expect(container?.textContent).toContain('Thông số phản xạ thời gian')
      expect(container?.textContent).toContain('Lịch sử đánh giá ghi nhớ')
      expect(container?.textContent).toContain('Thông báo Sự cố Dữ liệu Cá nhân (Breach Notification SLA)')
    })

    it('renders MarketplaceGuidelinesPage with Three-Way IP and Clone Overlay protection', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/marketplace-guidelines']}>
            <MarketplaceGuidelinesPage />
          </MemoryRouter>,
        )
      })

      const doc = legalDocuments['marketplace-guidelines']
      expect(container?.textContent).toContain(doc.title)
      expect(container?.textContent).toContain(doc.officialBadge)
      expect(container?.textContent).toContain(`~${doc.readTimeMinutes} phút đọc tiêu chuẩn`)

      // Three-Way IP Model
      expect(container?.textContent).toContain('Phân định Ba Tầng Quyền Sở hữu Trí tuệ (Three-Way IP Division)')
      expect(container?.textContent).toContain('Quyền Sở hữu của Nền tảng Flama (Platform IP)')
      expect(container?.textContent).toContain('Quyền Sở hữu của Tác giả Tạo bộ thẻ (Deck Creators IP)')
      expect(container?.textContent).toContain('Quyền Sở hữu của Người học (Learners IP)')

      // Clone Overlay Legal Mechanism
      expect(container?.textContent).toContain('Cơ chế Pháp lý & Khiên Bảo vệ của Kiến trúc Clone Overlay')
      expect(container?.textContent).toContain('Khiên Chống Đánh cắp Bản quyền cho Tác giả (Anti-Theft Shield)')
      expect(container?.textContent).toContain('Khiên Bảo toàn Thành quả Học tập cho Người học (Study Investment Shield)')

      // Notice & Takedown Procedure
      expect(container?.textContent).toContain('Quy trình Tiếp nhận & Xử lý Khiếu nại Bản quyền (Notice & Takedown)')
      expect(container?.textContent).toContain('Chính sách Xử lý Tái phạm Bản quyền (Three-Strike Policy)')
    })

    it('renders CommunityGuidelinesPage with anti-scraping and flashcard security rules', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/community-guidelines']}>
            <CommunityGuidelinesPage />
          </MemoryRouter>,
        )
      })

      const doc = legalDocuments['community-guidelines']
      expect(container?.textContent).toContain(doc.title)
      expect(container?.textContent).toContain(doc.officialBadge)
      expect(container?.textContent).toContain(`~${doc.readTimeMinutes} phút đọc tiêu chuẩn`)

      // Prohibited conducts
      expect(container?.textContent).toContain('Tiêu chuẩn An toàn Kỹ thuật Nội dung Thẻ Học (Flashcard Security)')
      expect(container?.textContent).toContain('Nghiêm cấm Cào Dữ liệu Tự động & Hành vi Gian lận')
      expect(container?.textContent).toContain('lọc mã độc đa tầng')
      expect(container?.textContent).toContain('khử độc mã HTML')
      expect(container?.textContent).toContain('Cơ chế Báo cáo Vi phạm & Kênh Tiếp nhận Phiếu Hỗ trợ')
    })

    it('renders CookiesPage with browser storage transparency', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/cookies']}>
            <CookiesPage />
          </MemoryRouter>,
        )
      })

      const doc = legalDocuments.cookies
      expect(container?.textContent).toContain(doc.title)
      expect(container?.textContent).toContain(doc.officialBadge)
      expect(container?.textContent).toContain(`~${doc.readTimeMinutes} phút đọc tiêu chuẩn`)

      // Cookie classifications
      expect(container?.textContent).toContain('Khái niệm Cookie & Công nghệ Lưu trữ Cục bộ')
      expect(container?.textContent).toContain('Danh mục Cookie Thiết yếu Bắt buộc (Essential Cookies)')
      expect(container?.textContent).toContain('Cookie Phiên đăng nhập (session cookie)')
      expect(container?.textContent).toContain('Cookie Bảo vệ CSRF')
      expect(container?.textContent).toContain('Ứng dụng của Bộ nhớ Cục bộ (LocalStorage / SessionStorage)')
      expect(container?.textContent).toContain('Quyền Quản lý & Vô hiệu hóa Cookie của Người học')
    })
  })

  // ---------------------------------------------------------------------------
  // 3. DESKTOP TABLE OF CONTENTS & RELATED POLICIES
  // ---------------------------------------------------------------------------
  describe('Desktop Table of Contents Navigation', () => {
    it('renders TOC sidebar with clause links and clause count', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const desktopAside = container?.querySelector('aside.lg\\:block')
      expect(desktopAside).not.toBeNull()

      // Header indicates clause count
      expect(desktopAside?.textContent).toContain('Mục lục văn bản')
      expect(desktopAside?.textContent).toContain('8 điều khoản')

      // All 8 clauses are present in TOC
      const tocNav = desktopAside?.querySelector('nav[aria-label="Mục lục điều khoản"]')
      expect(tocNav).not.toBeNull()

      const clauseButtons = Array.from(tocNav?.querySelectorAll('button') || [])
      expect(clauseButtons.length).toBeGreaterThanOrEqual(8)

      // Subclauses are also listed (e.g., 1.1, 1.2, 1.3)
      expect(tocNav?.textContent).toContain('1.1')
      expect(tocNav?.textContent).toContain('Khung Thỏa thuận Pháp lý Toàn vẹn')
      expect(tocNav?.textContent).toContain('1.2')
      expect(tocNav?.textContent).toContain('Điều kiện Năng lực Hành vi & Độ tuổi')

      // Related policies navigation box
      expect(desktopAside?.textContent).toContain('Văn bản pháp lý liên quan')
      expect(desktopAside?.textContent).toContain('Chính sách bảo mật')
      expect(desktopAside?.textContent).toContain('Quy chế Marketplace')
      expect(desktopAside?.textContent).toContain('Chuẩn mực cộng đồng')
      expect(desktopAside?.textContent).toContain('Chính sách cookie')
    })

    it('scrolls to clause and updates URL hash when TOC item is clicked', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const targetEl = document.getElementById('clause-terms-payos')
      expect(targetEl).not.toBeNull()

      // Find the TOC button for Điều 3
      const tocButtons = Array.from(
        container?.querySelectorAll('nav[aria-label="Mục lục điều khoản"] button') || [],
      )
      const payosTocBtn = tocButtons.find((btn) =>
        btn.textContent?.includes('Điều 3'),
      ) as HTMLButtonElement | undefined
      expect(payosTocBtn).toBeDefined()

      await act(async () => {
        payosTocBtn?.click()
      })

      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' })
      expect(window.location.hash).toBe('#clause-terms-payos')
    })
  })

  // ---------------------------------------------------------------------------
  // 4. ANCHOR LINK DEEP LINKING & COPY TO CLIPBOARD
  // ---------------------------------------------------------------------------
  describe('Clause Anchor Deep Linking & Copy to Clipboard', () => {
    it('renders anchor copy buttons with correct aria-labels for each clause', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const clause1CopyBtn = container?.querySelector(
        'button[aria-label="Sao chép liên kết Điều 1"]',
      )
      expect(clause1CopyBtn).not.toBeNull()

      const subclauseCopyBtn = container?.querySelector(
        'button[aria-label="Sao chép liên kết 1.1"]',
      )
      expect(subclauseCopyBtn).not.toBeNull()
    })

    it('copies deep-link URL and triggers toast notification when clause anchor is clicked', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const clause1CopyBtn = container?.querySelector(
        'button[aria-label="Sao chép liên kết Điều 1"]',
      ) as HTMLButtonElement

      await act(async () => {
        clause1CopyBtn.click()
      })

      expect(writeTextMock).toHaveBeenCalledTimes(1)
      expect(writeTextMock).toHaveBeenCalledWith(
        expect.stringMatching(/#clause-terms-scope$/),
      )
      expect(toast.success).toHaveBeenCalledWith(
        'Đã sao chép liên kết: Điều 1 - Phạm vi Áp dụng & Chấp thuận Điều khoản',
      )
      expect(window.location.hash).toBe('#clause-terms-scope')
    })

    it('copies subclause deep-link URL when subclause anchor button is clicked', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const subclauseCopyBtn = container?.querySelector(
        'button[aria-label="Sao chép liên kết 1.1"]',
      ) as HTMLButtonElement

      await act(async () => {
        subclauseCopyBtn.click()
      })

      expect(writeTextMock).toHaveBeenCalledTimes(1)
      expect(writeTextMock).toHaveBeenCalledWith(
        expect.stringMatching(/#terms-1-1$/),
      )
      expect(toast.success).toHaveBeenCalledWith(
        'Đã sao chép liên kết: 1.1 - Khung Thỏa thuận Pháp lý Toàn vẹn',
      )
      expect(window.location.hash).toBe('#terms-1-1')
    })

    it('copies whole document URL when header copy button is clicked', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const headerCopyBtn = container?.querySelector(
        'button[title="Sao chép liên kết tài liệu"]',
      ) as HTMLButtonElement
      expect(headerCopyBtn).not.toBeNull()

      await act(async () => {
        headerCopyBtn.click()
      })

      expect(writeTextMock).toHaveBeenCalledTimes(1)
      expect(toast.success).toHaveBeenCalledWith('Đã sao chép liên kết văn bản!')
    })

    it('handles clipboard API write rejection gracefully with fallback toast', async () => {
      writeTextMock.mockRejectedValueOnce(new Error('Permission denied'))

      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const clause1CopyBtn = container?.querySelector(
        'button[aria-label="Sao chép liên kết Điều 1"]',
      ) as HTMLButtonElement

      await act(async () => {
        clause1CopyBtn.click()
      })

      // Even when clipboard write fails, hash is updated and fallback toast displayed
      expect(window.location.hash).toBe('#clause-terms-scope')
      expect(toast.success).toHaveBeenCalledWith(
        'Đã chọn: Điều 1 - Phạm vi Áp dụng & Chấp thuận Điều khoản',
      )
    })
  })

  // ---------------------------------------------------------------------------
  // 5. MOBILE TABLE OF CONTENTS DRAWER (SHEET)
  // ---------------------------------------------------------------------------
  describe('Mobile TOC Drawer (Sheet)', () => {
    it('renders floating mobile TOC trigger button with clause count', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const mobileTrigger = Array.from(
        container?.querySelectorAll('button') || [],
      ).find((btn) => btn.textContent?.includes('Mục lục (8 điều)'))

      expect(mobileTrigger).toBeDefined()
    })

    it('opens mobile TOC drawer and selects clause to navigate', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const mobileTrigger = Array.from(
        container?.querySelectorAll('button') || [],
      ).find((btn) => btn.textContent?.includes('Mục lục (8 điều)')) as HTMLButtonElement

      // Trigger drawer open
      await act(async () => {
        mobileTrigger.click()
      })

      // Radix UI Dialog / Sheet portals to document.body
      const sheetContent = document.body.querySelector('[data-slot="sheet-content"]')
      expect(sheetContent).not.toBeNull()
      expect(sheetContent?.textContent).toContain('Mục lục văn bản')

      // Select clause inside the drawer
      const drawerClauseButtons = Array.from(
        sheetContent?.querySelectorAll('button') || [],
      )
      const payosClauseBtn = drawerClauseButtons.find((btn) =>
        btn.textContent?.includes('Điều 3'),
      )
      expect(payosClauseBtn).toBeDefined()

      await act(async () => {
        payosClauseBtn?.click()
      })

      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' })
      expect(window.location.hash).toBe('#clause-terms-payos')
    })
  })

  // ---------------------------------------------------------------------------
  // 6. TOP DOCUMENT SWITCHER TABS & CROSS-POLICY NAVIGATION
  // ---------------------------------------------------------------------------
  describe('Top Document Switcher Tabs', () => {
    it('renders all 5 policy switch links with correct routes', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const switcherNav = container?.querySelector(
        'nav[aria-label="Chuyển đổi văn bản pháp lý"]',
      )
      expect(switcherNav).not.toBeNull()

      const links = Array.from(switcherNav?.querySelectorAll('a') || [])
      expect(links).toHaveLength(5)

      const expectedLinks = [
        { href: '/terms', label: 'Điều khoản dịch vụ' },
        { href: '/privacy', label: 'Chính sách bảo mật' },
        { href: '/marketplace-guidelines', label: 'Quy chế Marketplace' },
        { href: '/community-guidelines', label: 'Chuẩn mực cộng đồng' },
        { href: '/cookies', label: 'Chính sách cookie' },
      ]

      expectedLinks.forEach((expected, idx) => {
        expect(links[idx]?.getAttribute('href')).toBe(expected.href)
        expect(links[idx]?.textContent).toBe(expected.label)
      })
    })

    it('marks current document tab with active primary styling', async () => {
      // Test TermsPage active tab
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      let switcherNav = container?.querySelector(
        'nav[aria-label="Chuyển đổi văn bản pháp lý"]',
      )
      let termsLink = switcherNav?.querySelector('a[href="/terms"]')
      let privacyLink = switcherNav?.querySelector('a[href="/privacy"]')

      expect(termsLink?.className).toContain('bg-primary')
      expect(termsLink?.className).toContain('text-primary-foreground')
      expect(privacyLink?.className).not.toContain('bg-primary')

      // Test PrivacyPage active tab
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/privacy']}>
            <PrivacyPage />
          </MemoryRouter>,
        )
      })

      switcherNav = container?.querySelector(
        'nav[aria-label="Chuyển đổi văn bản pháp lý"]',
      )
      termsLink = switcherNav?.querySelector('a[href="/terms"]')
      privacyLink = switcherNav?.querySelector('a[href="/privacy"]')

      expect(privacyLink?.className).toContain('bg-primary')
      expect(termsLink?.className).not.toContain('bg-primary')
    })
  })

  // ---------------------------------------------------------------------------
  // 7. EDITORIAL LAYOUT, STATUTORY CALLOUTS & PRINT OPTIMIZATION
  // ---------------------------------------------------------------------------
  describe('Editorial Layout, Callouts & Print Support', () => {
    it('uses editorial max-w-3xl prose container without card-in-card nesting', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const article = container?.querySelector('article')
      expect(article).not.toBeNull()
      expect(article?.className).toContain('max-w-3xl')

      // Editorial clauses have clean legal-clause class
      const clauses = container?.querySelectorAll('.legal-clause')
      expect(clauses?.length).toBe(8)
    })

    it('renders statutory callout blocks with accessible icons and semantic aria-labels', async () => {
      // Test warning and statutory callouts on TermsPage
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      // Warning callout in Clause 3 (payOS)
      const warningCallout = container?.querySelector(
        'aside[aria-label="Nghiêm cấm Gian lận Tài chính & Tra soát Bất hợp pháp"]',
      )
      expect(warningCallout).not.toBeNull()
      expect(warningCallout?.className).toContain('border-amber-500/80')
      expect(warningCallout?.textContent).toContain('Nghiêm cấm Gian lận Tài chính & Tra soát Bất hợp pháp')

      // Statutory callout in Clause 2 (Accounts)
      const statutoryCallout = container?.querySelector(
        'aside[aria-label="Lưu ý Pháp lý về Bảo vệ Phiên Đăng nhập"]',
      )
      expect(statutoryCallout).not.toBeNull()
      expect(statutoryCallout?.className).toContain('border-primary/80')

      // Test info callout on PrivacyPage
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/privacy']}>
            <PrivacyPage />
          </MemoryRouter>,
        )
      })

      const infoCallout = container?.querySelector(
        'aside[aria-label="Cam kết Phân lập Hạ tầng Thanh toán"]',
      )
      expect(infoCallout).not.toBeNull()
      expect(infoCallout?.className).toContain('border-sky-500/80')
      expect(infoCallout?.textContent).toContain('Cam kết Phân lập Hạ tầng Thanh toán')
    })

    it('includes print stylesheet rules for page break avoidance', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const styleTag = container?.querySelector('style')
      expect(styleTag).not.toBeNull()
      expect(styleTag?.textContent).toContain('@media print')
      expect(styleTag?.textContent).toContain('break-inside: avoid !important;')
      expect(styleTag?.textContent).toContain('.print-hidden')
    })

    it('calls window.print when print button is clicked', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const printButton = container?.querySelector(
        'button[title="In văn bản hoặc xuất PDF"]',
      ) as HTMLButtonElement
      expect(printButton).not.toBeNull()

      await act(async () => {
        printButton.click()
      })

      expect(printMock).toHaveBeenCalledTimes(1)
    })

    it('renders dispute resolution & concierge support footer with link to /support', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      const supportFooter = container?.querySelector('footer')
      expect(supportFooter).not.toBeNull()
      expect(supportFooter?.textContent).toContain(
        'Bạn có thắc mắc hoặc cần giải quyết tranh chấp pháp lý?',
      )
      expect(supportFooter?.textContent).toContain('24–48 giờ')

      const supportLink = supportFooter?.querySelector('a[href="/support"]')
      expect(supportLink).not.toBeNull()
      expect(supportLink?.textContent).toContain('Gửi yêu cầu hỗ trợ')
    })
  })

  // ---------------------------------------------------------------------------
  // 8. SCROLLSPY & INITIAL HASH NAVIGATION
  // ---------------------------------------------------------------------------
  describe('Scrollspy & Initial Hash Navigation', () => {
    it('observes all clause headings with IntersectionObserver', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      expect(observeMock).toHaveBeenCalled()
      // Total tracked headings (8 clauses + subclauses)
      const trackedElements = container?.querySelectorAll('[data-clause-id]')
      expect(trackedElements?.length).toBeGreaterThanOrEqual(8)
      expect(observeMock.mock.calls.length).toBe(trackedElements?.length)
    })

    it('updates active clause when IntersectionObserver triggers', async () => {
      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      expect(observerCallback).not.toBeNull()

      const payosHeading = document.getElementById('clause-terms-payos')
      expect(payosHeading).not.toBeNull()

      // Simulate intersection
      await act(async () => {
        observerCallback?.(
          [
            {
              target: payosHeading!,
              isIntersecting: true,
              boundingClientRect: { top: 100 } as DOMRectReadOnly,
            } as unknown as IntersectionObserverEntry,
          ],
          {} as unknown as IntersectionObserver,
        )
      })

      // The desktop TOC item for Điều 3 should now have active primary styling
      const desktopAside = container?.querySelector('aside.lg\\:block')
      const activeTocBtn = desktopAside?.querySelector('button.bg-primary\\/10')
      expect(activeTocBtn?.textContent).toContain('Điều 3.')
    })

    it('scrolls to initial URL hash on mount after delay', async () => {
      vi.useFakeTimers()
      window.location.hash = '#clause-terms-payos'

      await act(async () => {
        root?.render(
          <MemoryRouter initialEntries={['/terms#clause-terms-payos']}>
            <TermsPage />
          </MemoryRouter>,
        )
      })

      // Advance past 120ms debounce timeout
      await act(async () => {
        vi.advanceTimersByTime(200)
      })

      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: 'smooth' })
    })
  })

  // ---------------------------------------------------------------------------
  // 9. ZERO TECHNICAL LEAKS & ZERO NARROW DOMAIN STEREOTYPES
  // ---------------------------------------------------------------------------
  describe('Zero Technical Leaks & Zero Narrow Stereotypes in Rendered DOM', () => {
    const FORBIDDEN_TOKENS = [
      'flask',
      'werkzeug',
      'pbkdf',
      'fernet',
      'bleach',
      'dompurify',
      '.net 8',
      'wpf',
      '4790',
      '4791',
      '127.0.0.1',
      'localhost',
      'payment_orders',
      'review_events',
      'card_progress',
      'deckclonenotefieldoverride',
      'deckinstall',
      'deckrelease',
      'on delete cascade',
      'user_id = null',
      'merchant_order_code',
      'is_disabled = true',
      'clone_mode',
      'user_disabled',
      'too many requests',
      'userapitoken',
      'flama_audio_pairing_token',
      'reviewed_at',
      'duration_ms',
      'step_index',
      'ease_factor',
      'lapses',
      'memory_stability',
      'leech',
      'voicevox',
      'kokoro',
      'yomitan',
      'tiếng nhật',
      'nhật bản',
      'jlpt',
      'nat-test',
      'minna no nihongo',
      'kanji',
      'furigana',
      'zundamon',
      'shikikoin',
      'kasukabe',
      'ずんだもん',
      'ba gậy',
      'zero-copy',
      'note types',
      'field overrides',
      '30m ttl',
      'oidc',
      'avatar url',
      'mysql',
      'sqlite',
      'sqlalchemy',
      'alembic',
      'gunicorn',
      'ankiconnect',
      'yomichan',
      'rikaichan',
      'mecab',
      'sudachi',
      'kuromoji',
      'soumatome',
      'shin kanzen',
      'genki',
      'tobira',
      'jft-basic',
      'bjt',
      'eju',
      'kanken',
      'hiragana',
      'katakana',
    ]

    const pages = [
      { name: 'TermsPage', path: '/terms', component: <TermsPage /> },
      { name: 'PrivacyPage', path: '/privacy', component: <PrivacyPage /> },
      {
        name: 'MarketplaceGuidelinesPage',
        path: '/marketplace-guidelines',
        component: <MarketplaceGuidelinesPage />,
      },
      {
        name: 'CommunityGuidelinesPage',
        path: '/community-guidelines',
        component: <CommunityGuidelinesPage />,
      },
      { name: 'CookiesPage', path: '/cookies', component: <CookiesPage /> },
    ]

    pages.forEach(({ name, path, component }) => {
      it(`ensures rendered ${name} has zero technical leaks or narrow domain stereotypes`, async () => {
        await act(async () => {
          root?.render(
            <MemoryRouter initialEntries={[path]}>
              {component}
            </MemoryRouter>,
          )
        })

        const renderedText = (container?.textContent || '').toLowerCase()
        FORBIDDEN_TOKENS.forEach((token) => {
          expect(renderedText).not.toContain(token.toLowerCase())
        })
      })
    })
  })
})

