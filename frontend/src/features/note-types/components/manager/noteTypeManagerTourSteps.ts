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
        target: '[data-tour="card-fields-btn"]',
        title: tr('manager_tour.step5_fields_title', '⚙️ 5. Nút "Trường" (Quản Lý Cột Dữ Liệu)'),
        content: tr(
          'manager_tour.step5_fields_desc',
          'Bấm vào đây để thêm các trường như Word, Meaning, Audio, Example, Furigana... định hình cấu trúc dữ liệu lưu trữ cho thẻ.'
        ),
        placement: 'top',
      },
      {
        target: '[data-tour="card-template-btn"]',
        title: tr('manager_tour.step6_templates_title', '🎨 6. Nút "Templates" (Soạn Giao Diện & Xem Trước)'),
        content: tr(
          'manager_tour.step6_templates_desc',
          'Bấm vào đây để mở trình soạn thảo HTML/CSS Front & Back, dán mã code tạo bởi AI và xem mô phỏng thẻ mẫu (Live Preview) theo thời gian thực.'
        ),
        placement: 'top',
      },
      {
        target: '[data-tour="card-share-btn"]',
        title: tr('manager_tour.step7_share_title', '🌐 7. Nút "Chia Sẻ" Lên Kho Cộng Đồng'),
        content: tr(
          'manager_tour.step7_share_desc',
          'Khi đã thiết kế xong mẫu thẻ ưng ý, bạn có thể bấm nút này để xuất bản lên Marketplace cho cộng đồng Flama cùng sử dụng.'
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
