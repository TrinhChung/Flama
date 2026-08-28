import type { GuideCategory, GuideArticle } from './types'

export const GUIDE_CATEGORIES: GuideCategory[] = [
  {
    slug: 'getting-started',
    title: 'Bắt đầu Nhanh',
    description: 'Quy trình 3 phút làm quen và bắt đầu phiên học Flashcard đầu tiên.',
    iconName: 'Sparkles',
    articles: [
      {
        slug: 'getting-started',
        title: '3 Phút Bắt Đầu Phiên Học Đầu Tiên',
        shortDescription: 'Hướng dẫn từng bước giúp bạn chọn bài học, làm quen thao tác lật thẻ và hoàn thành phiên học đầu tiên.',
        categorySlug: 'getting-started',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        intro: 'Hệ thống học tập Flama được thiết kế tối ưu hóa cho người học ngôn ngữ. Bạn không cần phải thiết lập kỹ thuật phức tạp để có thể bắt đầu học và ghi nhớ từ vựng ngay lập tức.',
        steps: [
          {
            title: 'Bước 1: Chọn hoặc tạo bài học đầu tiên',
            description: 'Tại Bảng điều khiển (Dashboard), bạn có thể chọn một bộ thẻ có sẵn hoặc vào Marketplace tải về bộ thẻ chuẩn JLPT N5/N4. Ngoài ra bạn có thể bấm nút "Tạo bộ thẻ" để tự tạo bộ từ vựng của riêng mình.',
            badge: 'Dashboard',
            tip: 'Nếu tự tạo bộ thẻ, hãy đặt tên theo cấu trúc phân cấp (ví dụ: Tiếng Nhật::N5::Bài 01) để danh mục luôn ngăn nắp.',
          },
          {
            title: 'Bước 2: Thêm từ vựng đầu tiên',
            description: 'Nhấn vào biểu tượng dấu cộng (+) tại bộ thẻ để mở cửa sổ thêm thẻ. Nhập Chữ Hán (Kanji), Cách đọc (Hiragana) và Ý nghĩa tiếng Việt.',
            badge: 'Tạo thẻ',
            tip: 'Bạn chỉ cần nhập 1 lần, hệ thống sẽ tự động tạo thẻ hỏi 2 chiều (Kanji -> Nghĩa và Nghĩa -> Kanji).',
          },
          {
            title: 'Bước 3: Thực hiện phiên học',
            description: 'Bấm nút "Học ngay". Quan sát câu hỏi mặt trước, tự gợi nhớ đáp án trong đầu rồi bấm phím Space (hoặc Enter) để lật mở đáp án.',
            badge: 'Phòng học',
          },
          {
            title: 'Bước 4: Tự chấm điểm trung thực',
            description: 'Chọn 1 trong 4 mức độ: 1 - Học lại (Again), 2 - Khó (Hard), 3 - Tốt (Good), 4 - Dễ (Easy). Thuật toán sẽ tự động lên lịch nhắc lại vào thời điểm não bộ sắp quên.',
            badge: 'Đánh giá',
            tip: 'Khuyến nghị: Luôn chọn số 3 (Good) cho các thẻ bạn nhớ đúng và phản xạ bình thường.',
          },
        ],
        keyTakeaways: [
          'Học đều đặn mỗi ngày từ 10 - 20 thẻ mới để duy trì chuỗi học Streak.',
          'Mốc chốt ngày mới của Flama là 4:00 sáng, cho phép bạn học khuya mà không bị mất chuỗi.',
        ],
        troubleshootingSlug: 'dashboard-study',
      },
      {
        slug: 'core-concepts',
        title: 'Các Khái Niệm Cốt Lõi: Bộ Thẻ, Ghi Chú, Thẻ & SRS',
        shortDescription: 'Hiểu rõ nguyên lý hoạt động của Bộ thẻ, Ghi chú dữ liệu (Note), Thẻ hiển thị (Card) và Thuật toán Spaced Repetition.',
        categorySlug: 'getting-started',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        intro: 'Để khai thác tối đa sức mạnh của Flama, việc nắm vững cấu trúc tổ chức dữ liệu sẽ giúp bạn tiết kiệm hàng trăm giờ học tập.',
        detailedSections: [
          {
            title: '1. Bộ thẻ (Deck)',
            content: 'Bộ thẻ là thùng chứa dùng để phân loại học liệu theo cấp độ, giáo trình hoặc chủ đề. Bạn có thể lồng ghép nhiều bộ thẻ con vào bộ thẻ cha bằng cú pháp hai dấu hai chấm (::).',
          },
          {
            title: '2. Ghi chú dữ liệu (Note) vs Thẻ hiển thị (Card)',
            content: 'Đây là kiến trúc 1-to-Many mạnh mẽ của Flama: Bạn chỉ cần nhập dữ liệu một lần vào Ghi chú (Note), hệ thống sẽ tự động sinh ra các Thẻ (Card) tương ứng để học hai chiều. Tiến độ học của từng thẻ là hoàn toàn độc lập.',
          },
          {
            title: '3. Thuật toán Lặp lại Ngắt quãng (Spaced Repetition System - SRS)',
            content: 'Não bộ con người quên lãng kiến thức theo một đường cong quy luật. SRS tự động tính toán thời điểm chính xác khi trí nhớ của bạn sắp phai mờ để đưa thẻ ra ôn tập, giúp ghi nhớ vĩnh viễn với số lần lặp ít nhất.',
          },
        ],
        keyTakeaways: [
          'Ghi chú (Note) lưu giữ dữ liệu gốc, Thẻ (Card) là đơn vị hiển thị để bạn ôn tập.',
          'Không bao giờ cần tự nhớ lịch ôn — hệ thống sẽ tự động chuẩn bị danh sách thẻ Due mỗi ngày.',
        ],
      },
    ],
  },
  {
    slug: 'dashboard',
    title: 'Bảng Điều Khiển & Quản Lý Bộ Thẻ',
    description: 'Tổ chức cây bộ thẻ phân cấp, theo dõi chỉ số học tập, chuỗi Streak và dự báo ôn tập.',
    iconName: 'LayoutDashboard',
    articles: [
      {
        slug: 'overview',
        title: 'Tổng Quan Bảng Điều Khiển & Chu Trình Học Mỗi Ngày',
        shortDescription: 'Làm quen với các khu vực chức năng trên Bảng điều khiển, thanh tác vụ nhanh và lịch trình học tập.',
        categorySlug: 'dashboard',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        intro: 'Bảng điều khiển là trung tâm điều phối toàn bộ hoạt động học tập hàng ngày của bạn trên Flama.',
        detailedSections: [
          {
            title: '1. Thanh Chỉ Số Học Tập Trong Ngày',
            content: 'Hiển thị tổng số thẻ bạn đã học trong ngày, mục tiêu ngày đã hoàn thành được bao nhiêu phần trăm và chuỗi ngày học liên tục (Streak).',
          },
          {
            title: '2. Cây Danh Mục Bộ Thẻ (Deck Tree)',
            content: 'Liệt kê danh sách tất cả các bộ thẻ của bạn kèm 3 con số phân loại theo màu sắc: Xanh dương (Thẻ mới), Đỏ/Cam (Đang học trong ngày), Xanh lá (Đến hạn ôn tập).',
          },
          {
            title: '3. Thanh Tác Vụ Nhanh (Quick Actions)',
            content: 'Nút "Học ngay", "Thêm thẻ (+)", "Duyệt thư viện", "Nhập file", "Kho học liệu" giúp bạn thao tác tức thì.',
          },
        ],
        troubleshootingSlug: 'dashboard-study',
      },
      {
        slug: 'deck-grouping',
        title: 'Gom Nhóm Bộ Thẻ Phân Cấp Bằng Dấu `::` (Subdecks)',
        shortDescription: 'Cách tạo cây thư mục nhiều cấp (Deck Tree) ngăn nắp và cơ chế học gộp từ thư mục cha.',
        categorySlug: 'dashboard',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        intro: 'Khi học nhiều giáo trình hoặc chủ đề, việc sắp xếp bộ thẻ phân cấp giúp màn hình học tập của bạn luôn khoa học và gọn gàng như mục lục một cuốn sách.',
        steps: [
          {
            title: 'Bước 1: Đặt tên bộ thẻ có chứa dấu `::`',
            description: 'Khi tạo mới hoặc đổi tên bộ thẻ, sử dụng hai dấu hai chấm liền nhau `::` để phân cách các cấp cha con.',
            tip: 'Ví dụ: "Tiếng Nhật::N3::Soumatome::Tuần 1 Ngày 1"',
          },
          {
            title: 'Bước 2: Hệ thống tự động tạo Cây Thư mục',
            description: 'Flama sẽ tự động nhóm các bộ thẻ có cùng tiền tố lại thành một cây phân cấp có thể mở rộng hoặc thu gọn.',
          },
          {
            title: 'Bước 3: Chọn phạm vi học tập linh hoạt',
            description: 'Bạn có thể chọn học riêng một bài học con hoặc bấm "Học" tại thư mục cha để ôn tập tổng hợp toàn bộ các nhánh con bên dưới.',
          },
        ],
        detailedSections: [
          {
            title: 'Cơ Chế Đếm Gộp Số Lượng (Aggregated Counters)',
            content: 'Các con số hiển thị ở dòng bộ thẻ cha là tổng số lượng thẻ cần học của chính nó cộng với tất cả các nhánh con cháu bên dưới. Bạn có thể theo dõi tiến độ tổng thể dễ dàng.',
          },
          {
            title: 'Học Bộ Thẻ Cha vs Học Bộ Thẻ Con',
            content: 'Nhấn nút Học ở cấp cha: Hệ thống gom tất cả các thẻ đến hạn của toàn bộ các bài học con. Nhấn nút Học ở cấp con: Phiên học chỉ giới hạn đúng trong phạm vi bài học con đó.',
          },
        ],
        keyTakeaways: [
          'Dùng `::` không giới hạn số cấp thư mục (Ví dụ: Ngôn ngữ::Tiếng Nhật::N2::Từ vựng).',
          'Đổi tên thư mục cha sẽ tự động cập nhật đường dẫn cho toàn bộ các thư mục con.',
        ],
      },
      {
        slug: 'deck-management',
        title: 'Quản Trị, Ghim & Thiết Lập Giới Hạn Bộ Thẻ',
        shortDescription: 'Cấu hình số thẻ mới mỗi ngày, giới hạn ôn tập, ghim bài học quan trọng và quản lý dữ liệu an toàn.',
        categorySlug: 'dashboard',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        params: [
          {
            name: 'Số thẻ mới mỗi ngày (New Cards/Day)',
            type: 'number',
            defaultValue: '20',
            description: 'Số lượng thẻ mới tối đa được đưa vào học mỗi ngày. Khuyến nghị: 15 - 25 thẻ để tránh quá tải ôn tập sau 1-2 tuần.',
          },
          {
            name: 'Số lượt ôn tập tối đa (Max Reviews/Day)',
            type: 'number',
            defaultValue: '200',
            description: 'Trần số lượng thẻ đến hạn cần ôn tập trong một ngày nhằm kiểm soát thời lượng học.',
          },
          {
            name: 'Ghim bộ thẻ (Pinned)',
            type: 'boolean',
            defaultValue: 'false',
            description: 'Đưa bộ thẻ ưu tiên lên đầu danh sách trên Bảng điều khiển để truy cập nhanh.',
          },
        ],
        detailedSections: [
          {
            title: 'Xóa Bộ Thẻ An Toàn',
            content: 'Khi xóa bộ thẻ, bạn có thể chọn xóa chỉ bộ thẻ (các thẻ bên trong được chuyển về bộ thẻ Mặc định) hoặc xóa toàn bộ thẻ học liên quan.',
          },
        ],
      },
      {
        slug: 'study-metrics',
        title: 'Giải Mã Các Chỉ Số Thống Kê: New, Learn, Due & Streak',
        shortDescription: 'Ý nghĩa 3 nhóm màu sắc, cách tính chuỗi ngày học Streak (mốc 4:00 sáng), tỷ lệ ghi nhớ và biểu đồ dự báo.',
        categorySlug: 'dashboard',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: '1. Ba Nhóm Màu Sắc Trạng Thái Thẻ',
            content: '• Màu Xanh Dương (New): Thẻ mới tinh chưa từng học lần nào.\n• Màu Đỏ / Cam (Learn): Thẻ đang trong các bước học ban đầu hoặc vừa bị đánh giá sai (Again), chờ hoàn thành trong ngày.\n• Màu Xanh Lá (Due): Thẻ đã tốt nghiệp giai đoạn học ban đầu, hôm nay đến hạn ôn tập định kỳ theo thuật toán SRS.',
          },
          {
            title: '2. Quy Tắc Tính Chuỗi Ngày Học (Streak)',
            content: 'Chuỗi ngày học tăng thêm 1 khi bạn hoàn thành ít nhất một phiên học trong ngày. Mốc chuyển ngày mới của hệ thống là 4:00 SÁNG (Day Boundary Cutoff) — giúp người học thức khuya sau 12h đêm không bao giờ bị đứt chuỗi Streak.',
          },
          {
            title: '3. Tỷ Lệ Ghi Nhớ (Retention Rate) & Dự Báo Ôn Tập',
            content: 'Tỷ lệ % số lần đánh giá thành công (Good / Easy) trên tổng số lượt ôn tập thẻ Due. Mức tối ưu lý tưởng theo chuẩn Spaced Repetition là 85% - 90%. Biểu đồ Dự báo ôn tập tại trang /statistics giúp bạn biết trước khối lượng thẻ cần ôn trong 7 ngày tới.',
          },
        ],
      },
    ],
  },
  {
    slug: 'study',
    title: 'Phòng Học Flashcard & Ôn Tập',
    description: 'Quy trình học tiêu chuẩn, nguyên tắc 4 mức đánh giá, bảng phím tắt và tùy biến Furigana/Audio.',
    iconName: 'GraduationCap',
    articles: [
      {
        slug: 'flashcard-flow',
        title: 'Quy Trình Học Tiêu Chuẩn & Nguyên Tắc 4 Mức Đánh Giá',
        shortDescription: 'Cách lật thẻ, tự đánh giá mức độ ghi nhớ trung thực để thuật toán SRS lên lịch tối ưu nhất.',
        categorySlug: 'study',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Quan sát mặt trước (Question)',
            description: 'Đọc câu hỏi, thử tự gợi nhớ cách phát âm Kanji, ngữ nghĩa và ngữ cảnh câu ví dụ trong tâm trí.',
          },
          {
            title: 'Bước 2: Lật mở mặt sau (Show Answer)',
            description: 'Nhấn phím Space hoặc Enter để đối chiếu đáp án mặt sau kèm phát âm mẫu.',
          },
          {
            title: 'Bước 3: Tự chấm điểm theo 4 mức độ',
            description: '1 - Học lại (Again): Quên hoặc nhớ sai nghĩa.\n2 - Khó (Hard): Nhớ đúng nhưng mất nhiều giây ngập ngừng.\n3 - Tốt (Good): Nhớ chính xác và tự tin.\n4 - Dễ (Easy): Quá thuộc, phản xạ tức thì.',
          },
        ],
        keyTakeaways: [
          'Hãy trung thực khi chấm điểm: Đừng ngại bấm số 1 (Again) khi nhớ sai, vì việc lặp lại sớm là chìa khóa khắc sâu trí nhớ.',
          'Sử dụng phím tắt Ctrl + Z bất cứ lúc nào nếu lỡ tay bấm nhầm điểm.',
        ],
      },
      {
        slug: 'spaced-repetition',
        title: 'Cơ Chế Thuật Toán Lặp Lại Ngắt Quãng (Spaced Repetition)',
        shortDescription: 'Vòng đời của thẻ: Giai đoạn Học ban đầu (Learning) ➔ Tốt nghiệp (Graduated) ➔ Ôn tập định kỳ (Review).',
        categorySlug: 'study',
        readTimeMinutes: 5,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Vòng Đời Của Thẻ Học',
            content: '1. Thẻ Mới (New): Chưa từng học.\n2. Đang học (Learning): Trải qua các bước đệm (ví dụ: 1 phút ➔ 10 phút) để đưa vào trí nhớ ngắn hạn.\n3. Tốt nghiệp (Graduated): Chuyển sang lịch ôn ngắt quãng (1 ngày ➔ 3 ngày ➔ 7 ngày ➔ 20 ngày ➔ vài tháng).\n4. Tái học (Relearning): Khi bạn bấm Again trên thẻ đã tốt nghiệp, thẻ sẽ quay lại bước học ngắn để củng cố trước khi tiếp tục chu kỳ ôn tập.',
          },
          {
            title: 'Hệ Số Độ Khó (Ease Factor)',
            content: 'Mỗi thẻ có một hệ số độ khó riêng. Khi bạn bấm Easy, khoảng cách tăng theo cấp số nhân nhanh hơn; khi bấm Hard, khoảng cách tăng chậm hơn để đảm bảo bạn không bị quên.',
          },
        ],
      },
      {
        slug: 'shortcuts',
        title: 'Bảng Tra Cứu Phím Tắt Bàn Phím Khi Học Flashcard',
        shortDescription: 'Tăng tốc độ học gấp 3 lần với hệ thống phím tắt đầy đủ cho mọi thao tác trong phòng học.',
        categorySlug: 'study',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        shortcuts: [
          { key: 'Space / Enter', action: 'Lật thẻ', description: 'Lật mở mặt sau của thẻ học' },
          { key: '1', action: 'Học lại (Again)', description: 'Chưa thuộc, đưa thẻ lặp lại trong phiên' },
          { key: '2', action: 'Khó (Hard)', description: 'Nhớ khó khăn, tăng khoảng cách nhẹ' },
          { key: '3', action: 'Tốt (Good)', description: 'Mức chuẩn khuyến nghị cho đáp án đúng' },
          { key: '4', action: 'Dễ (Easy)', description: 'Nhớ xuất sắc, tăng khoảng cách nhảy vọt' },
          { key: 'R / F5', action: 'Phát lại âm thanh', description: 'Nghe lại phát âm tiếng Nhật của thẻ' },
          { key: 'Ctrl + Z / Z', action: 'Hoàn tác (Undo)', description: 'Thu hồi lượt chấm điểm vừa rồi để làm lại' },
          { key: 'F', action: 'Ẩn/Hiện Furigana', description: 'Bật/tắt phiên âm Hiragana trên chữ Hán' },
          { key: 'E', action: 'Sửa nhanh (Edit)', description: 'Mở modal chỉnh sửa trực tiếp nội dung thẻ' },
          { key: '* / -', action: 'Gắn cờ (Flag)', description: 'Đánh dấu cờ ưu tiên để lọc lại trong trình duyệt' },
        ],
      },
      {
        slug: 'audio-and-furigana',
        title: 'Tùy Chỉnh Phiên Âm Furigana & Tự Động Phát Âm',
        shortDescription: 'Cấu hình hiển thị cách đọc chữ Hán (Furigana) và thiết lập tốc độ phát âm tự động.',
        categorySlug: 'study',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Phiên Âm Furigana',
            content: 'Hệ thống hỗ trợ hiển thị phiên âm Hiragana trên đầu chữ Kanji theo định dạng chuẩn `Kanji[furigana]`. Bạn có thể nhấn phím F để ẩn Furigana ở mặt trước nhằm thử thách khả năng nhận diện mặt chữ Kanji.',
          },
          {
            title: 'Tự Động Phát Âm',
            content: 'Khi lật thẻ, âm thanh phát âm sẽ tự động chạy nếu thẻ có đính kèm file audio hoặc được cấu hình phát qua Flama Audio Desktop / Cloud TTS.',
          },
        ],
      },
    ],
  },
  {
    slug: 'browse',
    title: 'Duyệt & Quản Lý Thư Viện Thẻ',
    description: 'Tìm kiếm nâng cao, bộ lọc trạng thái, thao tác hàng loạt và quản lý thẻ khó nhớ (Leech).',
    iconName: 'Search',
    articles: [
      {
        slug: 'search-syntax',
        title: 'Cú Pháp Tìm Kiếm & Bộ Lọc Nâng Cao',
        shortDescription: 'Tra cứu nhanh hàng nghìn thẻ học theo bộ thẻ, thẻ nhãn (tag), trạng thái và cờ đánh dấu.',
        categorySlug: 'browse',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Cú Pháp Tìm Kiếm Chuẩn',
            content: '• `từ_khóa`: Tìm kiếm toàn văn trong tất cả các trường dữ liệu.\n• `deck:"Tên Bộ Thẻ"`: Lọc thẻ thuộc một bộ thẻ cụ thể.\n• `tag:tên_nhãn`: Lọc thẻ theo tag được gắn (ví dụ: `tag:jlpt_n3`).\n• `-tag:tên_nhãn`: Loại trừ các thẻ có tag chỉ định.\n• `is:new`: Lọc các thẻ mới chưa học.\n• `is:learn`: Lọc thẻ đang trong giai đoạn học ban đầu.\n• `is:due`: Lọc các thẻ đang đến hạn ôn tập hôm nay.\n• `is:suspended`: Lọc các thẻ đang bị tạm dừng học.\n• `flag:1`: Lọc theo cờ đánh dấu (1: Đỏ, 2: Cam, 3: Xanh...).',
          },
        ],
      },
      {
        slug: 'batch-actions',
        title: 'Thao Tác Hàng Loạt (Batch Actions)',
        shortDescription: 'Chuyển bộ thẻ, gắn nhãn, tạm dừng học hoặc đặt lại tiến độ cho hàng trăm thẻ cùng lúc.',
        categorySlug: 'browse',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Chọn các thẻ cần xử lý',
            description: 'Dùng chuột tick chọn từng thẻ, hoặc giữ Shift để chọn dải thẻ, hoặc bấm nút Chọn tất cả.',
          },
          {
            title: 'Bước 2: Chọn tác vụ trên thanh công cụ hàng loạt',
            description: '• Đổi bộ thẻ (Change Deck): Di chuyển các thẻ đã chọn sang bộ thẻ mới.\n• Gắn / Gỡ nhãn (Add/Remove Tags): Quản lý chủ đề hàng loạt.\n• Tạm dừng / Mở lại (Suspend / Unsuspend): Đóng băng thẻ tạm thời không cho xuất hiện trong phiên học.\n• Đặt lại tiến độ (Reset Progress): Xóa lịch sử học để đưa thẻ về trạng thái thẻ mới ban đầu.',
          },
        ],
      },
      {
        slug: 'card-lifecycle',
        title: 'Quản Lý Vòng Đời Thẻ & Xử Lý Thẻ Khó Nhớ (Leech)',
        shortDescription: 'Nhận diện tự động các thẻ học mãi không thuộc để bổ sung hình ảnh, câu ví dụ hoặc phân tích bộ thủ.',
        categorySlug: 'browse',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Thẻ Khó Nhớ (Leech Card) Là Gì?',
            content: 'Khi một thẻ bị bạn đánh giá "Học lại" (Again) quá 8 lần, hệ thống sẽ tự động gắn cờ/nhãn `leech`. Đây là dấu hiệu cho thấy phương pháp ghi nhớ hiện tại chưa hiệu quả đối với từ vựng này.',
          },
          {
            title: 'Phương Pháp Khắc Phục',
            content: '1. Thêm hình ảnh minh họa sinh động vào trường Image.\n2. Viết lại câu ví dụ gần gũi với cuộc sống hàng ngày.\n3. Phân tích chiết tự các bộ thủ Kanji để tạo câu chuyện liên tưởng.',
          },
        ],
      },
    ],
  },
  {
    slug: 'note-types',
    title: 'Loại Ghi Chú & Mẫu Thẻ (Note Types)',
    description: 'Kiến trúc 1 Ghi chú sinh nhiều Thẻ, quản lý trường dữ liệu, mẫu HTML/CSS và thẻ đục lỗ (Cloze).',
    iconName: 'NotebookTabs',
    articles: [
      {
        slug: 'concept',
        title: 'Kiến Trúc 1 Ghi Chú Sinh Nhiều Thẻ Học (1-to-Many)',
        shortDescription: 'Nhập dữ liệu 1 lần — Tự động tạo thẻ học 2 chiều: Bí quyết tiết kiệm 50% thời gian tạo bài học.',
        categorySlug: 'note-types',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        intro: 'Trong phương pháp học ngoại ngữ truyền thống, bạn phải tạo 2 thẻ riêng biệt để học xuôi và học ngược. Với Flama, bạn chỉ cần nhập thông tin một lần vào Ghi chú (Note).',
        detailedSections: [
          {
            title: 'Ví Dụ Minh Họa',
            content: 'Bạn tạo 1 Note có các trường:\n• Kanji: 食べる\n• Reading: たべる\n• Meaning: Ăn\n\nTừ Note này, Loại ghi chú sẽ tự động sinh ra 2 Card:\n• Card 1 (Nhận diện): Mặt trước hiện "食べる" ➔ Mặt sau hiện "たべる - Ăn".\n• Card 2 (Tái hiện): Mặt trước hiện "Ăn" ➔ Mặt sau hiện "食べる - たべる".',
          },
        ],
      },
      {
        slug: 'fields',
        title: 'Quản Lý Danh Sách Trường Dữ Liệu (Fields)',
        shortDescription: 'Thêm, sửa, sắp xếp các trường văn bản, âm thanh, hình ảnh và gợi ý trong Loại ghi chú.',
        categorySlug: 'note-types',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Vào trang Quản lý Loại thẻ',
            description: 'Truy cập menu Loại thẻ (/note-types) và bấm vào nút "Quản lý trường" của Loại ghi chú bạn muốn sửa.',
          },
          {
            title: 'Bước 2: Thêm hoặc sắp xếp lại các trường',
            description: 'Đặt tên trường rõ ràng (ví dụ: Kanji, Reading, Meaning, Audio, Example, Image). Bạn có thể kéo thả để thay đổi thứ tự nhập liệu.',
          },
        ],
      },
      {
        slug: 'templates',
        title: 'Tùy Biến Mẫu Thẻ Bằng HTML, Mustache Tags & CSS',
        shortDescription: 'Trang trí giao diện thẻ học với Mustache tags {{Field}}, {{FrontSide}}, Dark Mode và CSS tùy chỉnh.',
        categorySlug: 'note-types',
        readTimeMinutes: 5,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Cú Pháp Mustache Tags Thường Dùng',
            content: '• `{{Tên_Trường}}`: Hiển thị nội dung của trường.\n• `{{FrontSide}}`: Hiển thị lại toàn bộ nội dung mặt trước ở mặt sau.\n• `{{#Tên_Trường}} ... {{/Tên_Trường}}`: Thẻ điều kiện — chỉ hiển thị khối nội dung bên trong nếu trường đó có dữ liệu.\n• `{{^Tên_Trường}} ... {{/Tên_Trường}}`: Chỉ hiển thị nếu trường đó để trống.',
          },
          {
            title: 'Tùy Biến Giao Diện CSS',
            content: 'Bạn có thể chỉnh sửa font chữ, kích cỡ chữ Hán lớn hơn, màu sắc nổi bật và hỗ trợ tự động hiển thị mượt mà trên cả Dark Mode lẫn Light Mode.',
          },
        ],
      },
      {
        slug: 'cloze-deletion',
        title: 'Hướng Dẫn Tạo & Sử Dụng Mẫu Thẻ Đục Lỗ (Cloze Deletion)',
        shortDescription: 'Tạo câu đố điền vào chỗ trống chuyên dụng cho việc học ngữ pháp và mẫu câu giao tiếp.',
        categorySlug: 'note-types',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Chọn Loại ghi chú là Cloze',
            description: 'Khi tạo thẻ mới, chọn Loại thẻ là "Cloze" (hoặc Thẻ đục lỗ).',
          },
          {
            title: 'Bước 2: Đục lỗ cụm từ cần đố',
            description: 'Bôi đen từ hoặc cấu trúc ngữ pháp cần che trong câu ví dụ, sau đó nhấn tổ hợp phím `Ctrl + Shift + C` (hoặc gõ cú pháp `{{c1::từ_cần_ẩn}}`).',
            tip: 'Bạn có thể thêm gợi ý bằng cú pháp `{{c1::từ_cần_ẩn::gợi ý}}`. Khi học, máy sẽ hiện `[gợi ý]`.',
          },
          {
            title: 'Bước 3: Tạo nhiều lỗ đục trong một câu',
            description: 'Dùng `{{c1::...}}` cho lỗ đục thứ nhất, `{{c2::...}}` cho lỗ đục thứ hai. Hệ thống sẽ tự sinh ra 2 thẻ học riêng biệt tương ứng.',
          },
        ],
      },
    ],
  },
  {
    slug: 'marketplace',
    title: 'Marketplace & Chia Sẻ Học Liệu',
    description: 'Cài đặt bộ thẻ cộng đồng, mô hình Clone Overlay độc quyền bảo vệ ghi chú riêng, Change Requests và xuất bản.',
    iconName: 'Store',
    articles: [
      {
        slug: 'discovery',
        title: 'Tìm Kiếm & Cài Đặt Bộ Thẻ Chia Sẻ Từ Cộng Đồng',
        shortDescription: 'Khám phá kho học liệu phong phú từ cộng đồng, lọc theo cấp độ JLPT N5 - N1 và cài đặt nhanh vào tài khoản.',
        categorySlug: 'marketplace',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Truy cập Kho Học Liệu (Marketplace)',
            description: 'Chọn mục "Bộ thẻ" (/marketplace/decks) trên thanh điều hướng.',
          },
          {
            title: 'Bước 2: Tìm kiếm và lọc theo cấp độ',
            description: 'Sử dụng bộ lọc trình độ JLPT (N5, N4, N3, N2, N1) hoặc tìm theo tên giáo trình (Minna no Nihongo, Soumatome, Shinkanzen Master).',
          },
          {
            title: 'Bước 3: Cài đặt bộ thẻ',
            description: 'Bấm nút "Cài đặt bộ thẻ". Toàn bộ bài học sẽ được nạp vào tài khoản của bạn ngay lập tức.',
          },
        ],
      },
      {
        slug: 'overlay-clone',
        title: 'Cơ Chế Clone Overlay: Tùy Biến Thẻ An Toàn Khi Cập Nhật',
        shortDescription: 'Mô hình độc quyền: Thoải mái thêm ghi chú, ví dụ riêng mà không sợ bị ghi đè khi tác giả ra mắt bản phát hành mới.',
        categorySlug: 'marketplace',
        readTimeMinutes: 5,
        updatedAt: '2026-08-28',
        intro: 'Trong các ứng dụng flashcard thông thường, khi bạn tải bộ thẻ của người khác về rồi chỉnh sửa theo ý mình, nếu tác giả cập nhật sửa lỗi, việc đồng bộ sẽ ghi đè và làm mất toàn bộ ghi chú của bạn. Flama giải quyết triệt để vấn đề này bằng kiến trúc Clone Overlay.',
        detailedSections: [
          {
            title: 'Nguyên Lý Hoạt Động Của Clone Overlay',
            content: 'Dữ liệu được tách biệt thành 2 lớp:\n1. Lớp Nguồn của Tác giả (Source Layer): Chứa nội dung gốc, âm thanh và các bản sửa lỗi phát hành từ tác giả.\n2. Lớp Phủ Cá Nhân của Bạn (Overlay Layer): Lưu trữ các trường dữ liệu bạn tự viết thêm, ghi chú riêng và toàn bộ lịch sử tiến độ ôn tập SRS.',
          },
          {
            title: 'Khi Tác Giả Ra Bản Cập Nhật Mới',
            content: 'Khi bạn bấm "Cập nhật" tại trang Deck đã cài (/installed-decks):\n• Các lỗi chính tả hoặc âm thanh mới từ tác giả sẽ được nạp vào bài học.\n• Toàn bộ ghi chú riêng và tiến độ thuộc bài của bạn ĐƯỢC GIỮ NGUYÊN 100%. Không bao giờ xảy ra tình trạng mất dữ liệu cá nhân.',
          },
        ],
        troubleshootingSlug: 'marketplace-updates',
      },
      {
        slug: 'change-requests',
        title: 'Quy Trình Gửi Đề Xuất Chỉnh Sửa Cho Tác Giả (Change Requests)',
        shortDescription: 'Phát hiện chữ Hán hoặc phiên âm sai? Gửi báo lỗi kèm bản đối chiếu 3 chiều trực quan (3-Way Diff).',
        categorySlug: 'marketplace',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Bấm nút Báo sửa lỗi',
            description: 'Tại bộ thẻ đã cài đặt, chọn nút "Gửi đề xuất sửa đổi" (Change Request).',
          },
          {
            title: 'Bước 2: Nhập nội dung điều chỉnh',
            description: 'Chỉnh sửa lại chữ Hán, phiên âm hoặc bổ sung giải nghĩa chuẩn xác hơn và bấm Gửi.',
          },
          {
            title: 'Bước 3: Tác giả duyệt',
            description: 'Tác giả xem bảng đối chiếu trực quan (Diff) giữa bản cũ và bản mới. Khi tác giả bấm Duyệt (Approve), nội dung sửa đổi sẽ được đưa vào bản phát hành chính thức cho toàn bộ cộng đồng.',
          },
        ],
      },
      {
        slug: 'creator-publishing',
        title: 'Dành Cho Tác Giả: Xuất Bản & Quản Lý Bản Phát Hành (Release Builder)',
        shortDescription: 'Đăng tải bộ thẻ lên Marketplace, sử dụng công cụ Release Builder để tạo phiên bản phát hành mới (v1.1.0) kèm Changelog.',
        categorySlug: 'marketplace',
        readTimeMinutes: 5,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Đăng bộ thẻ lên Marketplace',
            description: 'Truy cập trang Đăng học liệu (/marketplace/decks/publish), điền tiêu đề, mô tả, cấp độ JLPT và gắn ảnh bìa.',
          },
          {
            title: 'Bước 2: Tạo Bản Phát Hành Mới (Release Builder)',
            description: 'Khi bạn bổ sung thêm từ vựng mới hoặc sửa các lỗi học liệu, vào trang Quản lý phát hành (/creator/decks/:id/releases/new), nhập mã phiên bản (ví dụ v1.1.0) và ghi chú tóm tắt nội dung mới (Changelog).',
          },
        ],
      },
    ],
  },
  {
    slug: 'import-sync',
    title: 'Nhập Dữ Liệu & Đồng Bộ Anki',
    description: 'Wizard 4 bước nhập từ vựng từ tệp CSV/TSV và đồng bộ trực tiếp với phần mềm Anki Desktop.',
    iconName: 'ArrowRightLeft',
    articles: [
      {
        slug: 'csv-wizard',
        title: 'Nhập Thẻ Từ Tệp CSV / TSV / Text Qua Wizard 4 Bước',
        shortDescription: 'Hướng dẫn sử dụng File Import Wizard tại /import để đưa danh sách từ vựng từ Excel/CSV vào hệ thống an toàn.',
        categorySlug: 'import-sync',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Chọn Đích & Loại thẻ (Target Deck & Note Type)',
            description: 'Chọn bộ thẻ tiếp nhận dữ liệu và Loại ghi chú tương ứng với cấu trúc dữ liệu của bạn.',
            badge: 'Bước 1',
          },
          {
            title: 'Bước 2: Tải & Phân tích cú pháp (Upload & Parse)',
            description: 'Kéo thả tệp bảng tính (.csv, .tsv, .txt). Chọn đúng ký tự phân cách (Dấu phẩy, Dấu chấm phẩy hoặc Dấu Tab).',
            badge: 'Bước 2',
            tip: 'Nếu xuất từ Excel, hãy lưu tệp dưới định dạng CSV UTF-8 để không bị lỗi font chữ tiếng Nhật.',
          },
          {
            title: 'Bước 3: Ánh xạ Cột & Chế độ ghi đè (Mapping)',
            description: 'Ghép từng cột trong file Excel với trường tương ứng trên Flama. Chọn chế độ xử lý thẻ trùng: Bỏ qua (Skip), Ghi đè cập nhật (Update) hoặc Thêm mới (Add).',
            badge: 'Bước 3',
          },
          {
            title: 'Bước 4: Ước lượng & Nạp thẻ (Execution & Report)',
            description: 'Xem bảng tóm tắt số lượng dòng hợp lệ và bấm "Nạp thẻ" để hoàn tất quy trình.',
            badge: 'Bước 4',
          },
        ],
        troubleshootingSlug: 'import-csv',
      },
      {
        slug: 'anki-connect-sync',
        title: 'Đồng Bộ Trực Tiếp Từ Phần Mềm Anki Desktop Qua AnkiConnect',
        shortDescription: 'Kết nối trực tiếp trình duyệt với Anki Desktop đang mở trên máy tính cá nhân (cổng 8765) để kéo Decks, Cards và Media.',
        categorySlug: 'import-sync',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Cài đặt add-on AnkiConnect trên Anki Desktop',
            description: 'Trên phần mềm Anki Desktop máy tính, vào Tools ➔ Add-ons ➔ Get Add-ons ➔ Nhập mã `2055492159` để cài đặt AnkiConnect.',
          },
          {
            title: 'Bước 2: Cấu hình cho phép kết nối CORS',
            description: 'Trong cấu hình của AnkiConnect trên Anki Desktop, thêm domain web của Flama vào danh sách `webCorsOriginList` (mặc định cho phép `*` hoặc `localhost`).',
          },
          {
            title: 'Bước 3: Thực hiện đồng bộ trên trang /sync',
            description: 'Mở trang Đồng bộ Anki (/sync) trên Flama. Thanh trạng thái sẽ chuyển sang màu xanh "Đã kết nối". Bạn chỉ cần chọn Bộ thẻ cần đồng bộ và bấm Bắt đầu.',
          },
        ],
        troubleshootingSlug: 'anki-sync',
      },
    ],
  },
  {
    slug: 'integrations',
    title: 'Tiện Ích Khai Thác & Trợ Lý AI',
    description: 'Khai thác từ vựng 1-click với Yomitan trên trình duyệt và kết nối trợ lý AI (Claude, Cursor, Antigravity) qua MCP.',
    iconName: 'Bot',
    articles: [
      {
        slug: 'yomitan',
        title: 'Khai Thác Từ Vựng 1-Click Với Tiện Ích Yomitan',
        shortDescription: 'Rê chuột tra từ khi đọc báo, manga trên web và bấm dấu (+) để từ vựng tự động được tạo thành Flashcard trong Flama.',
        categorySlug: 'integrations',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        intro: 'Dịch vụ Flama Connect là dịch vụ cầu nối được tích hợp sẵn ở máy chủ backend của Flama. Bạn KHÔNG CẦN tải về hay cài đặt bất kỳ phần mềm Flama Connect nào trên máy tính. Bạn chỉ cần thực hiện 3 bước cấu hình đơn giản.',
        steps: [
          {
            title: 'Bước 1: Tạo Token kết nối trên Flama',
            description: 'Truy cập trang Cài đặt Yomitan (/settings/yomitan) trên Flama. Bấm nút "Tạo Token mới", sau đó bấm Sao chép đường dẫn kết nối (Server URL).',
            badge: 'Web Flama',
          },
          {
            title: 'Bước 2: Dán Server URL vào tiện ích Yomitan',
            description: 'Mở Cài đặt (Settings) của tiện ích Yomitan trên trình duyệt ➔ Chọn mục "Anki / Connect" ➔ Bật kích hoạt (Enable Anki integration) ➔ Dán đường dẫn Server URL vừa sao chép vào ô "Server".',
            badge: 'Yomitan',
          },
          {
            title: 'Bước 3: Cấu hình ánh xạ các trường từ vựng',
            description: 'Chọn bộ thẻ đích và cấu hình ánh xạ: {expression} ➔ Kanji, {reading} ➔ Reading, {glossary} ➔ Meaning, {audio} ➔ Audio.',
            badge: 'Ánh xạ',
          },
        ],
        keyTakeaways: [
          'Sau khi kết nối, mỗi khi rê chuột tra từ trên web và bấm dấu (+), Flashcard sẽ được nạp thẳng vào bộ thẻ bạn chọn.',
        ],
        troubleshootingSlug: 'yomitan',
      },
      {
        slug: 'mcp-ai',
        title: 'Kết Nối Trợ Lý AI Qua Model Context Protocol (MCP)',
        shortDescription: 'Tạo MCP Token tại /settings/mcp-tokens để kết nối Claude, Cursor, Antigravity tự động phân tích và tạo bài học.',
        categorySlug: 'integrations',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Tạo mã MCP Token',
            description: 'Vào trang Cài đặt MCP Tokens (/settings/mcp-tokens), đặt tên định danh và bấm "Tạo token".',
          },
          {
            title: 'Bước 2: Cấu hình vào tệp cấu hình AI (Claude/Cursor)',
            description: 'Sao chép đoạn JSON cấu hình MCP Server và dán vào tệp `claude_desktop_config.json` hoặc cấu hình MCP của Cursor/Antigravity.',
          },
        ],
      },
    ],
  },
  {
    slug: 'audio',
    title: 'Hệ Thống Âm Thanh & Giọng Đọc (TTS)',
    description: 'Ứng dụng Flama Audio Desktop phát âm offline miễn phí, cấu hình Cloud TTS và tạo âm thanh hàng loạt.',
    iconName: 'AudioLines',
    articles: [
      {
        slug: 'flama-audio',
        title: 'Ứng Dụng Flama Audio Desktop (Phát Âm Ngoại Tuyến 100%)',
        shortDescription: 'Tải phần mềm FlamaAudio-Portable.exe (.NET 8) để phát âm giọng bản xứ VOICEVOX và Kokoro TTS hoàn toàn miễn phí không cần mạng.',
        categorySlug: 'audio',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        intro: 'Flama Audio Desktop là ứng dụng máy tính duy nhất mà người dùng có thể tải về nếu muốn sử dụng giọng đọc tiếng Nhật tự nhiên chuẩn bản xứ chạy cục bộ trên máy Windows mà không tốn tiền API hay cần kết nối mạng.',
        steps: [
          {
            title: 'Bước 1: Tải tệp FlamaAudio-Portable.exe',
            description: 'Tải tệp từ trang Tải Flama Audio (/guide/flama-audio) hoặc nút tải trên thanh điều hướng.',
          },
          {
            title: 'Bước 2: Khởi chạy phần mềm trên Windows',
            description: 'Nhấp đúp chuột để mở tệp. Phần mềm sẽ tự động khởi tạo dịch vụ VOICEVOX/Kokoro trên cổng cục bộ `127.0.0.1:4791`.',
          },
          {
            title: 'Bước 3: Sử dụng trên web Flama',
            description: 'Khi học thẻ hoặc tạo âm thanh, hệ thống sẽ tự động gửi yêu cầu đến Flama Audio Desktop để phát âm tức thì.',
          },
        ],
        troubleshootingSlug: 'flama-audio',
      },
      {
        slug: 'cloud-tts-keys',
        title: 'Cấu Hình Khóa API Giọng Đọc Đám Mây (Cloud TTS)',
        shortDescription: 'Hướng dẫn đăng ký và nhập API Key cho VoiceVox API, OpenAI TTS, ElevenLabs và Google Speech.',
        categorySlug: 'audio',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        detailedSections: [
          {
            title: 'Các Nhà Cung Cấp Được Hỗ Trợ',
            content: '• VoiceVox API: Miễn phí, giọng đọc anime đa dạng.\n• OpenAI TTS: Giọng đọc tự nhiên chất lượng cao (Alloy, Echo, Fable, Onyx, Nova, Shimmer).\n• ElevenLabs: Đỉnh cao về cảm xúc và ngữ điệu ngôn ngữ.\n• Google Cloud Text-to-Speech: Giọng đọc Wavenet/Neural2 chuẩn xác.',
          },
          {
            title: 'Bảo Mật API Key',
            content: 'Toàn bộ API Key cá nhân của bạn được mã hóa chuẩn AES-256 trên máy chủ và chỉ được giải mã khi thực hiện tổng hợp âm thanh.',
          },
        ],
      },
      {
        slug: 'batch-generation',
        title: 'Công Cụ Tạo Phát Âm Hàng Loạt (Deck Audio Generator)',
        shortDescription: 'Quét toàn bộ bộ thẻ và tự động tạo file phát âm hàng loạt cho hàng nghìn từ vựng cùng lúc tại trang /audio/generate.',
        categorySlug: 'audio',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Truy cập Studio Tạo Âm Thanh',
            description: 'Vào trang /audio/generate từ thanh menu bên trái.',
          },
          {
            title: 'Bước 2: Chọn Bộ thẻ và Giọng đọc',
            description: 'Chọn bộ thẻ cần tạo âm thanh, trường văn bản nguồn (Kanji/Reading) và trường lưu âm thanh đích (Audio). Chọn nhà cung cấp TTS (Flama Audio, OpenAI, ElevenLabs...).',
          },
          {
            title: 'Bước 3: Bắt đầu tạo hàng loạt',
            description: 'Bấm nút "Tạo âm thanh hàng loạt". Hệ thống sẽ xử lý tuần tự và cập nhật tiến độ trực tiếp trên màn hình.',
          },
        ],
      },
    ],
  },
  {
    slug: 'account-billing',
    title: 'Tài Khoản, Ví & Thanh Toán',
    description: 'Quản trị hồ sơ, bảo mật tài khoản, quyền riêng tư và nạp tiền ví qua PayOS VietQR tự động.',
    iconName: 'Wallet',
    articles: [
      {
        slug: 'profile-security',
        title: 'Quản Trị Hồ Sơ, Bảo Mật & Quyền Riêng Tư',
        shortDescription: 'Cập nhật thông tin cá nhân, bảo vệ tài khoản bằng mật khẩu mạnh và quản lý quyền hiển thị chuỗi ngày học Streak.',
        categorySlug: 'account-billing',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Mở trang Cá nhân',
            description: 'Bấm vào biểu tượng avatar của bạn ở góc dưới thanh điều hướng và chọn "Trang cá nhân" (/profile).',
          },
          {
            title: 'Bước 2: Điều chỉnh thông tin & bảo mật',
            description: 'Cập nhật tên hiển thị, ảnh đại diện, đổi mật khẩu và thiết lập quyền công khai hồ sơ.',
          },
        ],
      },
      {
        slug: 'wallet-payos',
        title: 'Nạp Số Dư Ví Flama & Thanh Toán Qua PayOS VietQR',
        shortDescription: 'Nạp tiền vào Flama Wallet tự động 24/7 bằng quét mã VietQR ngân hàng qua cổng PayOS để mua các khóa học bản quyền.',
        categorySlug: 'account-billing',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        steps: [
          {
            title: 'Bước 1: Vào trang Ví Flama',
            description: 'Truy cập mục "Ví & Doanh thu" (/wallet) trên thanh điều hướng.',
          },
          {
            title: 'Bước 2: Chọn số tiền cần nạp',
            description: 'Nhập số tiền hoặc chọn các mức nạp nhanh có sẵn, sau đó bấm nút "Tạo mã nạp tiền VietQR".',
          },
          {
            title: 'Bước 3: Quét mã QR trên ứng dụng ngân hàng',
            description: 'Mở ứng dụng ngân hàng bất kỳ (Mobile Banking), quét mã VietQR hiển thị trên màn hình. Số dư ví sẽ được cộng tự động trong vòng 5 - 10 giây.',
          },
        ],
      },
    ],
  },
  {
    slug: 'troubleshooting',
    title: 'Trung Tâm Xử Lý Sự Cố',
    description: 'Chẩn đoán và khắc phục nhanh các trục trặc thường gặp theo đúng triệu chứng quan sát thực tế.',
    iconName: 'AlertTriangle',
    articles: [
      {
        slug: 'dashboard-study',
        title: 'Khắc Phục Sự Cố Hiển Thị Thẻ & Số Lượng Ôn Tập',
        shortDescription: 'Tại sao số thẻ cần học hôm nay không hiển thị, không có thẻ mới hoặc chuỗi Streak chưa tăng?',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Bảng điều khiển không hiển thị thẻ mới mặc dù bộ thẻ vẫn còn từ vựng.',
            cause: 'Bạn đã đạt giới hạn số lượng thẻ mới tối đa trong ngày (New Cards/Day) được thiết lập cho bộ thẻ.',
            solution: [
              'Vào phần Cài đặt Bộ thẻ (Deck Settings).',
              'Tăng ô "Số thẻ mới mỗi ngày" lên con số bạn mong muốn.',
              'Quay lại Bảng điều khiển và tải lại trang.',
            ],
          },
          {
            symptom: 'Học bài lúc 1:00 đêm nhưng chuỗi ngày học Streak chưa tăng lên ngày tiếp theo.',
            cause: 'Mốc chuyển sang ngày mới của hệ thống là 4:00 sáng để hỗ trợ người học khuya.',
            solution: [
              'Chuỗi ngày học của bạn vẫn được bảo toàn tuyệt đối.',
              'Sau 4:00 sáng, hệ thống sẽ tự động chốt phiên và tính cho ngày mới.',
            ],
          },
        ],
      },
      {
        slug: 'import-csv',
        title: 'Khắc Phục Lỗi Khi Nạp Tệp CSV / Excel',
        shortDescription: 'Xử lý lỗi tệp bảng tính bị dồn vào một cột, lỗi font chữ tiếng Nhật hoặc báo thiếu trường bắt buộc.',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Khi tải tệp lên ở Bước 2, tất cả chữ bị dồn vào một cột duy nhất.',
            cause: 'Chọn sai ký tự phân cách (Delimiter) trong bảng tính.',
            solution: [
              'Tại Bước 2 của File Import Wizard, đổi lựa chọn "Dấu phân cách" từ Dấu phẩy sang Dấu chấm phẩy (;) hoặc Dấu Tab (\\t).',
              'Xem lại bản xem trước ở bảng bên dưới cho đến khi các cột tách riêng biệt.',
            ],
          },
          {
            symptom: 'Chữ Hán và Hiragana sau khi nhập bị biến thành ký tự lạ hoặc dấu hỏi chấm (???).',
            cause: 'Tệp CSV được lưu bằng bảng mã ANSI hoặc Windows-1258 thay vì UTF-8.',
            solution: [
              'Mở file trên Excel ➔ Chọn Save As (Lưu dưới dạng).',
              'Tại ô File format, chọn "CSV UTF-8 (Comma delimited) (*.csv)".',
              'Tải lại tệp lên Flama.',
            ],
          },
        ],
      },
      {
        slug: 'anki-sync',
        title: 'Khắc Phục Lỗi Kết Nối Với Anki Desktop (AnkiConnect)',
        shortDescription: 'Xử lý lỗi không tìm thấy cổng 8765, lỗi CORS hoặc không tải được media từ Anki Desktop.',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 4,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Trang /sync hiển thị trạng thái "Không tìm thấy Anki Desktop đang chạy".',
            cause: 'Phần mềm Anki Desktop chưa được mở hoặc chưa cài đặt add-on AnkiConnect.',
            solution: [
              'Mở phần mềm Anki Desktop trên máy tính của bạn.',
              'Kiểm tra menu Tools ➔ Add-ons xem đã có "AnkiConnect" chưa. Nếu chưa, hãy cài đặt mã `2055492159`.',
              'Khởi động lại Anki Desktop và bấm nút "Thử lại" trên trang /sync.',
            ],
          },
        ],
      },
      {
        slug: 'yomitan',
        title: 'Khắc Phục Lỗi Kết Nối & Thêm Thẻ Từ Tiện Ích Yomitan',
        shortDescription: 'Xử lý lỗi bấm dấu (+) trên Yomitan không thêm được thẻ hoặc báo lỗi kết nối máy chủ.',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Yomitan báo lỗi "Could not connect to Anki/Flama server".',
            cause: 'Đường dẫn Server URL hoặc mã Token trong cài đặt Yomitan bị sai hoặc đã bị thu hồi.',
            solution: [
              'Vào trang /settings/yomitan trên Flama.',
              'Tạo một mã Token mới và bấm nút "Sao chép Server URL".',
              'Mở Cài đặt Yomitan ➔ Anki/Connect ➔ Dán lại vào ô Server URL và bấm Test connection.',
            ],
          },
        ],
      },
      {
        slug: 'flama-audio',
        title: 'Khắc Phục Lỗi Không Nghe Được Phát Âm / Flama Audio',
        shortDescription: 'Xử lý sự cố không nghe thấy tiếng, lỗi cảnh báo SmartScreen khi tải ứng dụng hoặc mất kết nối cổng 4791.',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Bấm biểu tượng chiếc loa nhưng không nghe thấy âm thanh phát ra.',
            cause: 'Phần mềm Flama Audio Desktop chưa được mở trên máy tính Windows của bạn.',
            solution: [
              'Mở tệp `FlamaAudio-Portable.exe` trên máy tính của bạn.',
              'Đảm bảo cửa sổ phần mềm hiển thị trạng thái "Service Running on 127.0.0.1:4791".',
              'Bấm lại vào biểu tượng loa trên trang học tập.',
            ],
          },
          {
            symptom: 'Trình duyệt hoặc Windows SmartScreen cảnh báo khi tải tệp FlamaAudio-Portable.exe.',
            cause: 'Tệp phần mềm cục bộ tự biên dịch chưa đăng ký chứng chỉ thương mại với Microsoft.',
            solution: [
              'Bấm dấu ba chấm (...) cạnh tệp tải về trên trình duyệt ➔ Chọn Giữ lại (Keep).',
              'Bấm mũi tên mở rộng ➔ Chọn Vẫn giữ (Keep anyway). Tệp hoàn toàn an toàn và sạch 100%.',
            ],
          },
        ],
      },
      {
        slug: 'marketplace-updates',
        title: 'Xử Lý Khi Nhận Thông Báo Cập Nhật Bộ Thẻ Từ Tác Giả',
        shortDescription: 'Hướng dẫn cập nhật bản phát hành mới của bộ thẻ đã cài mà vẫn bảo toàn nguyên vẹn ghi chú cá nhân.',
        categorySlug: 'troubleshooting',
        readTimeMinutes: 3,
        updatedAt: '2026-08-28',
        troubleshoot: [
          {
            symptom: 'Bộ thẻ đã cài đặt hiện biểu tượng thông báo "Có bản cập nhật mới v1.1.0".',
            cause: 'Tác giả bộ thẻ đã phát hành phiên bản sửa lỗi hoặc bổ sung từ vựng mới.',
            solution: [
              'Truy cập trang Deck đã cài (/installed-decks).',
              'Bấm vào nút "Xem bản cập nhật" và bấm "Cập nhật".',
              'Nhờ mô hình Clone Overlay của Flama, toàn bộ ghi chú riêng và tiến trình học của bạn sẽ được giữ nguyên 100%.',
            ],
          },
        ],
      },
    ],
  },
]

export function getAllArticles(): GuideArticle[] {
  const articles: GuideArticle[] = []
  for (const cat of GUIDE_CATEGORIES) {
    for (const art of cat.articles) {
      articles.push(art)
    }
  }
  return articles
}

export function getArticleBySlug(categorySlug: string, articleSlug?: string): { category?: GuideCategory; article?: GuideArticle } {
  // If only 1 param passed, it might be category slug or a flat article slug (like 'getting-started' or 'core-concepts')
  if (!articleSlug) {
    // Check if category matches
    const category = GUIDE_CATEGORIES.find((c) => c.slug === categorySlug)
    if (category && category.articles.length > 0) {
      return { category, article: category.articles[0] }
    }
    // Check if any article slug matches categorySlug
    for (const cat of GUIDE_CATEGORIES) {
      const art = cat.articles.find((a) => a.slug === categorySlug)
      if (art) return { category: cat, article: art }
    }
    return {}
  }

  const category = GUIDE_CATEGORIES.find((c) => c.slug === categorySlug)
  if (!category) {
    // Fallback: look for article across all categories
    for (const cat of GUIDE_CATEGORIES) {
      const art = cat.articles.find((a) => a.slug === articleSlug)
      if (art) return { category: cat, article: art }
    }
    return {}
  }

  const article = category.articles.find((a) => a.slug === articleSlug)
  return { category, article: article || category.articles[0] }
}

export function searchArticles(query: string): GuideArticle[] {
  const clean = query.trim().toLowerCase()
  if (!clean) return []

  const all = getAllArticles()
  return all.filter((art) => {
    const titleMatch = art.title.toLowerCase().includes(clean)
    const descMatch = art.shortDescription.toLowerCase().includes(clean)
    const introMatch = art.intro?.toLowerCase().includes(clean) || false
    const stepsMatch = art.steps?.some((s) => s.title.toLowerCase().includes(clean) || s.description.toLowerCase().includes(clean)) || false
    const troubleshootMatch = art.troubleshoot?.some((t) => t.symptom.toLowerCase().includes(clean) || t.cause.toLowerCase().includes(clean)) || false

    return titleMatch || descMatch || introMatch || stepsMatch || troubleshootMatch
  })
}
