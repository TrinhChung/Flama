/**
 * Flama Platform Legal Documents Data Engine
 * Standardized schema and official Vietnamese legal texts for all core platform policies.
 * 
 * Documents:
 * 1. terms: Điều khoản Sử dụng Dịch vụ & Bảo vệ Nền tảng (Terms of Service)
 * 2. privacy: Chính sách Bảo mật Dữ liệu & Quyền Riêng tư (Privacy Policy - Nghị định 13/2023/NĐ-CP)
 * 3. marketplace-guidelines: Quy chế Hoạt động Marketplace & Bản quyền Trí tuệ (Marketplace & IP Guidelines)
 * 4. community-guidelines: Chuẩn mực Cộng đồng & Quy tắc Ứng xử Người dùng (Community Guidelines)
 * 5. cookies: Chính sách Cookie & Lưu trữ Cục bộ (Cookie Policy)
 */

import { legalDocumentsEn } from './legalDocumentsData.en'

export interface LegalSubClause {
  id: string
  clauseNumber: string
  title: string
  content: string[]
  bullets?: string[]
}

export interface StatutoryCallout {
  type: 'warning' | 'info' | 'statutory'
  label: string
  text: string
}

export interface LegalClause {
  id: string
  clauseNumber: string
  title: string
  summary?: string
  content?: string[]
  subClauses?: LegalSubClause[]
  bullets?: string[]
  callout?: StatutoryCallout
}

export interface LegalDocument {
  id: string
  title: string
  officialBadge: string
  lastUpdated: string
  effectiveDate: string
  version: string
  readTimeMinutes: number
  executiveSummary: string
  clauses: LegalClause[]
}

export const legalDocuments: Record<string, LegalDocument> = {
  terms: {
    id: 'terms',
    title: 'Điều khoản Sử dụng Dịch vụ & Bảo vệ Nền tảng',
    officialBadge: 'Quy chuẩn Pháp lý Nền tảng v2.0',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 18,
    executiveSummary:
      'Văn bản này xác lập hợp đồng sử dụng dịch vụ có tính ràng buộc pháp lý giữa người dùng và Nền tảng Học tập Flama. Quy chế bao gồm điều kiện tài khoản, cơ chế thanh toán qua cổng payOS, quy định miễn trừ đối với dịch vụ vệ tinh Flama Connect và Flama Audio, chế tài xử lý vi phạm, và giới hạn trách nhiệm pháp lý theo luật định.',
    clauses: [
      {
        id: 'clause-terms-scope',
        clauseNumber: 'Điều 1',
        title: 'Phạm vi Áp dụng & Chấp thuận Điều khoản',
        summary: 'Xác lập hiệu lực pháp lý của bản Điều khoản Dịch vụ và điều kiện tham gia nền tảng.',
        content: [
          'Chào mừng bạn đến với Flama (sau đây gọi là "Nền tảng", "Hệ thống" hoặc "Chúng tôi"). Bằng việc truy cập, tạo tài khoản, cài đặt ứng dụng máy trạm hoặc sử dụng bất kỳ tính năng nào trên Flama, bạn xác nhận đã đọc kỹ, hiểu rõ và đồng ý bị ràng buộc vô điều kiện bởi bản Điều khoản Sử dụng Dịch vụ này cùng các chính sách liên quan được công bố công khai.',
        ],
        subClauses: [
          {
            id: 'terms-1-1',
            clauseNumber: '1.1',
            title: 'Khung Thỏa thuận Pháp lý Toàn vẹn',
            content: [
              'Bản Điều khoản Dịch vụ này, cùng với Chính sách Bảo mật, Quy chế Marketplace & Bản quyền, và Chuẩn mực Cộng đồng, cấu thành thỏa thuận pháp lý toàn vẹn giữa bạn và Flama đối với việc sử dụng dịch vụ.',
              'Trường hợp có sự mâu thuẫn giữa bản tóm tắt giao diện và nội dung chi tiết của các điều khoản văn bản này, nội dung chi tiết trong văn bản pháp lý chính thức sẽ được ưu tiên áp dụng.',
            ],
          },
          {
            id: 'terms-1-2',
            clauseNumber: '1.2',
            title: 'Điều kiện Năng lực Hành vi & Độ tuổi',
            content: [
              'Dịch vụ của Flama dành cho cá nhân từ đủ 15 tuổi trở lên có đầy đủ năng lực hành vi dân sự theo quy định của Bộ luật Dân sự Việt Nam.',
              'Trường hợp người học dưới 15 tuổi, việc đăng ký tài khoản và thực hiện các giao dịch thanh toán trên nền tảng phải có sự đồng ý, bảo lãnh và giám sát trực tiếp từ cha mẹ hoặc người giám hộ hợp pháp.',
            ],
          },
          {
            id: 'terms-1-3',
            clauseNumber: '1.3',
            title: 'Hiệu lực và Sửa đổi Quy chế',
            content: [
              'Flama bảo lưu quyền cập nhật, sửa đổi hoặc điều chỉnh nội dung các điều khoản bất kỳ lúc nào nhằm đáp ứng yêu cầu vận hành kỹ thuật hoặc tuân thủ các thay đổi pháp luật hiện hành.',
              'Mọi thay đổi trọng yếu sẽ được thông báo trước ít nhất bảy (07) ngày thông qua thông báo trên thanh điều hướng hoặc qua email đăng ký của người dùng trước khi chính thức có hiệu lực thi hành.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-account',
        clauseNumber: 'Điều 2',
        title: 'Tài khoản Người dùng & Quản lý Phiên Bảo mật',
        summary: 'Quy định nghĩa vụ định danh, bảo mật mật khẩu và phòng vệ chống tấn công dò quét.',
        content: [
          'Để khai thác đầy đủ các tính năng học tập, lưu trữ tiến độ thuật toán Lặp lại Ngắt quãng (Spaced Repetition) và tham gia Marketplace, người dùng cần thiết lập một tài khoản duy nhất trên hệ thống Flama.',
        ],
        subClauses: [
          {
            id: 'terms-2-1',
            clauseNumber: '2.1',
            title: 'Đăng ký & Tính Chính xác của Dữ liệu Định danh',
            content: [
              'Người dùng cam kết cung cấp địa chỉ email hợp lệ, có thể truy cập được và các thông tin hồ sơ trung thực tại thời điểm đăng ký.',
              'Nghiêm cấm hành vi mạo danh cá nhân, tổ chức khác, tạo tài khoản giả mạo hoặc đăng ký hàng loạt tài khoản tự động (bot registration).',
            ],
          },
          {
            id: 'terms-2-2',
            clauseNumber: '2.2',
            title: 'Trách nhiệm Bảo mật & Cơ chế Khóa Chống Brute-Force',
            content: [
              'Người dùng tự chịu trách nhiệm bảo mật mật khẩu truy cập và các thiết bị đăng nhập của mình. Flama áp dụng tiêu chuẩn mã hóa mật khẩu một chiều an toàn cao và không thể khôi phục mật khẩu gốc.',
              'Để bảo vệ hệ thống trước các cuộc tấn công dò quét mật khẩu (Credential Stuffing / Brute-Force), dịch vụ bảo vệ đăng nhập sẽ tự động kích hoạt cơ chế khóa tạm thời (Rate-Limited Lockout) theo hàm số mũ đối với các địa chỉ IP hoặc tài khoản có số lần xác thực thất bại vượt ngưỡng an toàn.',
            ],
          },
          {
            id: 'terms-2-3',
            clauseNumber: '2.3',
            title: 'Tính chất Phi Chuyển nhượng của Tài khoản',
            content: [
              'Mỗi tài khoản Flama là tài sản định danh cá nhân độc quyền của người đăng ký. Bạn không được phép bán, chuyển nhượng, cho thuê, chia sẻ thông tin đăng nhập hoặc ủy quyền cho bên thứ ba sử dụng tài khoản dưới bất kỳ hình thức nào.',
              'Mọi hoạt động phát sinh từ tài khoản được hệ thống ghi nhận mặc nhiên là hành động có chủ quyền và sự chấp thuận của chính chủ sở hữu tài khoản.',
            ],
          },
        ],
        callout: {
          type: 'statutory',
          label: 'Lưu ý Pháp lý về Bảo vệ Phiên Đăng nhập',
          text: 'Người dùng có nghĩa vụ thông báo ngay lập tức cho bộ phận hỗ trợ kỹ thuật của Flama khi phát hiện bất kỳ dấu hiệu truy cập trái phép hoặc lỗ hổng bảo mật nào liên quan đến tài khoản cá nhân.',
        },
      },
      {
        id: 'clause-terms-payos',
        clauseNumber: 'Điều 3',
        title: 'Tích hợp Thanh toán payOS & Quy chế Giao dịch Tài chính',
        summary: 'Quy chế giao dịch VietQR qua cổng payOS, thời hạn đơn hàng, nội dung số không hoàn tiền và số dư lưu ký.',
        content: [
          'Flama triển khai hạ tầng thanh toán số phục vụ việc mua bán học liệu, bộ thẻ flashcard, mẫu định dạng ghi chú học tập chuyên dụng và đóng góp ủng hộ hệ thống. Toàn bộ các giao dịch trực tuyến được thực hiện thông qua cổng thanh toán trung gian payOS.',
        ],
        subClauses: [
          {
            id: 'terms-3-1',
            clauseNumber: '3.1',
            title: 'Đơn vị Xử lý Thanh toán Trung gian payOS',
            content: [
              'Cổng thanh toán payOS (thuộc Công ty Cổ phần Công nghệ PAYOS, hoạt động theo giấy phép trung gian thanh toán và chuẩn mực mạng lưới VietQR của Ngân hàng Nhà nước Việt Nam) là đơn vị độc lập chịu trách nhiệm điều hướng và xử lý kỹ thuật giao dịch ngân hàng.',
              'Mọi mức giá niêm yết trên Flama được hiển thị và thanh toán bằng Việt Nam Đồng (VND). Khi quét mã VietQR hoặc chuyển khoản, người dùng có trách nhiệm kiểm tra đúng số tiền và nội dung chuyển khoản theo thông tin đơn hàng.',
            ],
          },
          {
            id: 'terms-3-2',
            clauseNumber: '3.2',
            title: 'Thời hạn Phiên Thanh toán & Xử lý Giao dịch Quá hạn (30 Phút)',
            content: [
              'Mỗi liên kết thanh toán và mã QR đơn hàng trên hệ thống có thời hạn hiệu lực chính xác là ba mươi (30) phút (1800 giây) kể từ thời điểm khởi tạo.',
              'Các khoản tiền chuyển sau khi liên kết thanh toán đã hết hạn, hoặc chuyển sai mã tham chiếu định danh (Payment Reference), hệ thống sẽ không thể kích hoạt cấp quyền tự động. Các giao dịch này sẽ được chuyển sang trạng thái chờ rà soát và đối soát thủ công.',
            ],
          },
          {
            id: 'terms-3-3',
            clauseNumber: '3.3',
            title: 'Bản chất Nội dung Số & Miễn trừ Quyền Hủy Đơn',
            content: [
              'Các sản phẩm trên Flama Marketplace (bộ thẻ học, mẫu ghi chú) là nội dung giáo dục số được cung cấp quyền truy cập và giải phóng tức thì vào tài khoản học tập ngay khi giao dịch được hệ thống ngân hàng xác nhận thành công.',
              'Căn cứ theo quy định pháp luật về thương mại điện tử và bảo vệ người tiêu dùng đối với sản phẩm số tiêu dùng ngay, bằng việc xác nhận thanh toán, người dùng đồng ý nhận quyền sử dụng tức thì và từ bỏ quyền yêu cầu hoàn tiền hoặc quyền đơn phương hủy hợp đồng mà không có lý do kỹ thuật chính đáng.',
            ],
          },
          {
            id: 'terms-3-4',
            clauseNumber: '3.4',
            title: 'Chính sách Hoàn tiền Ngoại lệ (Exceptions Policy)',
            content: [
              'Flama chỉ xem xét hoàn tiền trong các trường hợp lỗi kỹ thuật bất khả kháng được xác minh cụ thể sau:',
              '1. Lỗi trừ tiền trùng lặp (Duplicate Billing): Người dùng bị trừ tiền nhiều hơn một lần cho cùng một mã đơn hàng trong vòng 24 giờ.',
              '2. Lỗi cấp quyền hệ thống vĩnh viễn (Grant Failure): Giao dịch đã được payOS ghi nhận thành công nhưng hệ thống Flama không cấp quyền truy cập học liệu và đội ngũ kỹ thuật không thể khắc phục trong vòng bảy (07) ngày làm việc kể từ thời điểm nhận phản ánh.',
              'Do cổng thanh toán VietQR/payOS không hỗ trợ hoàn tiền đảo ngược tự động, các khoản hoàn trả hợp lệ sẽ được thực hiện thủ công qua chuyển khoản ngân hàng trong thời hạn mười bốn (14) ngày làm việc. Yêu cầu hoàn tiền phải gửi qua kênh Hỗ trợ trong vòng 07 ngày kể từ ngày thanh toán.',
            ],
          },
          {
            id: 'terms-3-5',
            clauseNumber: '3.5',
            title: 'Ví Doanh thu Tác giả & Số dư Lưu ký Tạm thời',
            content: [
              'Khi học liệu trả phí của Tác giả (Creator) được mua thành công, số tiền ròng (sau khi khấu trừ phí nền tảng theo bậc: 10% với người dùng thông thường, 5% với tác giả đạt chuẩn) sẽ được ghi nhận vào số dư tài khoản của tác giả.',
              'Tính năng rút tiền (Payout) hiện đang trong lộ trình hoàn thiện hạ tầng đối soát thuế và xác minh danh tính. Toàn bộ số dư doanh thu được Flama bảo toàn và lưu trữ an toàn dưới dạng số dư lưu ký nội bộ cho đến khi chính thức phát hành cổng rút tiền tuân thủ quy định thuế.',
            ],
          },
        ],
        callout: {
          type: 'warning',
          label: 'Nghiêm cấm Gian lận Tài chính & Tra soát Bất hợp pháp',
          text: 'Mọi hành vi sử dụng tài khoản ngân hàng không chính chủ, gian lận thanh toán, cố tình khiếu nại tra soát gian lận (chargeback fraud) sau khi đã tải học liệu sẽ bị khóa tài khoản vĩnh viễn, tịch thu quyền truy cập và chuyển hồ sơ sang cơ quan công an xử lý theo pháp luật.',
        },
      },
      {
        id: 'clause-terms-connect',
        clauseNumber: 'Điều 4',
        title: 'Dịch vụ Vệ tinh Flama Connect & Miễn trừ Trách nhiệm Học liệu',
        summary: 'Bản chất cầu nối giao thức cục bộ, bảo vệ quyền riêng tư thiết bị và trách nhiệm bản quyền dữ liệu khai thác cá nhân.',
        content: [
          'Flama cung cấp dịch vụ vệ tinh Flama Connect vận hành dưới dạng cầu nối giao thức cục bộ trên máy tính người dùng nhằm kết nối tương thích với các tiện ích mở rộng trình duyệt phục vụ khai thác học liệu và thuật ngữ một chạm (1-click mining).',
        ],
        subClauses: [
          {
            id: 'terms-4-1',
            clauseNumber: '4.1',
            title: 'Bản chất Cầu nối Cục bộ (Local Loopback Isolation)',
            content: [
              'Flama Connect được thiết kế chạy trên mạng nội bộ khép kín trên máy tính người dùng, không lắng nghe trên các giao diện mạng công cộng. Người dùng chịu hoàn toàn trách nhiệm về việc cấu hình tường lửa máy tính và ngăn chặn các mã độc máy trạm truy vấn trái phép vào dịch vụ kết nối cục bộ này.',
            ],
          },
          {
            id: 'terms-4-2',
            clauseNumber: '4.2',
            title: 'Bảo mật Mã Xác thực Kết nối Flama Connect',
            content: [
              'Mã xác thực truy cập Flama Connect chứa các quyền hạn quan trọng (tạo thẻ, đọc danh mục bộ thẻ). Người dùng có nghĩa vụ bảo mật mã này trong trình duyệt và phải thu hồi (revoke) ngay lập tức trên trang cài đặt tài khoản nếu phát hiện rò rỉ.',
            ],
          },
          {
            id: 'terms-4-3',
            clauseNumber: '4.3',
            title: 'Nguyên tắc Nghiên cứu Cá nhân (Fair Use / Private Study)',
            content: [
              'Người dùng sử dụng Flama Connect để trích xuất câu ví dụ, định nghĩa khái niệm, thuật ngữ chuyên ngành, hình ảnh hoặc âm thanh từ các nguồn tài liệu học thuật và truyền thông bên ngoài.',
              'Flama chỉ cung cấp giao thức truyền tải kỹ thuật trung gian. Người dùng cam đoan và bảo đảm rằng nội dung khai thác chỉ phục vụ mục đích nghiên cứu, học tập cá nhân phi thương mại theo nguyên tắc sử dụng hợp lý (Fair Use) của pháp luật sở hữu trí tuệ.',
            ],
          },
          {
            id: 'terms-4-4',
            clauseNumber: '4.4',
            title: 'Tuyệt đối Cấm Phát tán & Tái thương mại hóa Nội dung Khai thác',
            content: [
              'Người dùng bị nghiêm cấm hoàn toàn việc đóng gói, chia sẻ công khai hoặc đăng bán trên Flama Marketplace các bộ thẻ chứa dữ liệu từ điển thương mại có bản quyền hoặc nội dung thuộc quyền sở hữu của bên thứ ba mà chưa có sự đồng ý bằng văn bản.',
            ],
          },
          {
            id: 'terms-4-5',
            clauseNumber: '4.5',
            title: 'Miễn trừ Trách nhiệm Tương thích Bên thứ ba',
            content: [
              'Dịch vụ Flama Connect được cung cấp trên nguyên tắc "AS-IS". Flama không bảo đảm tính tương thích liên tục khi các tiện ích mở rộng của bên thứ ba hoặc giao thức tiện ích trình duyệt (extension manifest) thay đổi phương thức kết nối hoặc chính sách bảo mật mà không báo trước.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-audio',
        clauseNumber: 'Điều 5',
        title: 'Dịch vụ Vệ tinh Flama Audio & Bản quyền Giọng đọc AI',
        summary: 'Điều khoản sử dụng ứng dụng máy tính Flama Audio, miễn trừ chi phí API bên thứ ba và quy chuẩn cấp phép giọng đọc AI.',
        content: [
          'Flama Audio là ứng dụng máy tính đồng hành độc lập dành cho người học, hỗ trợ tạo giọng đọc phát âm tự nhiên đa ngôn ngữ thông qua các công nghệ tổng hợp giọng nói cục bộ tiên tiến và các nhà cung cấp dịch vụ đám mây.',
        ],
        subClauses: [
          {
            id: 'terms-5-1',
            clauseNumber: '5.1',
            title: 'Khóa API Bên Thứ Ba & Trách nhiệm Cước phí Phát sinh',
            content: [
              'Khi người dùng cấu hình khóa API của các nhà cung cấp bên thứ ba (OpenAI, Microsoft Azure, Google Cloud) vào hồ sơ Flama, các khóa này được bảo vệ bằng tiêu chuẩn mã hóa công nghiệp đối xứng an toàn.',
              'Flama hoàn toàn không có quyền quản lý hóa đơn của bên thứ ba. Người dùng tự chịu trách nhiệm toàn bộ đối với các khoản phí phát sinh, hạn mức tiêu dùng và chính sách thanh toán của nhà cung cấp dịch vụ giọng đọc đám mây tương ứng.',
            ],
          },
          {
            id: 'terms-5-2',
            clauseNumber: '5.2',
            title: 'Độ Chuẩn xác Ngữ âm & Ảo giác Giọng đọc Nhân tạo (TTS Accuracy)',
            content: [
              'Âm thanh phát ra từ các mô hình mạng nơ-ron học sâu được tổng hợp hoàn toàn tự động. Flama không cam đoan về tính chính xác tuyệt đối của ngữ điệu, cách phát âm thuật ngữ chuyên ngành hay tính sư phạm của các tệp âm thanh này.',
              'Người dùng cần chủ động kiểm tra ngữ âm đối với các mục tiêu thi cử hoặc học tập chuyên sâu.',
            ],
          },
          {
            id: 'terms-5-3',
            clauseNumber: '5.3',
            title: 'Quy chuẩn Cấp phép Giọng đọc AI & Ghi nhận Quyền Tác giả (AI Voice Licensing & Attribution)',
            content: [
              'Các mô hình giọng đọc nhân tạo và công nghệ tổng hợp ngữ âm tích hợp trên Flama Audio (bao gồm các mô hình mã nguồn mở cục bộ và dịch vụ đám mây thương mại) chịu sự điều chỉnh của các điều khoản giấy phép mã nguồn mở hoặc thỏa thuận dịch vụ của từng đơn vị cung cấp tương ứng.',
              'Người dùng khi sử dụng âm thanh được tổng hợp từ các mô hình giọng đọc có yêu cầu ghi nhận nguồn trên các học liệu chia sẻ công khai có nghĩa vụ tuân thủ quy tắc dẫn nguồn (Attribution) theo hướng dẫn của nhà phát triển mô hình, đồng thời không được sử dụng giọng đọc vào các mục đích phỉ báng, xuyên tạc, thù địch, giả mạo giọng nói hoặc thương mại trái phép.',
            ],
          },
          {
            id: 'terms-5-4',
            clauseNumber: '5.4',
            title: 'Miễn trừ Phần mềm Máy trạm Ngoại vi',
            content: [
              'Ứng dụng Flama Audio hoạt động cục bộ trên hệ điều hành của người dùng. Flama không chịu trách nhiệm đối với sự cố xung đột phần cứng âm thanh, tài nguyên chiếm dụng CPU/GPU hoặc sự can thiệp của phần mềm diệt virus trên máy người học.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-suspension',
        clauseNumber: 'Điều 6',
        title: 'Đình chỉ Tài khoản, Chế tài Vi phạm & Chấm dứt Dịch vụ',
        summary: 'Cơ chế kỹ thuật khóa tài khoản, các hành vi dẫn tới chấm dứt quyền sử dụng và xử lý số dư ví vi phạm.',
        content: [
          'Để duy trì môi trường học tập tin cậy và an toàn cho toàn thể cộng đồng, Flama thực thi các quy tắc kiểm soát và chế tài kỷ luật nghiêm khắc.',
        ],
        subClauses: [
          {
            id: 'terms-6-1',
            clauseNumber: '6.1',
            title: 'Cơ chế Vô hiệu hóa Tài khoản & Ngắt Phiên Bảo mật',
            content: [
              'Khi tài khoản bị áp dụng biện pháp vô hiệu hóa do vi phạm, hệ thống Flama sẽ lập tức từ chối mọi phiên đăng nhập đang hoạt động với thông báo tài khoản bị tạm khóa, đồng thời hủy bỏ toàn bộ quyền truy cập của các mã xác thực kết nối liên quan.',
            ],
          },
          {
            id: 'terms-6-2',
            clauseNumber: '6.2',
            title: 'Các Căn cứ Đình chỉ hoặc Chấm dứt Tức thì',
            content: [
              'Flama có toàn quyền tạm ngừng, đình chỉ có thời hạn hoặc chấm dứt vĩnh viễn quyền truy cập của người dùng mà không cần thông báo trước trong các tình huống sau:',
              '1. Tấn công kỹ thuật: Khai thác lỗ hổng bảo mật, cào dữ liệu trái phép (scraping), cố tình chèn mã độc HTML/JavaScript vào thẻ flashcard, tấn công từ chối dịch vụ (DoS).',
              '2. Gian lận thanh toán: Sử dụng tài khoản ngân hàng phi pháp, chuyển khoản giả mạo hoặc gian lận tra soát đối với cổng payOS.',
              '3. Vi phạm bản quyền nhiều lần: Tái phạm việc tải lên các tài liệu học tập vi phạm sở hữu trí tuệ theo Quy chế Ba Lần Vi phạm (Three-Strike Rule).',
              '4. Hành vi độc hại: Phát tán ngôn từ thù địch, nội dung khiêu dâm, quấy rối các thành viên khác trong hệ thống hỗ trợ và đóng góp bộ thẻ.',
            ],
          },
          {
            id: 'terms-6-3',
            clauseNumber: '6.3',
            title: 'Hậu quả Chấm dứt Dịch vụ do Vi phạm',
            content: [
              'Tài khoản bị chấm dứt vĩnh viễn do vi phạm nghiêm trọng sẽ bị hủy bỏ toàn bộ quyền truy cập vào các gói học liệu đã mua. Mọi khoản số dư lưu ký trong ví phát sinh từ hành vi gian lận hoặc vi phạm bản quyền sẽ bị phong tỏa và xử lý theo quy định pháp luật.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-liability',
        clauseNumber: 'Điều 7',
        title: 'Giới hạn Trách nhiệm Pháp lý & Sự kiện Bất khả Kháng',
        summary: 'Tuyên bố miễn trừ bảo đảm học tập, giới hạn mức bồi thường tối đa 500.000 VNĐ và trường hợp bất khả kháng.',
        content: [
          'Trong giới hạn tối đa được pháp luật Việt Nam cho phép, trách nhiệm pháp lý của Flama đối với các rủi ro kỹ thuật và dịch vụ được xác lập như sau.',
        ],
        subClauses: [
          {
            id: 'terms-7-1',
            clauseNumber: '7.1',
            title: 'Tuyên bố Cung cấp Dịch vụ "Nguyên trạng" (AS-IS)',
            content: [
              'Nền tảng, giao diện web, thuật toán học tập và các dịch vụ vệ tinh được cung cấp trên nguyên tắc "AS-IS" và "AS-AVAILABLE". Flama không đưa ra bất kỳ bảo đảm ngụ ý hay tường minh nào về việc dịch vụ sẽ hoàn toàn không bị gián đoạn, không có lỗi nhỏ hoặc hoàn toàn đáp ứng kỳ vọng cá nhân của mọi người học.',
            ],
          },
          {
            id: 'terms-7-2',
            clauseNumber: '7.2',
            title: 'Miễn trừ Kết quả Học tập & Thi cử Học thuật',
            content: [
              'Flama là một công cụ hỗ trợ ghi nhớ và tối ưu hóa thời gian ôn tập tri thức. Flama không đưa ra bất kỳ sự bảo đảm nào rằng việc học tập trên nền tảng sẽ giúp người học vượt qua các kỳ thi chứng chỉ, bài kiểm tra khảo thí chuyên môn hoặc đạt được các mục tiêu học thuật cụ thể.',
            ],
          },
          {
            id: 'terms-7-3',
            clauseNumber: '7.3',
            title: 'Giới hạn Bồi thường Tối đa (Aggregate Liability Cap)',
            content: [
              'Trong mọi trường hợp phát sinh tranh chấp hoặc thiệt hại được xác định có lỗi trực tiếp từ Flama, tổng mức bồi thường thiệt hại tối đa mà Flama phải chịu đối với một người dùng sẽ không vượt quá số tiền lớn hơn giữa:',
              '(a) Tổng số tiền mà người dùng đó đã thanh toán cho Flama trong vòng ba (03) tháng gần nhất trước ngày phát sinh tranh chấp; hoặc',
              '(b) 500.000 VNĐ (Năm trăm nghìn đồng Việt Nam).',
            ],
          },
          {
            id: 'terms-7-4',
            clauseNumber: '7.4',
            title: 'Sự kiện Bất khả Kháng (Force Majeure)',
            content: [
              'Flama được miễn trừ toàn bộ trách nhiệm trong trường hợp dịch vụ bị gián đoạn do các sự kiện nằm ngoài tầm kiểm soát hợp lý, bao gồm sự cố đứt cáp quang quốc tế, lỗi hệ thống máy chủ đám mây, sự cố kỹ thuật của mạng lưới ngân hàng quốc gia, thiên tai, dịch bệnh hoặc các quyết định hành chính từ cơ quan nhà nước có thẩm quyền.',
            ],
          },
        ],
      },
      {
        id: 'clause-terms-governing',
        clauseNumber: 'Điều 8',
        title: 'Luật Áp dụng & Thẩm quyền Giải quyết Tranh chấp',
        summary: 'Xác định hệ thống pháp luật điều chỉnh và cơ chế tòa án tài phán tại Việt Nam.',
        content: [
          'Bản Điều khoản Sử dụng Dịch vụ này được giải thích và điều chỉnh toàn diện theo hệ thống pháp luật của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.',
          'Mọi tranh chấp phát sinh từ hoặc liên quan đến việc sử dụng nền tảng trước hết sẽ được giải quyết thông qua thương lượng thiện chí giữa các bên. Trường hợp không thể thương lượng thành công trong vòng ba mươi (30) ngày, tranh chấp sẽ được đệ trình lên Tòa án Nhân dân có thẩm quyền tại Việt Nam để giải quyết theo luật định.',
        ],
      },
    ],
  },

  privacy: {
    id: 'privacy',
    title: 'Chính sách Bảo mật Dữ liệu & Quyền Riêng tư',
    officialBadge: 'Tuân thủ Nghị định 13/2023/NĐ-CP',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 16,
    executiveSummary:
      'Chính sách Bảo mật của Flama được thiết lập tuân thủ nghiêm ngặt Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân. Tài liệu này minh bạch toàn bộ dữ liệu thu thập, công khai các nhóm thông số thuật toán Lặp lại Ngắt quãng (Spaced Repetition), phân lập dữ liệu tài chính qua payOS, và bảo đảm quyền yêu cầu xóa vĩnh viễn dữ liệu (Right to be Forgotten) cho người học.',
    clauses: [
      {
        id: 'clause-privacy-framework',
        clauseNumber: 'Điều 1',
        title: 'Khung Pháp lý & Nguyên tắc Xử lý Dữ liệu Cá nhân',
        summary: 'Căn cứ Nghị định 13/2023/NĐ-CP và các nguyên tắc bảo vệ quyền riêng tư người học.',
        content: [
          'Flama cam kết bảo vệ dữ liệu cá nhân của người học theo các tiêu chuẩn cao nhất của pháp luật Việt Nam, đặc biệt là Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân, Luật An toàn thông tin mạng và Luật An ninh mạng.',
        ],
        subClauses: [
          {
            id: 'privacy-1-1',
            clauseNumber: '1.1',
            title: 'Vai trò Pháp lý của Flama',
            content: [
              'Trong khuôn khổ cung cấp dịch vụ học tập, Flama đóng vai trò là Bên Kiểm soát và Xử lý Dữ liệu Cá nhân (Personal Data Controller and Processor) đối với các thông tin tài khoản và dữ liệu tiến độ học tập do người dùng tạo lập trên hệ thống.',
            ],
          },
          {
            id: 'privacy-1-2',
            clauseNumber: '1.2',
            title: 'Các Nguyên tắc Cốt lõi',
            content: [
              '1. Hợp pháp và Minh bạch: Dữ liệu chỉ được thu thập khi có sự đồng ý rõ ràng của người học và được công khai mục đích xử lý.',
              '2. Giới hạn Mục đích: Dữ liệu học tập chỉ phục vụ duy nhất mục tiêu tối ưu hóa khả năng ghi nhớ kiến thức của chính người học.',
              '3. Tối thiểu hóa Dữ liệu: Chỉ thu thập các trường thông tin cần thiết phục vụ vận hành thuật toán và giao dịch số.',
              '4. Toàn vẹn và Bảo mật: Áp dụng các biện pháp mã hóa tiên tiến nhằm ngăn chặn rò rỉ, truy cập trái phép hoặc mất mát dữ liệu.',
            ],
          },
        ],
      },
      {
        id: 'clause-privacy-taxonomy',
        clauseNumber: 'Điều 2',
        title: 'Danh mục & Phân loại Dữ liệu Cá nhân Thu thập',
        summary: 'Bóc tách 4 tầng dữ liệu: định danh cơ bản, tiến độ học tập, tham chiếu thanh toán payOS và nhật ký kỹ thuật.',
        content: [
          'Căn cứ Điều 2 Nghị định 13/2023/NĐ-CP, Flama phân loại và thu thập các nhóm dữ liệu cá nhân cụ thể sau:',
        ],
        subClauses: [
          {
            id: 'privacy-2-1',
            clauseNumber: '2.1',
            title: 'Dữ liệu Cá nhân Cơ bản (Basic Personal Data)',
            content: [
              'Bao gồm: Họ tên hiển thị, địa chỉ email, chuỗi mật khẩu đã được mã hóa an toàn theo tiêu chuẩn mã hóa công nghiệp, ảnh đại diện (avatar), phần giới thiệu tiểu sử cá nhân, và tùy chọn múi giờ địa phương (e.g. Asia/Ho_Chi_Minh).',
              'Trường hợp người học đăng nhập liên kết qua tài khoản của bên thứ ba (như Google), hệ thống chỉ tiếp nhận và lưu trữ mã định danh tài khoản duy nhất cùng địa chỉ email được cấp quyền.',
            ],
          },
          {
            id: 'privacy-2-2',
            clauseNumber: '2.2',
            title: 'Dữ liệu Học tập & Tiến độ Ghi nhớ (Learning Telemetry)',
            content: [
              'Bao gồm: Danh sách các bộ thẻ cá nhân, thẻ flashcard, các trường nội dung học liệu và khái niệm kiến thức, số lần lật thẻ, nhật ký thời gian hoàn thành các phiên ôn tập.',
            ],
          },
          {
            id: 'privacy-2-3',
            clauseNumber: '2.3',
            title: 'Dữ liệu Giao dịch Tài chính (Phân lập Tuyệt đối qua payOS)',
            content: [
              'Flama TUYỆT ĐỐI KHÔNG thu thập, không xử lý và không lưu trữ thông tin số thẻ ngân hàng, số thẻ tín dụng, ngày hết hạn hoặc mã số bảo mật CVV/CVC của người dùng.',
              'Hệ thống Flama chỉ lưu giữ các chứng từ giao dịch tài chính phi định danh do payOS cung cấp phục vụ việc kích hoạt quyền nội dung và đối soát thuế, gồm: Mã đơn hàng giao dịch, mã tham chiếu thanh toán, số tiền thanh toán (VND), thời gian giao dịch và trạng thái cấp quyền.',
            ],
          },
          {
            id: 'privacy-2-4',
            clauseNumber: '2.4',
            title: 'Dữ liệu Kỹ thuật & Phiên Truy cập Hệ thống',
            content: [
              'Bao gồm địa chỉ giao thức mạng (IP address), chuỗi định danh trình duyệt (User-Agent), nhật ký bảo mật đăng nhập, các token xác thực phiên làm việc và cấu hình hiển thị giao diện.',
            ],
          },
        ],
        callout: {
          type: 'info',
          label: 'Cam kết Phân lập Hạ tầng Thanh toán',
          text: 'Toàn bộ thao tác nhập thông tin tài khoản ngân hàng hoặc quét mã QR diễn ra trên hạ tầng bảo mật độc lập của payOS và ứng dụng ngân hàng của người dùng. Flama không bao giờ tiếp cận dữ liệu nhạy cảm của thẻ thanh toán.',
        },
      },
      {
        id: 'clause-privacy-srs',
        clauseNumber: 'Điều 3',
        title: 'Minh bạch Thuật toán Lặp lại Ngắt quãng (Spaced Repetition Telemetry)',
        summary: 'Minh bạch cơ sở khoa học của đường cong quên lãng Ebbinghaus và các nhóm dữ liệu phản xạ được ghi nhận trong mỗi phiên ôn tập.',
        content: [
          'Thuật toán Spaced Repetition vận hành dựa trên nguyên lý khoa học về Đường cong Quên lãng Ebbinghaus nhằm tính toán thời điểm vàng để ôn tập lại một đơn vị kiến thức trước khi não bộ quên lãng. Toàn bộ dữ liệu này chỉ nhằm phục vụ việc phân phối thẻ học cho chính bạn.',
        ],
        subClauses: [
          {
            id: 'privacy-3-1',
            clauseNumber: '3.1',
            title: 'Giới hạn Mục đích Nghiêm ngặt (Purpose Limitation)',
            content: [
              'Dữ liệu phản hồi thẻ học chỉ được sử dụng cho việc tính toán khoảng cách ôn tập tiếp theo. Dữ liệu này không bao giờ được bán cho các bên thứ ba, không phục vụ mục đích xây dựng hồ sơ thương mại (commercial profiling) và không bao giờ dùng cho quảng cáo hướng đối tượng.',
            ],
          },
          {
            id: 'privacy-3-2',
            clauseNumber: '3.2',
            title: 'Các Nhóm Thông số Thuật toán Thu thập Trong Mỗi Lần Ôn Tập',
            content: [
              'Trong mỗi lượt tương tác thẻ học, hệ thống ghi nhận các nhóm thông số chuẩn xác nhằm phục vụ cá nhân hóa lộ trình ghi nhớ:',
              '1. Thông số phản xạ thời gian: Mốc thời gian thực hiện thao tác đánh giá và khoảng thời gian phản hồi nhận thức tính từ thời điểm mở thẻ đến khi người học đưa ra lựa chọn.',
              '2. Lịch sử đánh giá ghi nhớ: Đánh giá chủ quan về mức độ nhớ lại kiến thức (các cấp độ: cần ôn lại, khó, tốt, dễ) và trạng thái phân bổ thẻ trong chu kỳ tiếp thu.',
              '3. Tiến trình và tần suất củng cố: Bước học trong chu kỳ ngắn hạn trong ngày, tổng số lượt ôn tập thành công và số lần cần củng cố lại khi kiến thức bị gián đoạn.',
              '4. Tự động điều chỉnh khoảng cách ôn tập: Các chỉ số toán học ước tính độ bền vững của ký ức, độ khó nhận thức của học liệu và thời điểm đến hạn ôn tập kế tiếp được chuẩn hóa theo múi giờ cá nhân.',
            ],
          },
          {
            id: 'privacy-3-3',
            clauseNumber: '3.3',
            title: 'Cơ chế Tự động Tạm hoãn Thẻ Cần Củng cố (Auto-Suspension)',
            content: [
              'Khi một chiếc thẻ có số lần ghi nhớ không thành công vượt quá ngưỡng quy định, thuật toán sẽ tự động đưa thẻ vào nhóm cần củng cố nhận thức và tạm dừng đưa vào phiên ôn tập tự động. Tính năng này bảo vệ người học khỏi việc rơi vào vòng lặp ghi nhớ tiêu cực gây mệt mỏi nhận thức và giúp người học chủ động rà soát lại phương pháp tiếp cận kiến thức.',
            ],
          },
        ],
      },
      {
        id: 'clause-privacy-rights',
        clauseNumber: 'Điều 4',
        title: 'Quyền của Chủ thể Dữ liệu theo Điều 9 Nghị định 13/2023/NĐ-CP',
        summary: 'Hiện thực hóa toàn diện 11 quyền hợp pháp của người dùng trên hệ thống Flama.',
        content: [
          'Flama tôn trọng và cung cấp đầy đủ các công cụ kỹ thuật và kênh vận hành để người học thực thi trọn vẹn 11 quyền của chủ thể dữ liệu theo Điều 9 Nghị định 13/2023/NĐ-CP:',
          '1. Quyền được biết: Được thông báo rõ ràng về các hoạt động xử lý dữ liệu qua Chính sách này.',
          '2. Quyền đồng ý: Đồng ý hoặc từ chối cung cấp dữ liệu tùy chọn khi đăng ký.',
          '3. Quyền truy cập: Xem toàn bộ dữ liệu hồ sơ cá nhân và bảng tiến độ học tập trên trang Dashboard và Profile.',
          '4. Quyền rút lại sự đồng ý: Hủy bỏ sự đồng ý đã cấp bằng cách vô hiệu hóa tài khoản hoặc liên hệ kênh hỗ trợ.',
          '5. Quyền xóa dữ liệu (Right to Erasure): Yêu cầu xóa vĩnh viễn dữ liệu tài khoản và học tập của mình.',
          '6. Quyền hạn chế xử lý dữ liệu: Yêu cầu tạm ngừng xử lý dữ liệu thông qua tính năng khóa tài khoản.',
          '7. Quyền cung cấp / Di chuyển dữ liệu (Data Portability): Tải về các bộ thẻ cá nhân dưới định dạng gói học liệu chuẩn mở (.apkg, CSV) và xuất phiếu bài tập in ấn.',
          '8. Quyền phản đối xử lý: Phản đối việc sử dụng dữ liệu cho các mục đích thống kê học thuật không bắt buộc.',
          '9. Quyền khiếu nại, tố cáo: Gửi khiếu nại trực tiếp đến hòm thư chuyên trách bảo mật của Flama hoặc cơ quan nhà nước.',
          '10. Quyền yêu cầu bồi thường thiệt hại: Khi có hành vi vi phạm pháp luật bảo vệ dữ liệu gây thiệt hại thực tế.',
          '11. Quyền tự bảo vệ: Sử dụng các công cụ đổi mật khẩu, đăng xuất từ xa và quản lý khóa truy cập API.',
        ],
      },
      {
        id: 'clause-privacy-erasure',
        clauseNumber: 'Điều 5',
        title: 'Cơ chế Xóa Dữ liệu Tầng bậc & Ngoại lệ Luật Kế toán',
        summary: 'Quy trình xóa sạch dữ liệu học tập và bảo lưu chứng từ giao dịch phục vụ nghĩa vụ thuế nhà nước.',
        content: [
          'Khi người dùng thực thi quyền xóa vĩnh viễn dữ liệu cá nhân hoặc chấm dứt tài khoản, Flama kích hoạt quy trình xóa dữ liệu kỹ thuật theo hai luồng xử lý riêng biệt:',
        ],
        subClauses: [
          {
            id: 'privacy-5-1',
            clauseNumber: '5.1',
            title: 'Quy trình Tiêu hủy Dữ liệu Liên đới Tự động',
            content: [
              'Hệ thống thực thi cơ chế xóa tầng bậc tự động triệt để nhằm lập tức và vĩnh viễn tiêu hủy các dữ liệu sau: Hồ sơ người dùng, các liên kết định danh bên ngoài, bản ghi học tập và lịch sử ôn tập chi tiết, dữ liệu tiến độ thẻ học, cấu hình thuật toán và các phiên làm việc bảo mật.',
            ],
          },
          {
            id: 'privacy-5-2',
            clauseNumber: '5.2',
            title: 'Ngoại lệ Lưu trữ Dữ liệu Tài chính theo Luật Kế toán',
            content: [
              'Căn cứ Điều 16 và Điều 17 Nghị định 13/2023/NĐ-CP cùng Luật Kế toán và Luật Quản lý Thuế Việt Nam, các chứng từ giao dịch phát sinh dòng tiền không được phép xóa bỏ ngay nhằm phục vụ nghĩa vụ quyết toán thuế và thanh tra tài chính theo luật định.',
              'Để bảo đảm quyền riêng tư, hệ thống Flama thực hiện cơ chế vô danh hóa toàn diện: toàn bộ mối liên kết định danh cá nhân đối với các chứng từ giao dịch tài chính đều được hủy bỏ vĩnh viễn. Danh tính của người dùng được cắt đứt hoàn toàn khỏi bản ghi thanh toán, chỉ bảo lưu các chứng từ giao dịch tài chính phi định danh phục vụ công tác thanh tra thuế theo luật định.',
            ],
          },
        ],
        callout: {
          type: 'statutory',
          label: 'Ngoại lệ Luật định',
          text: 'Việc bảo lưu chứng từ tài chính phi định danh là nghĩa vụ pháp lý bắt buộc theo Luật Kế toán Việt Nam và không cấu thành hành vi vi phạm quyền xóa dữ liệu cá nhân.',
        },
      },
      {
        id: 'clause-privacy-breach',
        clauseNumber: 'Điều 6',
        title: 'Thông báo Sự cố Dữ liệu Cá nhân (Breach Notification SLA)',
        summary: 'Cam kết tuân thủ thời hạn thông báo 72 giờ tới cơ quan quản lý A05 và thông tin liên hệ Cán bộ DPO.',
        content: [
          'Trong trường hợp phát hiện sự cố an ninh mạng dẫn đến rủi ro rò rỉ, mất mát hoặc truy cập trái phép vào dữ liệu cá nhân của người học, Flama cam kết:',
          '1. Thông báo tới Cơ quan Quản lý Nhà nước: Báo cáo bằng văn bản tới Cục An ninh mạng và phòng, chống tội phạm sử dụng công nghệ cao (A05 - Bộ Công an) trong vòng bảy mươi hai (72) giờ kể từ thời điểm phát hiện sự cố, theo đúng quy định tại Điều 23 Nghị định 13/2023/NĐ-CP.',
          '2. Cảnh báo tới Người dùng: Thông báo ngay lập tức tới những người dùng bị ảnh hưởng qua email và giao diện thông báo hệ thống, kèm theo khuyến nghị các biện pháp giảm thiểu thiệt hại (như đổi mật khẩu, thu hồi mã xác thực truy cập).',
        ],
        subClauses: [
          {
            id: 'privacy-6-1',
            clauseNumber: '6.1',
            title: 'Kênh Tiếp nhận Liên hệ Bảo vệ Dữ liệu (DPO)',
            content: [
              'Mọi thắc mắc, khiếu nại hoặc yêu cầu thực thi quyền liên quan đến dữ liệu cá nhân xin vui lòng gửi về: Cán bộ Phụ trách Bảo vệ Dữ liệu (Data Protection Officer) Flama qua email: privacy@flama.vn hoặc gửi yêu cầu qua kênh Hỗ trợ người dùng (/support).',
            ],
          },
        ],
      },
    ],
  },

  'marketplace-guidelines': {
    id: 'marketplace-guidelines',
    title: 'Quy chế Hoạt động Marketplace & Bản quyền Trí tuệ',
    officialBadge: 'Khung Bản quyền & Clone Overlay v2.0',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 15,
    executiveSummary:
      'Quy chế này phân định rành mạch quyền sở hữu trí tuệ giữa Nền tảng Flama, Tác giả tạo bộ thẻ (Deck Creators) và Người học (Learners). Văn bản làm rõ cơ chế khiên bảo vệ pháp lý của kiến trúc Clone Overlay và quy trình tiếp nhận, xử lý khiếu nại bản quyền (Notice & Takedown) chuẩn mực.',
    clauses: [
      {
        id: 'clause-market-division',
        clauseNumber: 'Điều 1',
        title: 'Phân định Ba Tầng Quyền Sở hữu Trí tuệ (Three-Way IP Division)',
        summary: 'Xác lập ranh giới quyền sở hữu trí tuệ tuyệt đối giữa Nền tảng, Tác giả và Người học.',
        content: [
          'Mô hình học liệu chia sẻ trên Flama thiết lập cấu trúc phân định bản quyền ba bên minh bạch nhằm bảo đảm quyền lợi hợp pháp của từng chủ thể tham gia:',
        ],
        subClauses: [
          {
            id: 'market-1-1',
            clauseNumber: '1.1',
            title: 'Quyền Sở hữu của Nền tảng Flama (Platform IP)',
            content: [
              'Flama sở hữu độc quyền toàn bộ mã nguồn phần mềm, thiết kế giao diện (UI/UX), kiến trúc cơ sở dữ liệu, thuật toán Spaced Repetition, hạ tầng kỹ thuật Clone Overlay, nhãn hiệu thương mại "Flama", biểu trưng và tên miền flama.vn.',
              'Không người dùng hay tác giả nào có quyền sao chép, dịch ngược mã nguồn (reverse engineer), cào dữ liệu hoặc sử dụng nhãn hiệu của Flama cho mục đích thương mại riêng mà không có văn bản chấp thuận trước.',
            ],
          },
          {
            id: 'market-1-2',
            clauseNumber: '1.2',
            title: 'Quyền Sở hữu của Tác giả Tạo bộ thẻ (Deck Creators IP)',
            content: [
              'Tác giả bảo lưu toàn vẹn quyền tác giả và quyền sở hữu trí tuệ đối với các nội dung do mình tự biên soạn, bao gồm: Văn bản giải thích ngữ pháp, ví dụ tự sáng tác, mẹo ghi nhớ độc quyền, cấu trúc giáo trình thẻ học, và các tệp âm thanh bản thu giọng đọc do chính tác giả thu âm.',
              'Bằng việc đăng tải bộ thẻ lên Flama Marketplace (miễn phí hoặc có phí), Tác giả cấp cho Flama giấy phép không độc quyền, có hiệu lực trên toàn cầu, miễn phí bản quyền (ngoài phần doanh thu thỏa thuận trên sàn) để lưu trữ, lập chỉ mục tìm kiếm, hiển thị, truyền phát âm thanh và phân phối quyền truy cập cho những người học đã cài đặt.',
            ],
          },
          {
            id: 'market-1-3',
            clauseNumber: '1.3',
            title: 'Quyền Sở hữu của Người học (Learners IP)',
            content: [
              'Người học sở hữu toàn bộ các ghi chú cá nhân, lớp trường nội dung tùy biến cá nhân, thẻ học bổ sung thêm, và toàn bộ lịch sử, dữ liệu tiến độ ghi nhớ SRS của bản thân.',
              'Ghi chú cá nhân của người học được bảo mật hoàn toàn trong bản cài đặt của họ và không bao giờ bị tự động chuyển giao cho tác giả gốc hay bên thứ ba trừ khi người học chủ động gửi yêu cầu đóng góp sửa đổi (Deck Change Request).',
            ],
          },
        ],
      },
      {
        id: 'clause-market-overlay',
        clauseNumber: 'Điều 2',
        title: 'Cơ chế Pháp lý & Khiên Bảo vệ của Kiến trúc Clone Overlay',
        summary: 'Kiến trúc Lớp phủ Logic Độc lập (Logical Overlay Architecture) và hai lớp khiên bảo vệ tác giả chống đánh cắp bộ thẻ và bảo toàn lịch sử người học.',
        content: [
          'Khác với các nền tảng flashcard truyền thống sao chép nhân đôi toàn bộ dữ liệu gây rủi ro thất thoát bản quyền, Flama ứng dụng mô hình Lớp phủ Logic (Logical Overlay Architecture) độc quyền nhằm phân lập độc lập giữa nội dung gốc của tác giả và không gian học tập cá nhân.',
        ],
        subClauses: [
          {
            id: 'market-2-1',
            clauseNumber: '2.1',
            title: 'Bản chất Cài đặt Lớp phủ Logic Độc lập',
            content: [
              'Khi người học cài đặt một bộ thẻ từ Marketplace, hệ thống không tạo bản sao trùng lặp nội dung gốc trong cơ sở dữ liệu. Bản cài đặt của người học liên kết trực tiếp với bản phát hành chính thức của tác giả.',
              'Mọi chỉnh sửa của người học chỉ được lưu dưới dạng lớp ghi chú cá nhân hóa độc lập trên tài khoản của người học và tuyệt đối không làm thay đổi bản ghi gốc của tác giả.',
            ],
          },
          {
            id: 'market-2-2',
            clauseNumber: '2.2',
            title: 'Khiên Chống Đánh cắp Bản quyền cho Tác giả (Anti-Theft Shield)',
            content: [
              'Bởi vì người học không sở hữu bản sao cơ sở dữ liệu độc lập của bộ thẻ, người học không thể xuất khẩu hoặc đăng bán lại bộ thẻ của tác giả như một sản phẩm mới độc lập trên Flama Marketplace.',
              'Cơ chế này triệt tiêu hoàn toàn vấn nạn "nhân bản lậu" và bảo vệ công sức nghiên cứu giáo trình của các tác giả chân chính.',
            ],
          },
          {
            id: 'market-2-3',
            clauseNumber: '2.3',
            title: 'Khiên Bảo toàn Thành quả Học tập cho Người học (Study Investment Shield)',
            content: [
              'Người học dành nhiều thời gian để tích lũy dữ liệu phản xạ trí nhớ. Dữ liệu tiến độ học tập và lịch sử phản xạ trí nhớ được neo chặt an toàn vào tài khoản cá nhân của người học.',
              'Ngay cả khi tác giả gỡ bỏ, ẩn hoặc xóa bộ thẻ khỏi Marketplace công cộng, các bản cài đặt lớp phủ hiện hữu của người học vẫn tiếp tục hoạt động vĩnh viễn trong không gian học tập cá nhân. Thành quả học tập của người học không bao giờ bị tước đoạt.',
            ],
          },
          {
            id: 'market-2-4',
            clauseNumber: '2.4',
            title: 'Đề xuất Đóng góp Chỉnh sửa (Deck Change Request)',
            content: [
              'Người học có thể gửi các đề xuất sửa lỗi chính tả hoặc cải thiện ngữ nghĩa ngược lại cho tác giả thông qua chức năng Deck Change Request.',
              'Bằng việc gửi đề xuất này, người học cấp cho tác giả quyền phi độc quyền, vĩnh viễn để tích hợp đề xuất đó vào các bản phát hành cập nhật trong tương lai.',
            ],
          },
        ],
      },
      {
        id: 'clause-market-standards',
        clauseNumber: 'Điều 3',
        title: 'Tiêu chuẩn Nội dung Bản quyền & Danh mục Cấm Đăng tải',
        summary: 'Quy tắc nghiêm cấm sao chép giáo trình thương mại, đề thi chưa công bố và dữ liệu từ điển thương mại.',
        content: [
          'Mọi học liệu đưa lên Marketplace phải là sản phẩm sáng tạo trí tuệ hợp pháp của tác giả hoặc sử dụng các nguồn tư liệu học tập mở được cấp phép hợp lệ.',
          'Nghiêm cấm tuyệt đối các hành vi sau trên Flama Marketplace:',
          '1. Quét (scan), sao chép nguyên văn sách giáo khoa, giáo trình thương mại đang có bản quyền bảo hộ thuộc mọi chuyên ngành khi chưa có sự cho phép bằng văn bản từ chủ sở hữu quyền hoặc nhà xuất bản.',
          '2. Phát tán đề thi chính thức của các kỳ thi chuẩn hóa, chứng chỉ nghề nghiệp hoặc khảo thí học thuật chưa được các tổ chức khảo thí công bố công khai hợp pháp.',
          '3. Trích xuất trái phép toàn bộ cơ sở dữ liệu của các từ điển thương mại có bản quyền.',
          '4. Tải lên các tệp âm thanh, bài hát hoặc hình ảnh vi phạm bản quyền của bên thứ ba.',
        ],
        callout: {
          type: 'warning',
          label: 'Quy tắc Không Khoan nhượng với Học liệu Lậu',
          text: 'Flama chủ động rà quét và áp dụng biện pháp gỡ bỏ ngay lập tức đối với bất kỳ bộ thẻ nào sao chép trái phép sách giáo khoa thương mại hoặc vi phạm bản quyền xuất bản.',
        },
      },
      {
        id: 'clause-market-takedown',
        clauseNumber: 'Điều 4',
        title: 'Quy trình Tiếp nhận & Xử lý Khiếu nại Bản quyền (Notice & Takedown)',
        summary: 'Thời hạn phản hồi 24-48 giờ, cách ly học liệu, quyền phản biện trong 10 ngày và thời hạn khởi kiện tòa án 14 ngày.',
        content: [
          'Flama tôn trọng quyền sở hữu trí tuệ của các tổ chức, cá nhân và vận hành quy trình Tiếp nhận và Xử lý Khiếu nại Bản quyền (Notice & Takedown) tuân thủ Luật Sở hữu trí tuệ Việt Nam và các hiệp ước quốc tế:',
        ],
        subClauses: [
          {
            id: 'market-4-1',
            clauseNumber: '4.1',
            title: 'Nội dung Đơn Khiếu nại Bản quyền Hợp lệ',
            content: [
              'Chủ sở hữu quyền tác giả hoặc người đại diện hợp pháp gửi thông báo khiếu nại tới địa chỉ email: legal@flama.vn hoặc gửi qua kênh Hỗ trợ (/support), bao gồm:',
              '(a) Chữ ký điện tử hoặc chữ ký thực của chủ sở hữu quyền hoặc đại diện được ủy quyền;',
              '(b) Mô tả tác phẩm gốc bị vi phạm kèm tài liệu chứng minh quyền sở hữu;',
              '(c) Đường dẫn URL chính xác hoặc mã định danh của bộ thẻ vi phạm trên Flama;',
              '(d) Thông tin liên hệ đầy đủ (họ tên, email, số điện thoại, địa chỉ);',
              '(e) Cam đoan bằng văn bản rằng thông tin trong đơn là trung thực và chịu trách nhiệm trước pháp luật về việc khiếu nại.',
            ],
          },
          {
            id: 'market-4-2',
            clauseNumber: '4.2',
            title: 'Thời hạn Xác minh & Chế tài Cách ly Khẩn cấp (24 - 48h SLA)',
            content: [
              'Trong thời hạn từ 24 đến 48 giờ làm việc kể từ thời điểm nhận được đơn khiếu nại hợp lệ, đội ngũ pháp lý của Flama sẽ tiến hành rà soát kỹ thuật ban đầu.',
              'Nếu đơn có căn cứ hợp lý, Flama sẽ lập tức áp dụng biện pháp cách ly tạm thời: chuyển trạng thái bộ thẻ sang chế độ lưu trữ riêng tư hoặc cách ly tạm thời, loại bỏ khỏi kết quả tìm kiếm Marketplace và gửi thông báo kèm bản sao khiếu nại tới tác giả bị tố cáo.',
            ],
          },
          {
            id: 'market-4-3',
            clauseNumber: '4.3',
            title: 'Quy trình Phản hồi Khiếu nại của Tác giả (Counter-Notice: 10 Ngày)',
            content: [
              'Tác giả có thời hạn mười (10) ngày làm việc kể từ khi nhận thông báo cách ly để gửi Đơn Phản hồi Khiếu nại (Counter-Notice) chứng minh quyền sử dụng hợp pháp của mình.',
              'Nếu tác giả không phản hồi hoặc thừa nhận hành vi vi phạm, bộ thẻ sẽ bị gỡ bỏ vĩnh viễn khỏi hệ thống.',
            ],
          },
          {
            id: 'market-4-4',
            clauseNumber: '4.4',
            title: 'Thời hạn Khởi kiện & Khôi phục Học liệu (14 Ngày)',
            content: [
              'Khi nhận được Counter-Notice hợp lệ từ tác giả, Flama sẽ chuyển tiếp văn bản này tới bên khiếu nại. Bên khiếu nại có thời hạn mười bốn (14) ngày làm việc để cung cấp chứng từ thụ lý vụ án của Tòa án có thẩm quyền.',
              'Nếu hết 14 ngày làm việc mà bên khiếu nại không cung cấp được bằng chứng khởi kiện, Flama có quyền khôi phục trạng thái hoạt động bình thường của bộ thẻ trên Marketplace.',
            ],
          },
        ],
      },
      {
        id: 'clause-market-strikes',
        clauseNumber: 'Điều 5',
        title: 'Chính sách Xử lý Tái phạm Bản quyền (Three-Strike Policy)',
        summary: 'Cơ chế xử phạt lũy tiến: Cảnh cáo -> Đình chỉ 30 ngày -> Thu hồi vĩnh viễn và tịch thu doanh thu vi phạm.',
        content: [
          'Nhằm ngăn ngừa hành vi cố tình vi phạm bản quyền trục lợi, Flama áp dụng chế tài Ba Lần Vi phạm (Three-Strike Repeat Infringer Policy):',
          '1. Lần vi phạm thứ nhất (Strike 1): Gửi cảnh cáo chính thức, gỡ bỏ học liệu vi phạm, yêu cầu tác giả cam kết lại quy chế bản quyền.',
          '2. Lần vi phạm thứ hai (Strike 2): Trong vòng 12 tháng kể từ lần vi phạm trước, tác giả sẽ bị đình chỉ quyền phát hành bộ thẻ mới trên Marketplace trong ba mươi (30) ngày, đồng thời tạm phong tỏa các khoản chi trả doanh thu liên quan.',
          '3. Lần vi phạm thứ ba (Strike 3): Tác giả tái phạm lần thứ 3 sẽ bị tước vĩnh viễn tư cách phát hành học liệu trên Marketplace, tịch thu toàn bộ số dư doanh thu thu được từ các sản phẩm vi phạm bản quyền và khóa vĩnh viễn tài khoản người dùng.',
        ],
      },
    ],
  },

  'community-guidelines': {
    id: 'community-guidelines',
    title: 'Chuẩn mực Cộng đồng & Quy tắc Ứng xử Người dùng',
    officialBadge: 'Tiêu chuẩn Đạo đức & Văn hóa Học tập',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 12,
    executiveSummary:
      'Chuẩn mực Cộng đồng Flama thiết lập các ranh giới đạo đức và quy chuẩn an toàn bắt buộc cho mọi người học và tác giả. Quy chế này quy định cụ thể về việc cấm phát tán mã độc qua thẻ flashcard, cấm cào dữ liệu tự động, loại bỏ ngôn từ độc hại và quy trình tiếp nhận xử lý tố cáo qua hệ thống phiếu hỗ trợ.',
    clauses: [
      {
        id: 'clause-comm-mission',
        clauseNumber: 'Điều 1',
        title: 'Sứ mệnh Cộng đồng & Tôn chỉ Học tập Tương trợ',
        summary: 'Xây dựng môi trường học tập và ghi nhớ tri thức văn minh, an toàn, tôn trọng và giàu tính xây dựng.',
        content: [
          'Flama hướng đến mục tiêu trở thành nền tảng học tập và ghi nhớ tri thức toàn diện đa lĩnh vực, văn minh và truyền cảm hứng. Chúng tôi tin rằng hiệu quả tiếp thu tri thức chỉ đạt mức cao nhất trong một môi trường an toàn, tôn trọng sự đa dạng và giàu tính tương trợ lẫn nhau.',
          'Mọi người dùng khi tham gia vào nền tảng Flama đều có nghĩa vụ ứng xử chuẩn mực, văn minh trong các nội dung thẻ học, phần bình luận, yêu cầu sửa đổi (change requests) và trong quá trình giao tiếp với đội ngũ hỗ trợ.',
        ],
      },
      {
        id: 'clause-comm-flashcard-security',
        clauseNumber: 'Điều 2',
        title: 'Tiêu chuẩn An toàn Kỹ thuật Nội dung Thẻ Học (Flashcard Security)',
        summary: 'Bốn tầng phòng thủ chống mã độc XSS và quy định nghiêm ngặt đối với thẻ HTML/CSS trong flashcard.',
        content: [
          'Flama cho phép định dạng thẻ học phong phú với ký tự ngữ âm hỗ trợ, văn bản đa phương thức, âm thanh và bố cục trực quan. Tuy nhiên, việc lợi dụng thẻ học để chèn mã độc hại là hành vi bị nghiêm cấm tuyệt đối.',
        ],
        subClauses: [
          {
            id: 'comm-2-1',
            clauseNumber: '2.1',
            title: 'Quy chuẩn Bảo vệ An toàn Đa tầng của Flama (Defense-in-Depth)',
            content: [
              'Để bảo vệ an toàn cho toàn thể người học, Flama thực thi cơ chế phòng vệ an ninh đa tầng theo tiêu chuẩn công nghiệp:',
              '1. Tầng máy chủ: Công nghệ lọc mã độc đa tầng phía máy chủ tự động loại bỏ triệt để mọi mã kịch bản nguy hiểm (<script>, <iframe>, <object>, <embed>, <form>, <link>) và chỉ cho phép danh mục thuộc tính an toàn.',
              '2. Tầng trình duyệt: Quy chuẩn khử độc mã HTML tự động trước khi hiển thị trên giao diện học tập của người dùng.',
              '3. Tầng cô lập thực thi: Các mặt của thẻ học được hiển thị bên trong khung nhúng cô lập an toàn, ngăn chặn hoàn toàn khả năng đọc trộm cookie phiên, mã định danh bảo mật hoặc can thiệp vào cửa sổ chính của hệ thống.',
              '4. Tầng an ninh mạng: Chính sách bảo mật nội dung nghiêm ngặt chặn đứng mọi kết nối tải dữ liệu ra máy chủ bên ngoài trái phép.',
            ],
          },
          {
            id: 'comm-2-2',
            clauseNumber: '2.2',
            title: 'Quy tắc Nghiêm cấm Mã Kịch bản & Khai thác Lỗ hổng',
            content: [
              'Người dùng tuyệt đối không được tìm cách vượt qua các rào cản làm sạch dữ liệu, không chèn các biểu thức JavaScript nguy hiểm, không sử dụng thuộc tính sự kiện ngoài danh mục âm thanh cho phép, không chèn hình ảnh theo dõi (tracking pixels) hoặc cố tình gây treo trình duyệt của người học khác.',
            ],
          },
        ],
        callout: {
          type: 'warning',
          label: 'Chế tài Đối với Hành vi Cố ý Tấn công Mã độc',
          text: 'Bất kỳ người dùng nào cố tình tạo ra hoặc phát tán các bộ thẻ chứa mã khai thác lỗ hổng bảo mật nhằm đánh cắp thông tin người học sẽ bị khóa tài khoản vĩnh viễn ngay lập tức mà không cần cảnh cáo.',
        },
      },
      {
        id: 'clause-comm-scraping',
        clauseNumber: 'Điều 3',
        title: 'Nghiêm cấm Cào Dữ liệu Tự động & Hành vi Gian lận',
        summary: 'Quy định cấm bot/crawler cào học liệu, cơ chế giới hạn tần suất API và nghiêm cấm làm sai lệch dữ liệu học.',
        content: [
          'Tài nguyên học liệu và hệ thống API của Flama được đầu tư kỹ lưỡng nhằm phục vụ trải nghiệm học tập chân thực của con người.',
        ],
        subClauses: [
          {
            id: 'comm-3-1',
            clauseNumber: '3.1',
            title: 'Tuyệt đối Cấm Trích xuất Tự động (Anti-Scraping Policy)',
            content: [
              'Người dùng không được phép triển khai các phần mềm tự động, bot, spider, crawler, công cụ trích xuất web (scraping) hoặc các kịch bản chạy ngầm để thu thập trái phép ngân hàng dữ liệu học tập, thông tin người dùng hoặc tài sản trên Marketplace của Flama.',
            ],
          },
          {
            id: 'comm-3-2',
            clauseNumber: '3.2',
            title: 'Hạn mức Truy vấn & Kiểm soát Tần suất Kết nối',
            content: [
              'Hệ thống giám sát tự động áp dụng các hạn mức truy vấn hợp lý theo ngày và theo phút nhằm bảo đảm tài nguyên phục vụ công bằng cho mọi người dùng. Mọi hành vi gửi truy vấn ồ ạt vượt ngưỡng cho phép sẽ bị hệ thống tự động hạn chế tần suất truy vấn, tạm thời ngắt kết nối và có thể bị áp dụng biện pháp ngăn chặn truy cập vĩnh viễn nếu tái diễn.',
            ],
          },
          {
            id: 'comm-3-3',
            clauseNumber: '3.3',
            title: 'Nghiêm cấm Gian lận Thành tích Học tập',
            content: [
              'Cấm sử dụng các công cụ tự động mô phỏng thao tác ôn tập nhằm gian lận các chỉ số ghi nhớ, chuỗi ngày học liên tục (streaks) hoặc thứ hạng trên các bảng vinh danh cộng đồng.',
            ],
          },
        ],
      },
      {
        id: 'clause-comm-prohibitions',
        clauseNumber: 'Điều 4',
        title: 'Nội dung Bị Cấm Tuyệt đối trên Toàn Nền tảng',
        summary: 'Danh mục các nội dung trái pháp luật, đồi trụy, thù địch, quấy rối và thương mại hóa rác.',
        content: [
          'Flama kiên quyết duy trì chính sách không khoan nhượng đối với các nội dung sau trong toàn bộ hệ thống (tiêu đề bộ thẻ, nội dung thẻ học, bình luận, tên tài khoản, phiếu hỗ trợ):',
          '1. Nội dung vi phạm pháp luật: Tuyên truyền chống phá nhà nước, kích động bạo lực, buôn bán hàng cấm, vũ khí, ma túy, hướng dẫn hành vi phạm tội.',
          '2. Nội dung đồi trụy & Khiêu dâm: Chia sẻ hình ảnh, âm thanh, văn bản khiêu dâm, đồi trụy, ấu dâm hoặc trái thuần phong mỹ tục Việt Nam.',
          '3. Ngôn từ thù ghét & Quấy rối: Nhục mạ, đe dọa, phỉ báng, bắt nạt trực tuyến, kỳ thị chủng tộc, tôn giáo, giới tính hoặc nguồn gốc xuất thân.',
          '4. Lừa đảo & Thư rác: Chèn đường dẫn lừa đảo (phishing), phát tán mã giảm giá rác, quảng cáo cờ bạc, tiền ảo hoặc các dịch vụ thương mại không liên quan đến giáo dục.',
        ],
      },
      {
        id: 'clause-comm-enforcement',
        clauseNumber: 'Điều 5',
        title: 'Cơ chế Báo cáo Vi phạm & Kênh Tiếp nhận Phiếu Hỗ trợ',
        summary: 'Quy trình gửi báo cáo vi phạm qua mã vé TK-YYYYMMDD-XXXXXX và thang đo chế tài xử phạt.',
        content: [
          'Để duy trì chuẩn mực cộng đồng, mọi thành viên đều có quyền và trách nhiệm báo cáo các hành vi hoặc nội dung sai phạm mà mình phát hiện:',
        ],
        subClauses: [
          {
            id: 'comm-5-1',
            clauseNumber: '5.1',
            title: 'Quy trình Gửi Báo cáo Vi phạm qua Phiếu Hỗ trợ',
            content: [
              'Người học có thể tạo phiếu báo cáo sai phạm trực tiếp trong ứng dụng tại trang Hỗ trợ (/support) hoặc qua cổng tiếp nhận yêu cầu trực tuyến. Mỗi báo cáo được hệ thống cấp một mã theo dõi duy nhất có định dạng chuẩn: `TK-YYYYMMDD-XXXXXX`.',
              'Đội ngũ kiểm duyệt Flama cam kết xem xét và xử lý các báo cáo trong vòng 48 giờ làm việc kể từ thời điểm tiếp nhận.',
            ],
          },
          {
            id: 'comm-5-2',
            clauseNumber: '5.2',
            title: 'Thang đo Chế tài Kỷ luật',
            content: [
              'Tùy theo mức độ nghiêm trọng và tần suất vi phạm, Flama sẽ áp dụng các biện pháp chế tài sau:',
              'Mức 1 (Nhắc nhở): Nhắc nhở qua email và yêu cầu chỉnh sửa hoặc tự gỡ bỏ nội dung chưa phù hợp.',
              'Mức 2 (Đình chỉ có thời hạn): Khóa quyền đăng tải bộ thẻ mới, tước quyền bình luận hoặc tạm khóa tài khoản từ 07 đến 30 ngày.',
              'Mức 3 (Chấm dứt vĩnh viễn): Xóa bỏ vĩnh viễn tài khoản, cấm địa chỉ IP máy tính và chuyển giao thông tin cho cơ quan pháp luật có thẩm quyền đối với các hành vi vi phạm pháp luật nghiêm trọng.',
            ],
          },
        ],
      },
    ],
  },

  cookies: {
    id: 'cookies',
    title: 'Chính sách Cookie & Lưu trữ Cục bộ',
    officialBadge: 'Minh bạch Kỹ thuật Lưu trữ',
    lastUpdated: '13/09/2026',
    effectiveDate: '15/09/2026',
    version: 'v2.0',
    readTimeMinutes: 8,
    executiveSummary:
      'Chính sách này giải thích cách thức Flama sử dụng cookie phiên làm việc bắt buộc và bộ nhớ cục bộ (LocalStorage) trên thiết bị của bạn. Flama tôn trọng quyền riêng tư và cam kết tuyệt đối không sử dụng cookie theo dõi quảng cáo của bên thứ ba.',
    clauses: [
      {
        id: 'clause-cookie-definition',
        clauseNumber: 'Điều 1',
        title: 'Khái niệm Cookie & Công nghệ Lưu trữ Cục bộ',
        summary: 'Định nghĩa tệp tin cookie và bộ nhớ trình duyệt Web Storage.',
        content: [
          'Cookie là các tệp văn bản nhỏ được trang web gửi đến và lưu trữ trên trình duyệt thiết bị của bạn khi bạn truy cập dịch vụ. Công nghệ lưu trữ cục bộ (LocalStorage và SessionStorage) cho phép trang web ghi nhớ các tùy chọn cá nhân của bạn trực tiếp trên trình duyệt mà không cần gửi dữ liệu liên tục về máy chủ trong mọi truy vấn.',
        ],
      },
      {
        id: 'clause-cookie-essential',
        clauseNumber: 'Điều 2',
        title: 'Danh mục Cookie Thiết yếu Bắt buộc (Essential Cookies)',
        summary: 'Các cookie cần thiết tuyệt đối để duy trì đăng nhập an toàn và bảo vệ chống tấn công CSRF.',
        content: [
          'Flama chỉ sử dụng các cookie thiết yếu phục vụ trực tiếp cho hoạt động bảo mật và vận hành cốt lõi của nền tảng:',
          '1. Cookie Phiên đăng nhập (session cookie): Vận hành theo cơ chế xác thực an toàn, cho phép hệ thống nhận diện bạn là người dùng đã xác thực khi di chuyển giữa các trang học tập. Cookie này được gắn các thuộc tính bảo mật nghiêm ngặt theo tiêu chuẩn công nghiệp: `HttpOnly` (ngăn chặn mã độc đánh cắp), `SameSite=Lax` (ngăn ngừa tấn công giả mạo yêu cầu) và `Secure` (chỉ truyền qua kênh mã hóa HTTPS bảo mật).',
          '2. Cookie Bảo vệ CSRF: Chứa mã xác thực ngẫu nhiên nhằm bảo vệ tài khoản của bạn trước các cuộc tấn công Cross-Site Request Forgery khi bạn thực hiện các thao tác quản lý thẻ hoặc thanh toán.',
        ],
        callout: {
          type: 'info',
          label: 'Cam kết Không Dùng Cookie Quảng cáo',
          text: 'Flama TUYỆT ĐỐI KHÔNG sử dụng cookie theo dõi hành vi của bên thứ ba (Third-party advertising cookies) và không chia sẻ dữ liệu duyệt web của bạn cho các mạng lưới quảng cáo thương mại.',
        },
      },
      {
        id: 'clause-cookie-storage',
        clauseNumber: 'Điều 3',
        title: 'Ứng dụng của Bộ nhớ Cục bộ (LocalStorage / SessionStorage)',
        summary: 'Lưu trữ tùy chọn giao diện sáng/tối, cấu hình hiển thị bảng học liệu và mã ghép nối Flama Audio.',
        content: [
          'Chúng tôi sử dụng bộ nhớ cục bộ trên trình duyệt để nâng cao trải nghiệm học tập mượt mà của bạn:',
          '1. Tùy chọn Giao diện: Ghi nhớ chế độ hiển thị Sáng (Light) / Tối (Dark) và độ rộng các cột hiển thị trong bảng tra cứu học liệu cá nhân.',
          '2. Tùy chọn Học tập: Lưu trữ cấu hình âm lượng âm thanh, tốc độ phát âm mặc định và giọng đọc ưu tiên mà bạn đã lựa chọn.',
          '3. Ghép nối Ứng dụng Flama Audio: Lưu trữ mã chứng thực ghép nối an toàn phục vụ việc kết nối giữa trình duyệt web và ứng dụng máy tính Flama Audio trên thiết bị.',
        ],
      },
      {
        id: 'clause-cookie-management',
        clauseNumber: 'Điều 4',
        title: 'Quyền Quản lý & Vô hiệu hóa Cookie của Người học',
        summary: 'Hướng dẫn cách quản lý và cảnh báo hệ quả khi tắt cookie phiên.',
        content: [
          'Bạn hoàn toàn có quyền kiểm soát, từ chối hoặc xóa bỏ các cookie đã lưu thông qua phần cài đặt bảo mật của trình duyệt web (Google Chrome, Microsoft Edge, Mozilla Firefox, Apple Safari).',
          'Tuy nhiên, xin lưu ý rằng vì cookie của Flama là cookie thiết yếu phục vụ đăng nhập, nếu bạn chặn toàn bộ cookie, hệ thống sẽ không thể duy trì trạng thái đăng nhập và bạn sẽ không thể truy cập vào các tính năng học tập cá nhân hóa.',
        ],
      },
    ],
  },
}

export { legalDocumentsEn }

/**
 * Helper array of all legal documents for navigation and indexing.
 */
export const legalDocumentsList: LegalDocument[] = Object.values(legalDocuments)

/**
 * Retrieve a specific legal document by ID with fallback and locale support.
 */
export function getLegalDocument(
  documentId: string,
  locale: 'vi' | 'en' = 'vi',
): LegalDocument | undefined {
  const docs = locale === 'en' ? legalDocumentsEn : legalDocuments
  return docs[documentId]
}

