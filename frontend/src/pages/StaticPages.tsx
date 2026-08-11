import { Info } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Page, PageHeader } from '@/shared/components/Page'

export { SupportPage } from '@/features/support/pages/SupportPage'
export { TtsKeyGuidePage } from '@/features/support/pages/TtsKeyGuidePage'
export { FlamaAudioGuidePage } from '@/features/support/pages/FlamaAudioGuidePage'


type LegalSection = {
  title: string
  paragraphs?: string[]
  items?: string[]
}

function LegalPage({
  title,
  summary,
  sections,
}: {
  title: string
  summary: string
  sections: LegalSection[]
}) {
  return (
    <Page className="max-w-4xl">
      <PageHeader title={title} description="Cập nhật lần cuối: 26/07/2026" />
      <Alert>
        <Info />
        <AlertTitle>Tóm tắt</AlertTitle>
        <AlertDescription>{summary}</AlertDescription>
      </Alert>
      {sections.map((section) => (
        <Card key={section.title}>
          <CardHeader>
            <CardTitle>{section.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 leading-7 text-muted-foreground">
            {section.paragraphs?.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            {section.items?.length ? (
              <ul className="list-disc space-y-2 pl-5">
                {section.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </Page>
  )
}

export function TermsPage() {
  return (
    <LegalPage
      title="Điều khoản sử dụng"
      summary="Các nguyên tắc sử dụng tài khoản, học liệu và marketplace Flama."
      sections={[
        {
          title: '1. Sự đồng ý và phạm vi dịch vụ',
          paragraphs: ['Khi sử dụng Flama, bạn đồng ý tuân thủ các điều khoản này. Flama cung cấp flashcard, quản lý từ vựng và lịch học lặp lại ngắt quãng.'],
        },
        {
          title: '2. Quyền sở hữu nội dung',
          paragraphs: ['Bạn sở hữu học liệu do mình tạo. Bạn cho phép Flama lưu trữ, xử lý, hiển thị, sao lưu và khôi phục nội dung đó để vận hành dịch vụ.'],
          items: ['Không sao chép hoặc phân phối trái phép tài sản, thương hiệu và mã nguồn Flama.', 'Không đăng nội dung vi phạm bản quyền hoặc quyền riêng tư của người khác.'],
        },
        {
          title: '3. Hành vi bị cấm',
          items: ['Tấn công, phá hoại, khai thác lỗ hổng hoặc đưa mã độc vào hệ thống.', 'Dùng bot, crawler hoặc tải dữ liệu hàng loạt trái phép.', 'Gian lận, giả mạo, spam, quấy rối hoặc sử dụng dịch vụ cho mục đích bất hợp pháp.'],
        },
        {
          title: '4. Tài khoản và chấm dứt dịch vụ',
          paragraphs: ['Bạn chịu trách nhiệm bảo vệ mật khẩu và hoạt động trên tài khoản. Flama có thể đình chỉ tài khoản vi phạm; bạn có thể yêu cầu xóa tài khoản và dữ liệu theo chính sách hiện hành.'],
        },
        {
          title: '5. Giới hạn trách nhiệm và thay đổi',
          paragraphs: ['Flama không chịu trách nhiệm cho thiệt hại gián tiếp, lỗi thiết bị hoặc nội dung của người dùng khác. Điều khoản có thể được cập nhật và ngày cập nhật sẽ được công bố trên trang này.'],
        },
      ]}
    />
  )
}

export function PrivacyPage() {
  return (
    <LegalPage
      title="Chính sách bảo mật"
      summary="Cách Flama thu thập, sử dụng và bảo vệ dữ liệu của người học."
      sections={[
        {
          title: '1. Dữ liệu được thu thập',
          items: ['Thông tin tài khoản như email, tên đăng nhập và mật khẩu đã băm.', 'Học liệu, tiến độ, lịch sử ôn tập và lựa chọn cấu hình.', 'Thông tin kỹ thuật cần thiết cho bảo mật và vận hành dịch vụ.'],
        },
        {
          title: '2. Mục đích sử dụng',
          items: ['Cung cấp, đồng bộ và cải thiện trải nghiệm học tập.', 'Bảo vệ tài khoản, phát hiện lạm dụng và hỗ trợ người dùng.', 'Đáp ứng nghĩa vụ pháp lý hợp lệ.'],
        },
        {
          title: '3. Chia sẻ và bảo vệ dữ liệu',
          paragraphs: ['Flama không bán dữ liệu người dùng. Dữ liệu chỉ được chia sẻ khi có sự đồng ý, yêu cầu pháp lý hợp lệ hoặc với nhà cung cấp cần thiết để vận hành dịch vụ theo nghĩa vụ bảo mật.'],
        },
        {
          title: '4. Quyền và thời gian lưu giữ',
          paragraphs: ['Bạn có thể yêu cầu truy cập, sửa, xuất hoặc xóa dữ liệu. Dữ liệu được giữ khi tài khoản hoạt động và có thể được giữ tạm thời trong bản sao lưu hoặc log bảo mật trước khi xóa theo chu kỳ vận hành.'],
        },
      ]}
    />
  )
}

export function CookiesPage() {
  return (
    <LegalPage
      title="Chính sách cookie"
      summary="Cookie phiên đăng nhập, CSRF và các lựa chọn cần thiết để ứng dụng hoạt động."
      sections={[
        {
          title: '1. Cookie thiết yếu',
          paragraphs: ['Flama dùng cookie phiên để duy trì đăng nhập và token CSRF để bảo vệ các thao tác thay đổi dữ liệu. Các cookie này cần thiết để ứng dụng hoạt động an toàn.'],
        },
        {
          title: '2. Lưu trữ cục bộ',
          paragraphs: ['Ứng dụng có thể lưu tùy chọn giao diện và trạng thái tạm thời trên trình duyệt. Không lưu mật khẩu hoặc khóa thanh toán trong local storage.'],
        },
        {
          title: '3. Kiểm soát của bạn',
          paragraphs: ['Bạn có thể xóa hoặc chặn cookie trong trình duyệt, nhưng đăng nhập và một số tính năng bảo mật có thể không hoạt động.'],
        },
      ]}
    />
  )
}
