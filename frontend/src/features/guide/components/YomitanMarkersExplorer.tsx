import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { EmptyState } from '@/shared/components/PageState'
import { toast } from 'sonner'
import {
  Check,
  Code,
  Copy,
  LayoutTemplate,
  Search,
} from 'lucide-react'

export type MarkerCategory = 'term' | 'kanji' | 'both'

export interface MarkerItem {
  name: string
  category: MarkerCategory
  description: string
  example?: string
}

export const YOMITAN_MARKERS: MarkerItem[] = [
  // Term markers (28)
  { name: '{audio}', category: 'term', description: 'File âm thanh phát âm của từ vựng từ các nguồn audio khả dụng (tự động nạp vào Flama tối đa 1 MB).' },
  { name: '{cloze-body-kana}', category: 'term', description: 'Cách đọc Kana cho từ thể cloze ({cloze-body}).' },
  { name: '{conjugation}', category: 'term', description: 'Chuỗi chia từ (conjugation path) từ từ inflected ban đầu về từ điển nguyên thể.' },
  { name: '{expression}', category: 'term', description: 'Từ vựng biểu diễn bằng Kanji (nếu không có Kanji sẽ sử dụng Kana). Khuyên dùng làm marker cho trường đầu tiên của thẻ từ vựng.', example: '日本語' },
  { name: '{furigana}', category: 'term', description: 'Từ dạng Kanji có hiển thị Furigana phía trên dạng thẻ HTML ruby.', example: '日本語[にほんご]' },
  { name: '{furigana-plain}', category: 'term', description: 'Từ dạng Kanji có hiển thị Furigana bên cạnh trong ngoặc vuông.', example: '日本語[にほんご]' },
  { name: '{glossary}', category: 'term', description: 'Danh sách đầy đủ các nghĩa / định nghĩa của từ vựng từ từ điển đã cài.' },
  { name: '{glossary-brief}', category: 'term', description: 'Danh sách định nghĩa của từ ở định dạng ngắn gọn, súc tích hơn.' },
  { name: '{glossary-no-dictionary}', category: 'term', description: 'Danh sách định nghĩa của từ, ngoại trừ nhãn tên từ điển bị ẩn.' },
  { name: '{glossary-first}', category: 'term', description: 'Định nghĩa đầu tiên của từ vựng.' },
  { name: '{glossary-plain}', category: 'term', description: 'Danh sách định nghĩa của từ chỉ sử dụng HTML cho các đoạn ngắt dòng.' },
  { name: '{glossary-plain-no-dictionary}', category: 'term', description: '{glossary-plain} ngoại trừ nhãn tên từ điển bị ẩn.' },
  { name: '{glossary-first-brief}', category: 'term', description: 'Định nghĩa đầu tiên của từ ở định dạng ngắn gọn hơn.' },
  { name: '{glossary-first-no-dictionary}', category: 'term', description: 'Định nghĩa đầu tiên của từ, ngoại trừ nhãn từ điển bị ẩn.' },
  { name: '{part-of-speech}', category: 'term', description: 'Thông tin từ loại của từ (Danh từ, Động từ, Tính từ,...).' },
  { name: '{phonetic-transcriptions}', category: 'term', description: 'Danh sách phiên âm ngữ âm cho từ vựng.' },
  { name: '{pitch-accents}', category: 'term', description: 'Danh sách ký hiệu hạ giọng trọng âm (downstep notations) cho từ.' },
  { name: '{pitch-accent-graphs}', category: 'term', description: 'Danh sách biểu đồ trọng âm (pitch accent graphs) cho từ.' },
  { name: '{pitch-accent-graphs-jj}', category: 'term', description: 'Danh sách biểu đồ trọng âm cho từ (được thiết kế theo phong cách Jidoujisho).' },
  { name: '{pitch-accent-positions}', category: 'term', description: 'Danh sách các vị trí hạ giọng trọng âm của từ ở dạng số.' },
  { name: '{pitch-accent-categories}', category: 'term', description: 'Danh sách phân loại nhóm trọng âm của từ (ví dụ: heiban, kifuku, atamadaka, odaka, nakadaka).' },
  { name: '{reading}', category: 'term', description: 'Cách đọc Kana cho từ, hoặc để trống đối với các từ mà biểu thức (expression) chính là cách đọc.', example: 'にほんご' },
  { name: '{single-glossary-DICT-NAME}', category: 'term', description: 'Tương tự {glossary}, nhưng chỉ lấy nội dung từ một từ điển duy nhất.' },
  { name: '{single-glossary-DICT-NAME-brief}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-brief}.' },
  { name: '{single-glossary-DICT-NAME-no-dictionary}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-no-dictionary}.' },
  { name: '{single-glossary-DICT-NAME-plain}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-plain}.' },
  { name: '{single-glossary-DICT-NAME-plain-no-dictionary}', category: 'term', description: 'Xem {single-glossary-DICT-NAME} và {glossary-plain-no-dictionary}.' },
  { name: '{tags}', category: 'term', description: 'Thẻ ngữ pháp và cách sử dụng cung cấp thông tin chi tiết về từ.' },

  // Kanji markers (6)
  { name: '{character}', category: 'kanji', description: 'Ký tự Unicode đại diện cho chữ Hán (Kanji) hiện tại. Khuyên dùng làm marker cho trường đầu tiên của thẻ Kanji.', example: '日' },
  { name: '{glossary}', category: 'kanji', description: 'Danh sách nghĩa / định nghĩa của chữ Hán.' },
  { name: '{kunyomi}', category: 'kanji', description: 'Cách đọc Kunyomi (âm Nhật) của chữ Hán, thể hiện bằng Hiragana.', example: 'ひ, び, か' },
  { name: '{onyomi}', category: 'kanji', description: 'Cách đọc Onyomi (âm Hán) của chữ Hán, thể hiện bằng Katakana.', example: 'ニチ, ジツ' },
  { name: '{onyomi-hiragana}', category: 'kanji', description: 'Cách đọc Onyomi (âm Hán) của chữ Hán, thể hiện bằng Hiragana.', example: 'にち, ジつ' },
  { name: '{stroke-count}', category: 'kanji', description: 'Số nét vẽ của ký tự chữ Hán.', example: '4' },

  // Both markers (22)
  { name: '{clipboard-image}', category: 'both', description: 'Hình ảnh được lưu trong bộ nhớ tạm (clipboard) của hệ thống (nếu có).' },
  { name: '{clipboard-text}', category: 'both', description: 'Đoạn văn bản được lưu trong bộ nhớ tạm (clipboard) của hệ thống (nếu có).' },
  { name: '{cloze-body}', category: 'both', description: 'Từ vựng dạng bị biến đổi ban đầu như khi xuất hiện trước khi được Yomitan đưa về dạng từ điển.' },
  { name: '{cloze-prefix}', category: 'both', description: 'Trích đoạn của câu {sentence} tính từ đầu câu cho đến trước {cloze-body}.' },
  { name: '{cloze-suffix}', category: 'both', description: 'Trích đoạn của câu {sentence} tính từ sau {cloze-body} cho đến hết câu.' },
  { name: '{dictionary}', category: 'both', description: 'Tên gốc của từ điển tạo nên thẻ ghi nhớ.' },
  { name: '{dictionary-alias}', category: 'both', description: 'Tên hiển thị của từ điển tạo nên thẻ ghi nhớ.' },
  { name: '{document-title}', category: 'both', description: 'Tiêu đề trang web nơi từ vựng hoặc chữ Hán xuất hiện.' },
  { name: '{frequencies}', category: 'both', description: 'Thông tin tần suất xuất hiện / độ phổ biến của từ vựng hoặc chữ Hán.' },
  { name: '{frequency-harmonic-rank}', category: 'both', description: 'Thứ hạng trung bình điều hòa về độ phổ biến. Mặc định là 9999999 khi không tìm thấy dữ liệu.' },
  { name: '{frequency-harmonic-occurrence}', category: 'both', description: 'Số lần xuất hiện trung bình điều hòa. Mặc định là 0 khi không tìm thấy dữ liệu.' },
  { name: '{frequency-average-rank}', category: 'both', description: 'Thứ hạng trung bình cộng về độ phổ biến. Mặc định là 9999999 khi không tìm thấy dữ liệu.' },
  { name: '{frequency-average-occurrence}', category: 'both', description: 'Số lần xuất hiện trung bình cộng. Mặc định là 0 khi không tìm thấy dữ liệu.' },
  { name: '{single-frequency-DICT-NAME}', category: 'both', description: 'Tất cả dữ liệu tần suất từ từ điển được chọn dưới dạng danh sách.' },
  { name: '{single-frequency-number-DICT-NAME}', category: 'both', description: 'Con số tần suất đơn từ từ điển được chọn không kèm định dạng dữ liệu.' },
  { name: '{screenshot}', category: 'both', description: 'Ảnh chụp màn hình trang web tại thời điểm từ vựng hoặc chữ Hán được thêm vào.' },
  { name: '{search-query}', category: 'both', description: 'Truy vấn tìm kiếm đầy đủ được hiển thị trên trang tìm kiếm hoặc popup.' },
  { name: '{popup-selection-text}', category: 'both', description: 'Đoạn văn bản đang được chọn / bôi đen trên trang tìm kiếm hoặc popup.' },
  { name: '{sentence}', category: 'both', description: 'Câu văn, trích dẫn hoặc cụm từ chứa từ vựng/chữ Hán từ nội dung nguồn.' },
  { name: '{sentence-furigana}', category: 'both', description: 'Câu văn hoặc trích dẫn chứa từ/Kanji có thêm Furigana dạng HTML.' },
  { name: '{sentence-furigana-plain}', category: 'both', description: 'Câu văn hoặc trích dẫn chứa từ/Kanji có thêm Furigana trong dấu ngoặc vuông [...].' },
  { name: '{url}', category: 'both', description: 'Địa chỉ URL của trang web nơi từ vựng hoặc chữ Hán xuất hiện.' },
  { name: '{url-plain}', category: 'both', description: 'Địa chỉ URL thô ({url}) không chứa HTML.' },
]

export function YomitanMarkersExplorer() {
  const { t } = useTranslation('guide')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'term' | 'kanji' | 'both'>('all')
  const [copied, setCopied] = useState<string | null>(null)

  const copy = async (label: string, value: string) => {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    window.setTimeout(() => setCopied(null), 1800)
    toast.success(t('yomitan.template_copied'))
  }

  const filteredMarkers = YOMITAN_MARKERS.filter((m) => {
    const matchesCategory = selectedCategory === 'all' || m.category === selectedCategory
    const q = searchQuery.trim().toLowerCase()
    const matchesSearch =
      !q ||
      m.name.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      (m.example && m.example.toLowerCase().includes(q))
    return matchesCategory && matchesSearch
  })

  const countTerm = YOMITAN_MARKERS.filter((m) => m.category === 'term').length
  const countKanji = YOMITAN_MARKERS.filter((m) => m.category === 'kanji').length
  const countBoth = YOMITAN_MARKERS.filter((m) => m.category === 'both').length

  return (
    <div className="space-y-6 w-full min-w-0">
      {/* Quick Recommended Template Card */}
      <Card className="rounded-2xl border border-purple-500/30 bg-gradient-to-br from-purple-500/5 via-card to-background shadow-2xs">
        <CardHeader className="p-4 sm:p-5 pb-2">
          <CardTitle className="text-sm sm:text-base font-bold flex items-center gap-2 text-foreground">
            <LayoutTemplate className="size-4.5 text-purple-600 dark:text-purple-400" />
            <span>{t('yomitan.template_header')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-4 sm:p-5 pt-0 space-y-3">
          <p className="text-xs text-muted-foreground leading-relaxed">
            Trong Yomitan Settings ➔ <strong>Configure card templates...</strong>, hãy gán các marker sau vào từng trường của bộ thẻ:
          </p>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 pt-1">
            <div
              onClick={() => copy('{expression}', '{expression}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Trường 1 (Từ vựng / Kanji)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{expression}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{expression}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>

            <div
              onClick={() => copy('{furigana}', '{furigana}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Trường 2 (Furigana / Cách đọc)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{furigana}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{furigana}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>

            <div
              onClick={() => copy('{glossary}', '{glossary}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Trường 3 (Ý nghĩa định nghĩa)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{glossary}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{glossary}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>

            <div
              onClick={() => copy('{audio}', '{audio}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Trường 4 (Âm thanh phát âm)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{audio}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{audio}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>

            <div
              onClick={() => copy('{sentence}', '{sentence}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Trường 5 (Câu ví dụ ngữ cảnh)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{sentence}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{sentence}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>

            <div
              onClick={() => copy('{character}', '{character}')}
              className="flex items-center justify-between p-2.5 rounded-xl border bg-card/80 hover:border-purple-500/50 cursor-pointer transition-all group"
            >
              <div className="space-y-0.5">
                <span className="text-[11px] text-muted-foreground block">Thẻ Kanji (Chữ Hán duy nhất)</span>
                <code className="font-mono text-xs font-bold text-purple-600 dark:text-purple-400">{'{character}'}</code>
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-primary transition-colors flex items-center gap-1">
                {copied === '{character}' ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Interactive Explorer Card */}
      <Card className="rounded-2xl border shadow-2xs min-w-0 overflow-hidden">
        <CardHeader className="p-4 sm:p-6 space-y-4 min-w-0">
          <div>
            <CardTitle className="text-base sm:text-lg font-bold flex items-center gap-2">
              <Code className="size-5 text-purple-500 shrink-0" />
              <span>{t('yomitan.explorer_title')}</span>
            </CardTitle>
            <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
              Nhấp vào bất kỳ thẻ marker nào dưới đây để sao chép nhanh mã thẻ vào bộ nhớ tạm.
            </p>
          </div>

          <div className="flex flex-col md:flex-row gap-3 pt-1 w-full min-w-0">
            <div className="relative flex-1 min-w-0">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <Input
                placeholder={t('yomitan.search_placeholder')}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-10 rounded-xl text-xs sm:text-sm w-full"
              />
            </div>
            <div className="flex gap-1.5 overflow-x-auto pb-1 md:pb-0 no-scrollbar max-w-full shrink-0">
              <Button
                size="sm"
                variant={selectedCategory === 'all' ? 'default' : 'outline'}
                onClick={() => setSelectedCategory('all')}
                className="rounded-xl text-xs h-9 px-3 shrink-0"
              >
                {t('yomitan.category_all')} ({YOMITAN_MARKERS.length})
              </Button>
              <Button
                size="sm"
                variant={selectedCategory === 'term' ? 'default' : 'outline'}
                onClick={() => setSelectedCategory('term')}
                className="rounded-xl text-xs h-9 px-3 shrink-0"
              >
                Từ vựng ({countTerm})
              </Button>
              <Button
                size="sm"
                variant={selectedCategory === 'kanji' ? 'default' : 'outline'}
                onClick={() => setSelectedCategory('kanji')}
                className="rounded-xl text-xs h-9 px-3 shrink-0"
              >
                Chữ Hán ({countKanji})
              </Button>
              <Button
                size="sm"
                variant={selectedCategory === 'both' ? 'default' : 'outline'}
                onClick={() => setSelectedCategory('both')}
                className="rounded-xl text-xs h-9 px-3 shrink-0"
              >
                Dùng chung ({countBoth})
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-4 sm:p-6 pt-0 min-w-0">
          {!filteredMarkers.length ? (
            <EmptyState
              title="Không tìm thấy marker phù hợp"
              description="Hãy thử thay đổi từ khóa tìm kiếm hoặc chọn danh mục khác."
            />
          ) : (
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 min-w-0">
              {filteredMarkers.map((marker) => (
                <div
                  key={marker.name}
                  onClick={() => copy(marker.name, marker.name)}
                  className="group relative flex flex-col justify-between gap-3 rounded-2xl border bg-card p-3.5 sm:p-4 transition-all hover:border-purple-500/50 hover:shadow-md cursor-pointer active:scale-[0.99] min-w-0 overflow-hidden"
                >
                  <div className="space-y-2.5 min-w-0">
                    <div className="flex flex-wrap items-start justify-between gap-2 min-w-0">
                      <div className="min-w-0 flex-1">
                        <code className="font-mono text-xs sm:text-sm font-bold text-purple-600 dark:text-purple-400 bg-purple-500/10 px-2 sm:px-2.5 py-1 rounded-lg group-hover:bg-purple-600 group-hover:text-white transition-colors break-all inline-block max-w-full">
                          {marker.name}
                        </code>
                      </div>
                      <Badge
                        variant="outline"
                        className="text-[10px] uppercase font-semibold tracking-wide shrink-0 self-start mt-0.5"
                      >
                        {marker.category === 'term'
                          ? 'Từ vựng'
                          : marker.category === 'kanji'
                          ? 'Chữ Hán'
                          : 'Dùng chung'}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed break-words">{marker.description}</p>
                  </div>

                  {marker.example ? (
                    <div className="pt-2 border-t flex items-center justify-between text-[11px] text-muted-foreground min-w-0 gap-2">
                      <span className="truncate min-w-0 flex-1">Ví dụ: <code className="text-foreground bg-muted px-1.5 py-0.5 rounded font-mono break-all">{marker.example}</code></span>
                      <span className="text-xs opacity-80 group-hover:opacity-100 transition-opacity text-purple-600 dark:text-purple-400 font-semibold flex items-center gap-1 shrink-0">
                        {copied === marker.name ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
                        {copied === marker.name ? t('article.copied') : t('article.copy_code')}
                      </span>
                    </div>
                  ) : (
                    <div className="flex justify-end text-[11px] pt-1">
                      <span className="text-xs opacity-80 group-hover:opacity-100 transition-opacity text-purple-600 dark:text-purple-400 font-semibold flex items-center gap-1">
                        {copied === marker.name ? <Check className="size-3 text-green-600" /> : <Copy className="size-3" />}
                        {copied === marker.name ? t('article.copied') : t('article.copy_code')}
                      </span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
