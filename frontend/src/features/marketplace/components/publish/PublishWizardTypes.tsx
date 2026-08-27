import { BookOpen, DollarSign, Sparkles, Target, AlertCircle } from 'lucide-react'

export const WIZARD_STEPS = [
  { id: 1, title: 'Học liệu & Tiêu đề', sub: 'Chọn bộ thẻ và mô tả', icon: BookOpen },
  { id: 2, title: 'Phân loại & Trình độ', sub: 'Chứng chỉ & Môn học', icon: Sparkles },
  { id: 3, title: 'Mục tiêu & Kỹ năng', sub: 'Goals & Chủ đề trọng tâm', icon: Target },
  { id: 4, title: 'Giá bán & Đăng tải', sub: 'Thiết lập giá và xuất bản', icon: DollarSign },
]

export function FieldErrorMessage({ error }: { error?: string }) {
  if (!error) return null
  return (
    <p className="text-xs font-semibold text-destructive mt-1.5 flex items-center gap-1.5 animate-in fade-in">
      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
      <span>{error}</span>
    </p>
  )
}
