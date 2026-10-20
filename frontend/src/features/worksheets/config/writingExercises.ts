/** Copy and toggles of the sentence-writing and grammar-practice layout controls. */
export interface WritingExerciseCopy {
  title: string
  promptLabel: string
  promptDefault: string
  promptPlaceholder: string
  promptSuggestions: string[]
  linesLabel: string
  linesHint?: string
  toggles: {
    field: 'show_sample_sentence' | 'show_sample_reading' | 'show_sample_meaning' | 'show_explanation' | 'show_example_hint'
    label: string
  }[]
}

export const SENTENCE_WRITING_COPY: WritingExerciseCopy = {
  title: 'Tuỳ biến Mẫu câu & Dòng kẻ viết tay',
  promptLabel: 'Đề bài / Yêu cầu của bài tập (Đầu trang):',
  promptDefault: 'Dịch các câu sau sang tiếng Việt hoặc phát triển thành đoạn văn:',
  promptPlaceholder: 'Ví dụ: Dịch câu sang tiếng Việt, Viết phát triển thành đoạn văn...',
  promptSuggestions: [
    'Dịch các câu sau sang tiếng Việt:',
    'Viết lại mỗi câu 3 lần:',
    'Đặt câu mới sử dụng cấu trúc mẫu:',
    'Nghe & chép chính tả (Dictation):',
  ],
  linesLabel: 'Số dòng kẻ viết tay mỗi câu:',
  linesHint: 'Tăng số dòng nếu yêu cầu học sinh viết cả đoạn văn hoặc dịch câu dài.',
  toggles: [
    { field: 'show_sample_sentence', label: 'Hiện câu mẫu' },
    { field: 'show_sample_reading', label: 'Hiện cách đọc / Furigana' },
    { field: 'show_sample_meaning', label: 'Hiện ý nghĩa (Tắt để bắt học sinh tự dịch)' },
  ],
}

export const GRAMMAR_PRACTICE_COPY: WritingExerciseCopy = {
  title: 'Tuỳ biến Bài tập Ngữ pháp & Đề bài',
  promptLabel: 'Đề bài / Yêu cầu của giáo viên:',
  promptDefault: 'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:',
  promptPlaceholder: 'Ví dụ: Đặt 2 câu với cấu trúc trên, Dịch sang tiếng Nhật...',
  promptSuggestions: [
    'Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:',
    'Viết đoạn văn ngắn (3-4 câu) áp dụng ngữ pháp:',
    'Dịch các câu ví dụ sang tiếng Việt:',
    'Tìm lỗi sai và viết lại câu đúng:',
  ],
  linesLabel: 'Số dòng kẻ viết bài mỗi mục:',
  toggles: [
    { field: 'show_explanation', label: 'Hiện giải thích cách dùng / ý nghĩa' },
    { field: 'show_example_hint', label: 'Hiện câu ví dụ mẫu gợi ý' },
  ],
}
