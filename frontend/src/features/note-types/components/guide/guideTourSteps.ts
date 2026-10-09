import type { TourStep } from '@/shared/components/SpotlightTour'

export const GUIDE_STORAGE_KEY = 'flama_guide_spotlight_tour_v1'

export function getGuideTourSteps(t?: any): TourStep[] {
  const tr = (key: string, fallback: string) => (t ? t(key, fallback) : fallback)

  return [
    {
      target: '[data-tour="guide-header"]',
      title: tr('guide_tour.step1_title', '📘 1. Trung Tâm Hướng Dẫn & Prompt AI'),
      content: tr(
        'guide_tour.step1_desc',
        'Trang tài liệu toàn diện này giúp bạn tạo ra bất kỳ mẫu Flashcard nào ưng ý cho Flama mà không cần biết viết code.'
      ),
      placement: 'bottom',
    },
    {
      target: '[data-tour="guide-tabs"]',
      title: tr('guide_tour.step2_title', '📑 2. Điều Hướng Các Chủ Đề Hướng Dẫn'),
      content: tr(
        'guide_tour.step2_desc',
        'Chuyển nhanh giữa 4 chuyên mục: Prompt AI Mẫu, Công Nghệ Thẻ, Quy Trình 4 Bước và Quy Tắc Vàng Tránh Lỗi.'
      ),
      placement: 'bottom',
    },
    {
      target: '[data-tour="guide-master-prompt"]',
      title: tr('guide_tour.step3_title', '🤖 3. Master Prompt Chuẩn Hóa Cho AI'),
      content: tr(
        'guide_tour.step3_desc',
        'Bấm nút "Sao Chép Toàn Bộ Prompt" để copy mẫu chỉ thị chuẩn rồi gửi cho ChatGPT / Claude / Gemini tạo sẵn HTML/CSS cho bạn.'
      ),
      placement: 'bottom',
    },
    {
      target: '[data-tour="guide-example-prompts"]',
      title: tr('guide_tour.step4_title', '💡 4. Các Mẫu Yêu Cầu Thực Tế'),
      content: tr(
        'guide_tour.step4_desc',
        'Tham khảo và sao chép nhanh các prompt mẫu cho Thẻ Từ Vựng hoặc Thẻ Ngữ Pháp JLPT có sẵn.'
      ),
      placement: 'top',
    },
    {
      target: '[data-tour="guide-start-btn"]',
      title: tr('guide_tour.step5_title', '🚀 5. Bắt Đầu Tạo Note Type Ngay'),
      content: tr(
        'guide_tour.step5_desc',
        'Sau khi có mã code từ AI, bấm nút này để quay lại trang Quản lý Loại Thẻ và áp dụng mẫu thiết kế của bạn.'
      ),
      placement: 'bottom',
    },
  ]
}

export const GUIDE_TOUR_STEPS: TourStep[] = getGuideTourSteps()
