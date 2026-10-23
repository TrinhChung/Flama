import { useTranslation } from 'react-i18next'
import { useQrCodePath } from '../../hooks/useQrCodePath'
import type { WorksheetLayoutOptions, WorksheetPageData } from '../../types'

interface PageHeaderProps {
  header: WorksheetPageData['header']
  options: WorksheetLayoutOptions
}

/** Genkō yōshi header: optional title plus a localized student-info line. */
export function EssayPageHeader({ header, options }: PageHeaderProps) {
  const { t } = useTranslation('worksheets')
  return (
    <header className="mb-2 shrink-0 relative z-10 w-full">
      {options.title_placement === 'header' && header.title && (
        <h1 className="text-center font-bold text-slate-900 text-base sm:text-lg mb-1.5">
          {header.title}
        </h1>
      )}
      {header.show_student_info && (
        <div className="flex justify-between items-center text-xs font-medium text-slate-800 px-1 py-0.5">
          {options.header_student_style === 'chinese' || !options.header_student_style ? (
            <>
              <span>班级 ____________</span>
              <span>姓名 ____________</span>
              <span>学号 ____________</span>
              <span>分数 ____________</span>
            </>
          ) : options.header_student_style === 'japanese' ? (
            <>
              <span>クラス ____________</span>
              <span>氏名 ____________</span>
              <span>学籍番号 ____________</span>
              <span>得点 ____________</span>
            </>
          ) : options.header_student_style === 'vietnamese' ? (
            <>
              <span>Lớp: ____________</span>
              <span>Họ tên: ____________</span>
              <span>Mã số: ____________</span>
              <span>Điểm: ____________</span>
            </>
          ) : (
            <>
              <span>{t('renderer.student_class', 'Lớp')}: ____________</span>
              <span>{t('renderer.student_name', 'Họ tên')}: ____________</span>
              <span>{t('renderer.student_score', 'Điểm')}: ____________</span>
            </>
          )}
        </div>
      )}
    </header>
  )
}

/** Standard header: QR link to the source page, title, student fields and page counter. */
export function StandardPageHeader({
  header,
  pageNumber,
  totalPages,
  currentUrl,
}: {
  header: WorksheetPageData['header']
  pageNumber: number
  totalPages: number
  currentUrl: string
}) {
  const { t } = useTranslation('worksheets')
  const qrData = useQrCodePath(currentUrl)
  return (
    <header className="border-b-2 border-slate-900 pb-1.5 mb-2.5 flex justify-between items-end shrink-0 relative z-10">
      <div className="flex items-end gap-2.5">
        {qrData && (
          <div className="relative w-11 h-0 shrink-0">
            <a
              href={currentUrl || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="absolute bottom-0 -left-2.5 w-[54px] h-[54px] p-1 bg-white border border-slate-300 rounded shadow-xs flex items-center justify-center hover:opacity-85 transition-opacity z-20"
              title={t('renderer.qr_title', {
                url: currentUrl,
                defaultValue: `Quét mã QR để mở trang: ${currentUrl}`,
              })}
              aria-label={t('renderer.qr_aria', 'Mã QR trang bài tập')}
            >
              <svg
                viewBox={`0 0 ${qrData.totalSize} ${qrData.totalSize}`}
                shapeRendering="crispEdges"
                className="size-full block"
              >
                <rect width={qrData.totalSize} height={qrData.totalSize} fill="#ffffff" />
                <path d={qrData.path} fill="#0f172a" />
              </svg>
            </a>
          </div>
        )}
        <div>
          <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight leading-tight">
            {header.title || 'Flama Worksheet'}
          </h1>
          {header.subtitle && (
            <p className="text-[10px] text-slate-500 mt-0.5">{header.subtitle}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 text-[10px] text-slate-700 font-medium shrink-0">
        {header.show_student_info && (
          <span>
            <strong className="text-slate-900">{t('renderer.name_label', 'Họ tên')}:</strong> _______________
          </span>
        )}
        {header.show_date && (
          <span>
            <strong className="text-slate-900">{t('renderer.date_label', 'Ngày')}:</strong> ___/___/20___
          </span>
        )}
        <span className="text-slate-500 font-normal">
          {t('renderer.page_label', {
            current: pageNumber,
            total: totalPages,
            defaultValue: `Trang ${pageNumber} / ${totalPages}`,
          })}
        </span>
      </div>
    </header>
  )
}
