# Task: Payment reconciliation, báo cáo giao dịch chưa được ghi nhận và quản trị trạng thái thanh toán

## Mục tiêu

Bổ sung cơ chế xử lý các trường hợp **người dùng đã thanh toán nhưng Flama chưa ghi nhận đúng trạng thái giao dịch**.

Người dùng cần có khả năng báo cáo trực tiếp từ các màn liên quan đến thanh toán. Quản trị viên cần có công cụ để tiếp nhận báo cáo, xác minh với dữ liệu thanh toán thực tế và cập nhật lại trạng thái giao dịch một cách an toàn, có lịch sử và có thể audit.

Mục tiêu không chỉ là thêm một nút `Báo cáo`, mà phải xây dựng một flow reconciliation hoàn chỉnh giữa:

- trạng thái hiển thị trên Flama
- trạng thái từ payment provider / ngân hàng / webhook
- bằng chứng người dùng cung cấp
- thao tác xác minh và điều chỉnh của admin

## Phạm vi

### 1. Nút báo cáo trên các màn thanh toán

Tại các màn có liên quan đến giao dịch/thanh toán, nếu giao dịch đang ở trạng thái như:

- pending quá lâu
- failed nhưng người dùng cho rằng đã thanh toán thành công
- chưa ghi nhận
- không nhận được quyền lợi sau thanh toán
- trạng thái trên Flama khác với trạng thái người dùng thấy từ ngân hàng/payment provider

cần có nút phù hợp, ví dụ:

- `Đã thanh toán nhưng chưa được ghi nhận`
- `Báo cáo vấn đề thanh toán`

Không nên hiển thị nút report một cách gây nhiễu cho mọi giao dịch đã hoàn tất bình thường. Cần nghiên cứu vị trí và điều kiện hiển thị phù hợp.

Các màn cần rà soát tối thiểu:

- checkout / payment result
- payment pending
- payment failed
- wallet / transaction history
- purchase history
- marketplace order / Deck purchase nếu có
- course/class payment nếu sau này dùng chung payment system

### 2. Form báo cáo của người dùng

Khi người dùng báo cáo, hệ thống phải tự đính kèm các dữ liệu giao dịch đã có thay vì bắt người dùng nhập lại toàn bộ.

Tối thiểu cần lưu:

- user ID
- transaction/order/payment ID của Flama
- payment provider nếu có
- provider transaction/reference ID nếu đã biết
- số tiền
- currency
- trạng thái hiện tại trên Flama
- thời điểm tạo giao dịch
- thời điểm report
- nội dung người dùng mô tả

Có thể cho phép người dùng bổ sung:

- mã giao dịch ngân hàng / payment reference
- thời gian thanh toán thực tế
- ảnh chụp biên lai / bằng chứng thanh toán
- ghi chú

Nếu cho upload ảnh bằng chứng, phải sử dụng pipeline xử lý ảnh/file an toàn của hệ thống, không tạo một luồng upload riêng bỏ qua validation/security.

### 3. Chống report trùng lặp và spam

Không tạo nhiều report độc lập cho cùng một giao dịch nếu report trước đó vẫn đang mở.

Cần nghiên cứu cơ chế:

- một payment issue active trên mỗi transaction
- nếu người dùng report lại thì đưa họ về issue hiện tại hoặc bổ sung thông tin
- rate limit
- chống spam
- ghi nhận số lần user bổ sung thông tin

### 4. Trạng thái của Payment Issue

Nên có state riêng cho ticket/reconciliation issue, tách khỏi transaction state.

Ví dụ:

- `OPEN`
- `INVESTIGATING`
- `WAITING_FOR_USER`
- `RESOLVED`
- `REJECTED`

Không bắt buộc dùng đúng enum trên nếu hệ thống đã có ticket/report model phù hợp.

Payment Issue và Payment Transaction là hai khái niệm khác nhau:

- Payment Issue = yêu cầu xác minh
- Payment Transaction = trạng thái tài chính thực tế

Không dùng status của report để thay trực tiếp status của transaction.

### 5. Admin: danh sách báo cáo thanh toán

Bổ sung khu vực trong Admin để quản trị viên xem các vấn đề thanh toán.

Cần hỗ trợ tối thiểu:

- danh sách report
- lọc theo trạng thái issue
- lọc theo payment status
- tìm theo user
- tìm theo transaction/order ID
- tìm theo provider reference
- lọc theo payment provider
- lọc theo thời gian
- ưu tiên các giao dịch pending bất thường lâu

Danh sách cần hiển thị đủ thông tin để admin biết report nào cần xử lý trước nhưng không nhồi toàn bộ chi tiết vào table.

### 6. Admin: màn chi tiết xác minh giao dịch

Khi mở một report, admin cần xem được đầy đủ dữ liệu liên quan:

#### Dữ liệu Flama

- user
- order / transaction
- sản phẩm/Deck/course liên quan
- số tiền
- currency
- payment method/provider
- trạng thái hiện tại
- thời gian tạo/cập nhật
- webhook/event đã nhận nếu có

#### Dữ liệu từ provider

Nếu provider có API hỗ trợ lookup, cần nghiên cứu chức năng `Verify / Refresh from provider` để truy vấn trạng thái mới nhất theo transaction/reference ID.

Không bắt admin phải tự nhìn ảnh biên lai nếu hệ thống có thể xác minh trực tiếp với nguồn thanh toán.

#### Dữ liệu report

- mô tả người dùng
- bằng chứng đính kèm
- thời điểm report
- lịch sử bổ sung thông tin

#### Lịch sử transaction

Hiển thị timeline hoặc event history, ví dụ:

- payment created
- redirected to provider
- callback received
- webhook received
- webhook validation failed
- status changed
- entitlement granted
- admin manually reconciled

### 7. Admin: cập nhật trạng thái giao dịch

Admin cần có chức năng cập nhật trạng thái transaction khi đã xác minh được payment provider đã nhận tiền nhưng Flama chưa cập nhật đúng.

Tuy nhiên **không cho phép admin thay đổi status tùy ý như sửa một field bình thường**.

Cần xây dựng action theo nghiệp vụ, ví dụ:

- `Xác nhận đã thanh toán`
- `Đánh dấu thanh toán thất bại`
- `Hủy giao dịch`
- `Hoàn tiền` nếu hệ thống có refund flow
- `Đồng bộ lại từ provider`

Mỗi action phải kiểm tra state transition hợp lệ.

Ví dụ không cho phép:

- từ refunded quay thẳng sang paid mà không có nghiệp vụ rõ ràng
- mark paid một giao dịch sai số tiền
- mark paid khi provider reference thuộc transaction khác

### 8. Khi admin xác nhận thanh toán thành công

Việc đổi transaction sang `PAID/SUCCESS` phải đi qua cùng business service với payment callback/webhook bình thường.

Không chỉ update một cột trong database.

Sau khi xác nhận cần đảm bảo toàn bộ side effects tương ứng được thực thi idempotent, ví dụ:

- cập nhật order
- cấp quyền sử dụng Deck/course/product
- cập nhật wallet/accounting record nếu có
- tạo purchase record
- cập nhật marketplace metrics nếu có
- gửi notification/email thành công
- đóng payment issue liên quan

Nếu một side effect đã chạy trước đó thì không được chạy trùng lần hai.

### 9. Reconciliation với payment provider

Cần nghiên cứu payment provider hiện tại và xác định khả năng:

- query trạng thái transaction bằng API
- lookup theo provider transaction ID
- lookup theo order/reference
- verify amount/currency
- verify recipient/merchant account
- verify payment timestamp
- nhận lại webhook/event

Ưu tiên nguồn dữ liệu từ payment provider hơn ảnh chụp do người dùng cung cấp.

Ảnh biên lai chỉ là bằng chứng hỗ trợ, không mặc định đủ để admin mark payment thành công.

### 10. Webhook recovery

Cần điều tra nguyên nhân Flama có thể không ghi nhận payment dù provider đã thành công, ví dụ:

- webhook không tới
- webhook timeout
- signature validation lỗi
- event đến sai thứ tự
- transaction đang lock
- database error
- worker failure
- retry không hoạt động
- callback frontend bị đóng sớm

Nếu provider hỗ trợ retry webhook hoặc fetch event history, cần thiết kế khả năng recover tự động.

Mục tiêu dài hạn là giảm số lượng trường hợp cần admin xử lý thủ công.

### 11. Automatic reconciliation job

Nghiên cứu thêm background job định kỳ để tự kiểm tra các transaction bị pending quá lâu.

Ví dụ:

1. tìm transaction `PENDING` quá ngưỡng
2. query provider
3. nếu provider xác nhận paid
4. chạy payment success service idempotent
5. cập nhật transaction
6. cấp entitlement
7. ghi audit log

Nếu có thể tự reconcile an toàn thì không cần chờ người dùng report.

Ngưỡng thời gian và provider nào hỗ trợ phải được cấu hình, không hardcode theo giả định.

### 12. Audit log bắt buộc

Mọi thao tác admin làm thay đổi transaction/payment state phải được ghi audit log.

Tối thiểu lưu:

- admin ID
- transaction ID
- issue/report ID nếu có
- old status
- new status
- action
- reason
- provider verification result
- thời gian
- request/correlation ID nếu có

Nếu admin override khác với trạng thái provider thì phải yêu cầu reason rõ ràng và đánh dấu đây là manual override.

Không cho phép xóa audit history từ UI admin thông thường.

### 13. Phân quyền admin

Không mặc định mọi tài khoản có quyền vào Admin đều được sửa trạng thái thanh toán.

Cần nghiên cứu permission riêng, ví dụ:

- `payment.view`
- `payment.reconcile`
- `payment.manual_update`
- `payment.refund`

Các action tài chính nhạy cảm cần giới hạn theo role.

Nếu hệ thống RBAC hiện tại chưa chi tiết như trên thì xác định phương án phù hợp với kiến trúc hiện tại.

### 14. Notification cho người dùng

Khi report thay đổi trạng thái cần thông báo cho người dùng.

Các trường hợp tối thiểu:

- report đã được tiếp nhận
- admin cần thêm thông tin
- giao dịch đã được xác minh thành công
- quyền lợi đã được cấp lại
- report bị từ chối và lý do

Không gửi notification trùng khi cùng event bị retry.

### 15. UX sau khi transaction được sửa

Khi admin hoặc automatic reconciliation đã xác nhận giao dịch:

- transaction history phải hiển thị trạng thái mới
- màn purchase/payment phải refresh đúng
- sản phẩm đã mua phải sử dụng được
- nút report không còn hiển thị như một issue chưa xử lý
- người dùng thấy được report đã resolved

Nếu frontend đang cache transaction/order thì phải có chiến lược invalidation/refetch phù hợp.

## Data model investigation

Trước khi triển khai cần kiểm tra các model hiện tại liên quan đến:

- Payment
- Transaction
- Order
- Wallet
- Purchase
- Marketplace purchase
- payment webhook/event
- notification
- admin audit log
- existing report/ticket system

Sau đó quyết định nên:

- mở rộng report system hiện có
- hay tạo `PaymentIssue` / `PaymentReconciliationCase` riêng

Không tạo model mới nếu một report/moderation framework hiện tại có thể mở rộng sạch sẽ.

## API investigation

Rà soát API hiện tại và đề xuất API cần thiết, ví dụ:

### User

- create payment issue
- get own payment issue
- add evidence/comment

### Admin

- list payment issues
- get payment issue detail
- verify/refresh provider status
- resolve/reject issue
- reconcile transaction
- view audit history

Tên endpoint cụ thể phải theo convention hiện tại của Flama.

## Security requirements

- User chỉ được report transaction thuộc tài khoản của mình, trừ trường hợp nghiệp vụ rõ ràng cho phép khác.
- Không tin transaction ID/provider reference do client gửi mà không verify ownership.
- Không expose secret/provider credential cho frontend.
- Evidence upload phải qua validation/security pipeline.
- Admin action phải có authorization phía backend.
- Manual status update phải được audit.
- Các action phải idempotent.
- Không cấp entitlement chỉ dựa trên trạng thái frontend callback.
- Verify amount, currency và transaction identity trước khi mark paid.

## Observability

Bổ sung hoặc rà soát metrics/logging cho:

- số payment pending quá ngưỡng
- webhook failures
- reconciliation success/failure
- số user report
- số manual override của admin
- thời gian trung bình xử lý payment issue
- transaction provider=paid nhưng Flama!=paid

Các lỗi reconciliation quan trọng cần có khả năng đưa vào hệ thống cảnh báo admin/ops nếu kiến trúc hiện tại hỗ trợ.

## Deliverables

- Nút báo cáo vấn đề tại các màn thanh toán phù hợp.
- Flow tạo Payment Issue từ transaction hiện có.
- Trang/list Payment Issues cho admin.
- Trang chi tiết để admin xác minh transaction.
- Provider status refresh/verification nếu provider hỗ trợ.
- Admin action cập nhật trạng thái giao dịch theo state machine.
- Payment success reconciliation chạy qua business service chung, không update DB trực tiếp.
- Audit log cho mọi manual transaction status change.
- Notification cho user khi issue được xử lý.
- Research automatic reconciliation cho transaction pending bất thường.
- Tests cho user flow, admin flow, authorization, idempotency và payment state transitions.

## Acceptance criteria

- Người dùng có thể báo cáo trường hợp đã thanh toán nhưng Flama chưa ghi nhận từ transaction/payment liên quan.
- Report tự liên kết với transaction và user tương ứng.
- Không tạo nhiều active report trùng cho cùng một transaction.
- Admin có thể xem đầy đủ transaction, report, evidence và lịch sử xử lý.
- Admin có thể xác minh trạng thái với payment provider nếu integration hỗ trợ.
- Admin có thể cập nhật transaction theo các transition được phép sau khi xác minh.
- Mọi thay đổi trạng thái do admin thực hiện đều có audit log.
- Khi transaction được xác nhận paid, các entitlement/order/purchase liên quan được đồng bộ đầy đủ và idempotent.
- Người dùng được thông báo kết quả xử lý.
- Không có trường hợp chỉ sửa `payment.status` trong DB nhưng bỏ sót quyền lợi hoặc các side effect liên quan.
- Các transaction pending bất thường có hướng xử lý/reconciliation rõ ràng thay vì phụ thuộc hoàn toàn vào report thủ công.