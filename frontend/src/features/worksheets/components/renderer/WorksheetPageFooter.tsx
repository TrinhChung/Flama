import { useTranslation } from 'react-i18next'
import type { WorksheetLayoutOptions } from '../../types'

/** Genkō yōshi footer: brand label, page counter and a handwritten-date line. */
export function EssayPageFooter({
  options,
  pageNumber,
  totalPages,
}: {
  options: WorksheetLayoutOptions
  pageNumber: number
  totalPages: number
}) {
  const { t } = useTranslation('worksheets')
  return (
    <footer className="pt-1 mt-2 flex justify-between items-center text-[10px] text-slate-500 shrink-0 relative z-10 px-1 font-serif">
      <span className="font-semibold text-slate-600">
        {options.footer_brand_label || 'Flama (400格)'}
      </span>
      <span className="text-[9px] text-slate-400 font-sans">
        {t('renderer.page_label', {
          current: pageNumber,
          total: totalPages,
          defaultValue: `Trang ${pageNumber} / ${totalPages}`,
        })}
      </span>
      <span className="tracking-widest">
        {options.footer_date_format === 'vietnamese'
          ? 'Ngày ...... Tháng ...... Năm 20......'
          : '年    月    日'}
      </span>
    </footer>
  )
}

/** Standard footer: generator credit with a link back to the source domain. */
export function StandardPageFooter({
  currentUrl,
  currentDomain,
  pageNumber,
  totalPages,
}: {
  currentUrl: string
  currentDomain: string
  pageNumber: number
  totalPages: number
}) {
  return (
    <footer className="border-t border-slate-200 pt-1 mt-2 flex justify-between items-center text-[9px] text-slate-400 shrink-0 relative z-10">
      <span className="truncate max-w-[75%]">
        Flama Worksheet Generator &bull;{' '}
        {currentUrl ? (
          <a
            href={currentUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline text-inherit"
          >
            {currentDomain}
          </a>
        ) : (
          currentDomain
        )}
      </span>
      <span className="shrink-0 ml-2">
        Trang {pageNumber} / {totalPages}
      </span>
    </footer>
  )
}
