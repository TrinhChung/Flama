import { useMemo } from 'react'
import { SpotlightTour, type TourStep } from '@/shared/components/SpotlightTour'

interface DashboardSpotlightTourProps {
  isOpen: boolean
  onClose: () => void
  onComplete?: () => void
  hasDecks: boolean
}

export function DashboardSpotlightTour({
  isOpen,
  onClose,
  onComplete,
  hasDecks,
}: DashboardSpotlightTourProps) {
  const steps: TourStep[] = useMemo(() => {
    const list: TourStep[] = [
      {
        target: '[data-tour="dash-toolbar-nav"]',
        title: '🧭 1. Thanh Công Cụ Điều Hướng',
        content:
          'Chuyển nhanh giữa danh sách bộ thẻ (Decks), phiên học ngắt quãng (Study), thống kê thời gian học (Stats), nhập dữ liệu từ Anki (Import), và tra cứu từ vựng (Browse).',
        placement: 'bottom',
      },
      {
        target: '[data-tour="dash-create-btn"]',
        title: '✨ 2. Tạo Bộ Thẻ Tùy Chỉnh',
        content:
          'Tự tạo bộ thẻ mới của riêng bạn. Bạn có thể xây dựng cây thư mục nhiều cấp cha-con (sub-decks) và tùy biến các trường dữ liệu theo ý muốn.',
        placement: 'bottom',
      },
      {
        target: '[data-tour="dash-deck-board"]',
        title: '📊 3. Bảng Quản Lý Deck & 3 Chỉ Số',
        content:
          'Theo dõi tiến độ qua 3 cột: Xanh lá (New - thẻ mới chưa học), Đỏ (Learn - thẻ đang ghi nhớ ngắn hạn), và Cam (Due - thẻ đến hạn ôn tập hôm nay theo thuật toán Spaced Repetition).',
        placement: 'top',
      },
    ]

    if (hasDecks) {
      list.push(
        {
          target: '[data-tour="dash-deck-row-first"]',
          title: '🎴 4. Chọn Bộ Thẻ Để Học',
          content:
            'Click vào bất kỳ bộ thẻ nào để chọn học hoặc nhấn icon bánh răng để đổi tên, đổi vị trí, xuất bản hoặc cài đặt lại tiến độ.',
          placement: 'top',
        },
        {
          target: '[data-tour="dash-study-action"]',
          title: '⚡ 5. Bắt Đầu Phiên Học Ngay',
          content:
            'Bấm nút Study để vào ngay phiên học Spaced Repetition. Sử dụng phím Space để lật mặt thẻ và các phím 1 (Again), 2 (Hard), 3 (Good), 4 (Easy) để đánh giá.',
          placement: 'bottom',
        },
      )
    }

    list.push(
      {
        target: '[data-tour="dash-marketplace-link"]',
        title: '📚 6. Khám Phá Thư Viện Marketplace',
        content:
          'Khám phá kho học liệu phong phú: Tiếng Nhật JLPT, Tiếng Anh TOEIC/IELTS, Tiếng Hàn TOPIK, Tiếng Trung HSK, CNTT & Lập trình với tính năng cài đặt 1-click.',
        placement: 'top',
      },
      {
        target: '[data-tour="dash-heatmap-section"]',
        title: '🔥 7. Bản Đồ Nhiệt & Chuỗi Ngày Học (Streak)',
        content:
          'Theo dõi chuỗi ngày học liên tục (Streak), tổng thời gian ôn tập và số lượng thẻ đã hoàn thành theo từng ngày trong năm.',
        placement: 'top',
      },
      {
        target: '[data-tour="dash-tour-btn"]',
        title: '🎯 8. Hướng Dẫn & Thiết Lập Mục Tiêu',
        content:
          'Bạn có thể bấm vào đây để xem lại tour hoặc điều chỉnh mục tiêu học tập bất kỳ lúc nào. Chúc bạn học tập thật hiệu quả cùng Flama!',
        placement: 'bottom',
      },
    )

    return list
  }, [hasDecks])

  return (
    <SpotlightTour
      steps={steps}
      isOpen={isOpen}
      onClose={onClose}
      onComplete={onComplete}
    />
  )
}
