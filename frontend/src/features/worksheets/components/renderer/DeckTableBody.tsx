import { Table as TableIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type {
  WorksheetFieldMapping,
  WorksheetItem,
  WorksheetLayoutOptions,
  WorksheetTableRowItem,
} from '../../types'
import { KanjiGridBox } from '../KanjiGridBox'
import type { GridStyle } from './pageMetrics'

/** `custom_columns` may be stored as a list or a comma-separated string. */
function customColumns(fieldMapping: WorksheetFieldMapping): string[] {
  const rawCols = fieldMapping.custom_columns || []
  return Array.isArray(rawCols)
    ? rawCols
    : String(rawCols).split(',').map((s) => s.trim()).filter(Boolean)
}

function widthStyle(width: string | number | undefined): string | undefined {
  if (!width) return undefined
  return typeof width === 'number' ? `${width}%` : width
}

function AuxiliaryCell({
  type,
  boxesCount,
  gridStyle,
}: {
  type: NonNullable<WorksheetLayoutOptions['auxiliary_column_type']>
  boxesCount: number
  gridStyle: GridStyle
}) {
  if (type === 'grid_boxes') {
    return (
      <div className="flex items-center justify-center -space-x-px border border-slate-600 bg-white rounded-[2px] overflow-hidden w-fit mx-auto shadow-2xs">
        {Array.from({ length: boxesCount }).map((_, bIdx) => (
          <KanjiGridBox
            key={`aux-b-${bIdx}`}
            char=""
            gridStyle={gridStyle}
            isBlank={true}
            size={22}
            rounded={false}
            strokeColor="#cbd5e1"
          />
        ))}
      </div>
    )
  }
  if (type === 'checkboxes') {
    return (
      <div className="flex items-center justify-around gap-1 text-[10px] text-slate-500 font-medium px-1">
        <span className="flex items-center gap-1">
          <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 1
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 2
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block size-3.5 rounded-[2px] border border-slate-400 bg-white" /> 3
        </span>
      </div>
    )
  }
  if (type === 'double_line') {
    return (
      <div className="flex flex-col justify-between min-h-[22px] py-1 gap-1.5 w-full">
        <div className="w-full border-b border-slate-300" />
        <div className="w-full border-b border-slate-300" />
      </div>
    )
  }
  if (type === 'blank') {
    return <div className="w-full min-h-[20px]" />
  }
  // Default: dashed line
  return <div className="w-full min-h-[20px] border-b border-dashed border-slate-300" />
}

/** Free-form table of user-picked fields with an optional auxiliary practice column. */
export function DeckTableBody({
  items,
  options,
  fieldMapping,
  gridStyle,
}: {
  items: WorksheetItem[]
  options: WorksheetLayoutOptions
  fieldMapping: WorksheetFieldMapping
  gridStyle: GridStyle
}) {
  const { t } = useTranslation('worksheets')
  const cols = customColumns(fieldMapping)

  if (cols.length === 0) {
    return (
      <div className="w-full border-2 border-dashed border-slate-300 rounded-xl p-8 flex flex-col items-center justify-center text-center gap-2 bg-slate-50/60 my-6">
        <div className="size-10 rounded-full bg-slate-200 flex items-center justify-center text-slate-500">
          <TableIcon className="size-5" />
        </div>
        <div className="text-sm font-bold text-slate-700">
          {t('renderer.no_columns_selected', 'Chưa chọn cột nào để hiển thị')}
        </div>
        <p className="text-xs text-slate-500 max-w-sm">
          {t(
            'renderer.no_columns_hint',
            'Vui lòng mở tab "Dữ liệu & Trường" ở bảng điều khiển bên trái và tích chọn các trường bạn muốn xuất bảng.'
          )}
        </p>
      </div>
    )
  }

  const colWidths = options.column_widths || {}
  const hasAuxCol =
    options.auxiliary_column_enabled !== undefined
      ? options.auxiliary_column_enabled
      : options.include_practice_column !== false
  const auxTitle =
    options.auxiliary_column_title ||
    options.practice_column_label ||
    t('renderer.auxiliary_default_title', 'Ghi chú / Luyện viết')
  const auxType = options.auxiliary_column_type || 'dashed_line'
  const auxBoxesCount = options.auxiliary_column_boxes_count || 4

  return (
    <table className="w-full border-collapse text-xs border border-slate-400 table-fixed">
      <thead>
        <tr className="bg-slate-100 text-slate-900 text-left font-semibold">
          {cols.map((col, cIdx) => (
            <th
              key={cIdx}
              className="border border-slate-400 px-2 py-1.5 text-xs truncate"
              style={{ width: widthStyle(colWidths[col]) }}
            >
              {col}
            </th>
          ))}
          {hasAuxCol && (
            <th
              className="border border-slate-400 px-2 py-1.5 text-xs text-center truncate"
              style={{ width: widthStyle(options.auxiliary_column_width) }}
            >
              {auxTitle}
            </th>
          )}
        </tr>
      </thead>
      <tbody>
        {items.map((rawItem, idx) => {
          const item = (rawItem || {}) as WorksheetTableRowItem
          const rowData =
            item && typeof item === 'object' && 'data' in item && item.data
              ? item.data
              : {}

          return (
            <tr key={`${item.note_id || idx}-${idx}`} className="border-b border-slate-300">
              {cols.map((col, cIdx) => (
                <td
                  key={cIdx}
                  className="border border-slate-300 px-2 py-1.5 text-slate-800 text-xs overflow-hidden break-words"
                >
                  {rowData[col] ??
                    (typeof item === 'object' && 'word' in item
                      ? (item as any).word
                      : typeof item === 'object' && 'char' in item
                      ? (item as any).char
                      : '')}
                </td>
              ))}
              {hasAuxCol && (
                <td className="border border-slate-300 px-2 py-1.5 align-middle">
                  <AuxiliaryCell type={auxType} boxesCount={auxBoxesCount} gridStyle={gridStyle} />
                </td>
              )}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
