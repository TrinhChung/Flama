import type { TourStep } from '@/shared/components/SpotlightTour'

export function getNoteTypeManagerTourSteps(
  hasNoteTypes: boolean,
  t?: any
): TourStep[] {
  const tr = (key: string, fallback: string) => (t ? t(key, fallback) : fallback)

  const steps: TourStep[] = [
    {
      target: '[data-tour="create-input"]',
      title: tr('manager_tour.step1_title', '📝 1. Nhập Tên Loại Thẻ Mới'),
      content: tr('manager_tour.step1_desc', 'Nhập tên loại thẻ bạn muốn tạo (Ví dụ: Từ vựng N3, Ngữ pháp N2, Kanji Hán Tự) vào ô này.'),
      placement: 'bottom',
    },
    {
      target: '[data-tour="create-button"]',
      title: tr('manager_tour.step2_title', '🚀 2. Bấm Tạo NoteType'),
      content: tr('manager_tour.step2_desc', 'Bấm nút này để khởi tạo loại thẻ. Hệ thống sẽ tự động chuyển bạn sang trang Quản lý Trường (Fields) để thêm cột dữ liệu.'),
      placement: 'bottom',
    },
    {
      target: '[data-tour="ai-prompt-btn"]',
      title: tr('manager_tour.step3_title', '🤖 3. Hướng Dẫn & Prompt AI'),
      content: tr(
        'manager_tour.step3_desc',
        'Không cần biết lập trình! Bấm nút này để mở trang hướng dẫn và sao chép Master Prompt cho ChatGPT / Claude tự thiết kế mẫu thẻ cho bạn.'
      ),
      placement: 'bottom',
    },
  ]

  if (hasNoteTypes) {
    steps.push(
      {
        target: '[data-tour="card-first"]',
        title: tr('manager_tour.step4_cards_title', '📇 4. Thẻ NoteType & Huy Hiệu Thông Số'),
        content: tr(
          'manager_tour.step4_cards_desc',
          'Mỗi thẻ hiển thị tên loại thẻ cùng 2 huy hiệu quan trọng: số lượng Template (các mặt thẻ hiển thị) và số lượng Trường dữ liệu hiện có trong bộ thẻ.'
        ),
        placement: 'top',
      },
      {
        target: '[data-tour="card-view-btn"]',
        title: tr('manager_tour.step5_view_title', '👁️ 5. Nút "Xem" (Thiết Lập & Quản Lý Cấu Trúc Thẻ)'),
        content: tr(
          'manager_tour.step5_view_desc',
          'Bấm nút Xem để mở giao diện quản lý: thiết lập các Trường (Fields), tùy chỉnh Giao diện (Templates), xem trước và chia sẻ hoặc xóa cấu trúc thẻ.'
        ),
        placement: 'top',
      },
    )
  } else {
    steps.push({
      target: '[data-tour="notetype-grid-area"]',
      title: tr('manager_tour.step4_empty_title', '📋 4. Khu Vực Danh Sách Loại Thẻ'),
      content: tr(
        'manager_tour.step4_empty_desc',
        'Sau khi tạo loại thẻ, các thẻ NoteType sẽ xuất hiện tại đây kèm các nút chức năng: Quản lý Trường (Fields), Tùy chỉnh Template (HTML/CSS), Xem trước Live Preview và Chia sẻ lên Kho Marketplace.'
      ),
      placement: 'top',
    })
  }

  return steps
}
