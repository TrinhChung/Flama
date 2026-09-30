# Đánh giá UI/UX các phase đã hoàn tất — Template, chế độ học và clone

> **Kế hoạch triển khai (2026-09-30):** các phát hiện dưới đây đã được chuyển thành [sổ nợ kỹ thuật TD-01..TD-22](../tech-debt/README.md). Track "Template Modularization" ở §5b được thay bằng TD-14..TD-19. Các khoản này dùng chung một vòng đời chia sẻ cho Deck/NoteType/Template, và nâng cấp chính bộ máy deck thay vì coi nó là chuẩn.

> Lập 2026-09-30. Loại: điều tra/báo cáo, **Runtime change: none**.
>
> **Chỉ đạo ưu tiên của chủ sản phẩm (2026-09-30):** UI cho Phase 8 xếp cuối. Trước hết cần UI cho các phase đã xong (tách Template/NoteType, chọn chế độ học, clone overlay), đo theo góc nhìn người dùng. Báo cáo này thay phần thứ tự ưu tiên ở §5 của [báo cáo UI/UX trước P8](./UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md); các phát hiện của báo cáo đó vẫn giữ nguyên giá trị.
>
> Phương pháp: đi lại 5 hành trình người dùng trên code React và backend tại nhánh `fix/legacy-lease-replay-under-note`. Chưa chạy trình duyệt, chưa đọc dữ liệu production. Mục cần xác nhận trên trình duyệt hoặc dữ liệu thật có ghi *(cần xác minh)*.

## 1. Trả lời nhanh bốn câu hỏi

| Câu hỏi | Trả lời | Mức | Chi tiết |
|---|---|---|---|
| 1. Người dùng đã dễ sử dụng chưa? | **Chưa.** Người quen HTML/Anki dùng được, người học phổ thông thì khó: không đổi tên/xóa Template được, thao tác tạo mới sinh thẻ ngay mà không hỏi, mất bản chỉnh sửa chưa lưu, không có lời giải thích về hệ quả | P1 | §2.1, §2.2 |
| 2. Đã chọn được chế độ học chưa? | **Có ở mức kỹ thuật, chưa ở mức sản phẩm.** Khi NoteType có từ 2 Template, trước phiên sẽ hiện bộ chọn. Tuy vậy, mỗi "chế độ" chỉ là một Template lật thẻ + 4 nút, tên hiển thị kiểu "Card 2", không nhớ lựa chọn, không giải thích tiến độ dùng chung. Deck đã cài có Note tự thêm còn bị tách thành 2 lựa chọn | P1 | §2.2 |
| 3. Đã tạo được nhiều Template chưa? | **Tạo được, nhưng không quản lý được trong UI.** Nút "Mới" tạo Template nội dung cứng `{{Word}}`/`{{Word}}` và sinh Card cho mọi Note ngay lập tức. API đã có đổi tên và xóa, nhưng UI không có nút | P1 | §2.1 |
| 4a. Clone **NoteType** từ chợ có tự sửa Template mà không ảnh hưởng người khác không? | **Có.** Người cài nhận một bản sao đầy đủ thuộc sở hữu riêng. Cần sửa nhãn và nút "Reset" (có thể xóa thiết kế đã mua) | P2 | §2.3 |
| 4b. Clone **deck** từ chợ có tự sửa Template mà không ảnh hưởng người khác không? | **Chưa.** Người cài cũng nhận bản sao NoteType, nhưng thẻ gốc của deck luôn render bằng Template của tác giả; sửa bản sao chỉ đổi các Note tự thêm, và UI không nói điều này. Chiều ngược lại: tác giả sửa nội dung Template thì mọi người cài bị đổi ngay, không có release hay thông báo | **P0 về sản phẩm** (lệch mục tiêu decoupling) | §2.4, §2.5 |

## 2. Hành trình chi tiết

### 2.1 Tạo và quản lý nhiều Template (hành trình J1)

Người dùng vào **Loại thẻ** (`/flashcards/note-types`), chọn một NoteType và mở **Trình soạn thảo Template** (`note-types/pages/NoteTypeDetailPage.tsx`).

| ID | Phát hiện | Bằng chứng | Tác động | Đề xuất |
|---|---|---|---|---|
| T1 | "Mới" tạo Template tên `Card N`, mặt trước và sau đều cứng `{{Word}}`, không hỏi tên, không sao chép Template đang xem | `NoteTypeDetailPage.tsx:129-144` (payload dòng 131-135) | NoteType không có trường `Word` sẽ nhận Template rỗng; tên "Card 2" hiện thẳng trong bộ chọn chế độ học | Dialog "Tạo chế độ/Template": tên bắt buộc; nguồn = sao chép Template đang chọn (mặc định) hoặc mẫu trống; xem trước |
| T2 | Tạo Template sinh Card ngay cho **mọi** Note của NoteType, không xác nhận | `flashcards_share_service.py:283-285`; `flashcard_content_service.py:790-866` | Deck đổi từ 1 thành 2 lựa chọn; từ đó mỗi lần bấm Học đều phải chọn (UX-B2 báo cáo trước) | Xác nhận kèm số Note sẽ nhận Card (`note_count` đã có trong API) và câu giải thích "một chế độ học mới, tiến độ dùng chung" |
| T3 | Không đổi tên Template trong UI, dù `PATCH` đã nhận `name` | UI chỉ có select + Mới + Reset + Lưu (`NoteTypeDetailPage.tsx:298-330, 430`); backend `flashcard_content_service.py:883-884` | Không sửa được tên "Card 2" | Đổi tên ngay trong danh sách Template |
| T4 | Không xóa Template trong UI, dù `DELETE` đã có và giữ tiến độ theo Note | `app/api/v1/flashcards/note_types.py:193-204`; `flashcard_content_service.py:934+` | Template tạo nhầm (T1) không gỡ được | Nút xóa kèm dialog: số Card bị gỡ, khẳng định tiến độ Note được giữ; chặn xóa Template mặc định/cuối cùng như backend |
| T5 | Mất chỉnh sửa chưa lưu khi đổi Template hoặc rời trang | Effect đồng bộ editor theo Template được chọn ghi đè state (`NoteTypeDetailPage.tsx:95-106`); không có `useBlocker`/`beforeunload` | Mất công sức soạn HTML | Trạng thái "chưa lưu", hỏi trước khi đổi hoặc rời |
| T6 | "Reset" dùng `window.confirm`; khôi phục về **mẫu hệ thống legacy**, không phải bản gốc của Template | `NoteTypeDetailPage.tsx:320-330`; `flashcard_content_service.py:915-932` | Với NoteType mua từ chợ, "Reset" xóa thiết kế đã mua mà không có hoàn tác | Đổi nhãn thành "Thay bằng mẫu mặc định của Flama"; dialog của design system; lưu bản trước để hoàn tác |
| T7 | Không có sắp xếp thứ tự, đặt mặc định, hay nhân bản Template/NoteType | Không có API hoặc UI tương ứng | Muốn thử một biến thể thì phải sửa thẳng Template đang dùng | Nhân bản Template (khả thi ngay, tái dùng `POST` với nội dung sao chép); nhân bản NoteType cần endpoint riêng |
| T8 | Lỗi backend hiện nguyên tiếng Anh trong toast | `toast.error(..., { description: error.message })` (`NoteTypeDetailPage.tsx:141-143`); thông điệp `SHARED_SCHEMA_VERSIONING_REQUIRED` (`flashcard_content_service.py:1547-1554`) | "Templates used by a released shared deck cannot be changed yet…" | Ánh xạ mã lỗi sang tiếng Việt kèm hướng xử lý |

### 2.2 Chọn chế độ học (hành trình J2)

Người dùng bấm **Học** trên Dashboard. Nếu phạm vi có từ 2 composition, màn "Chọn kiểu thẻ" hiện ra.

| ID | Phát hiện | Bằng chứng | Đề xuất |
|---|---|---|---|
| S1 | "Chế độ" = Template. Mọi composition đều là `flashcard` / `review.four-rating` / `legacy-anki` | `study_composition_service.py:25-27` | Đúng phạm vi đã xong (chế độ tương tác mới thuộc P8); UI nên gọi là "Cách học" hoặc "Mẫu thẻ", tránh hứa trắc nghiệm hay gõ đáp án |
| S2 | Lựa chọn chỉ hiện tên Template và loại nguồn; không mô tả, không xem trước, không số lượng | `StudyModeSelector.tsx:50-57` | Thêm ảnh xem trước mặt trước (tái dùng preview), số Note đến hạn |
| S3 | Không giải thích **tiến độ dùng chung theo Note**: học ở "Card 2" thì Note đó cũng xong ở "Card 1" | Không có câu chữ nào trong `StudyPage.tsx:347-384` | Một dòng giải thích ở bộ chọn và ở dialog tạo Template (T2) |
| S4 | Không nhớ lựa chọn; mỗi lần vào deck đều phải chọn lại | `useStudySession.ts:384-387` | Làm nổi bật "Dùng lần trước" ở client (vẫn bấm 1 lần, đúng chính sách P3-05) |
| S5 | Deck đã cài có Note tự thêm bị tách thành **2 lựa chọn**, "Thẻ gốc từ bộ đã cài" và "Thẻ riêng trong bộ đã cài", thường trùng tên Template; mỗi phiên chỉ học một nhóm *(cần xác minh bằng dữ liệu thật)* | composition ID khác nhau theo `source`/`local` (`study_composition_service.py:101-115, 169-181`); nhãn `StudyModeSelector.tsx:52-56` | Cần quyết định D-T3; tối thiểu: tiêu đề nhóm rõ ràng, giải thích vì sao tách |
| S6 | Màn hoàn thành nói "Tất cả các thẻ cần học hôm nay đã được ôn tập xong" dù lựa chọn khác còn thẻ | UX-B3 báo cáo trước | Nói rõ "Xong phần <Template>", kèm CTA học lựa chọn còn lại |

### 2.3 Cài NoteType từ chợ rồi tự sửa (hành trình J3)

Luồng: Chợ → NoteType → Cài. Backend tạo **bản sao đầy đủ** (NoteType, FieldDef, Template) thuộc người cài, `publish_status="private"` (`app/services/share/note_types.py:451-480, 499-548`). Mọi sửa đổi trên bản sao chỉ ảnh hưởng người đó. ✅

| ID | Phát hiện | Bằng chứng | Đề xuất |
|---|---|---|---|
| N1 | Danh sách Loại thẻ không đánh dấu bản sao từ chợ, dù API trả `is_marketplace_install` | `flashcard_content_service.py:106-113`; frontend chỉ dùng cờ này ở trang publish (`PublishNoteTypeSelector.tsx:27`) | Nhãn "Cài từ chợ — bản riêng của bạn" ở danh sách và trang chi tiết |
| N2 | Nút "Chia sẻ lên Kho" vẫn hiện cho bản sao, dù backend chặn chia sẻ lại | `NoteTypeDetailPage.tsx:265`, `NoteTypeManagerPage.tsx:375`; chặn ở `share/note_types.py:287-292` | Ẩn nút hoặc thay bằng giải thích |
| N3 | "Reset" có thể xóa thiết kế đã mua (T6) | như T6 | như T6 |
| N4 | Không có cách xem thay đổi hay nhận bản cập nhật từ tác giả NoteType | Không có liên kết bản sao ↔ nguồn trong UI | Ngoài phạm vi đợt đầu; ghi nhận |

### 2.4 Cài deck từ chợ rồi tự sửa Template (hành trình J4)

Luồng: Chợ → Deck → Cài. Backend tạo `DeckInstall(clone_mode="logical_overlay")`, cây deck local và **một bản sao NoteType** cho người cài (`app/services/share/install.py:351-394`). Nội dung Note gốc không bị copy.

```text
Thẻ gốc của tác giả (Card → Template của TÁC GIẢ)  ──render──>  người cài thấy Template tác giả
Note người cài tự thêm (NoteType BẢN SAO)            ──render──>  Template trong bản sao
Người cài sửa Template bản sao                       ──chỉ đổi──> Note tự thêm
```

Bằng chứng: khi dựng phiên, `build_effective_study_card` luôn dùng `template=card.template` (`app/services/study_artifact_service.py:90-150`, dòng 118 và 147). Overlay có override cho field, thứ tự field và giá trị Note (`models/deck_clone_*`), nhưng **không có model override Template**.

| ID | Phát hiện | Tác động | Đề xuất |
|---|---|---|---|
| D1 | Người cài mở NoteType bản sao, sửa Template, lưu thành công, nhưng thẻ gốc của deck **không đổi** | "Sửa rồi mà không thấy gì" — lỗi trải nghiệm lớn nhất của hành trình này | Ngắn hạn: nhãn trên bản sao "Chỉ áp dụng cho thẻ bạn tự thêm vào <deck>; thẻ gốc dùng mẫu của tác giả". Dài hạn: D-T1 |
| D2 | Người cài thêm Template mới vào bản sao thì chỉ Note tự thêm có Card mới (`flashcards_share_service.py:283`, lọc `Note.user_id == user_id`) | Không thể thêm cách học mới (ví dụ luyện nghe) cho deck đã mua | Theo D-T1 |
| D3 | Không có đường nào từ Browse/Study tới Template của deck đang học; NoteType của tác giả trả 404 với người cài (`_owned_note_type`, `flashcard_content_service.py:1503-1511`) | Người học không biết Template nào đang được dùng | Ở phiên học/Browse: "Mẫu thẻ: <tên> (của tác giả)" |
| D4 | Nội dung Note đã sửa được riêng qua Browse (overlay, `browse_card_service.py:1338+`) ✅, nhưng API overlay schema `POST /api/shared/decks/<id>/clone/overlay` (đổi tên/ẩn/thêm field) chưa có UI gọi | Không tùy biến được cấu trúc field của deck đã cài | Ghi nhận; làm cùng D-T1 |
| D5 | Bản sao NoteType chụp Template lúc cài; sau khi tác giả hotfix (J5), Note tự thêm và thẻ gốc hiển thị khác nhau trong cùng một deck | Không nhất quán | Theo D-T1/D-T2 |

**Kết luận J4:** mô hình overlay đã cô lập **nội dung** (không đụng Note nguồn, đúng guardrail), nhưng **Template chưa tham gia overlay**. Mục tiêu "sửa Template của mình mà không ảnh hưởng người khác" hiện chỉ đạt với NoteType cài riêng, chưa đạt với deck đã cài.

### 2.5 Tác giả sửa Template của deck đã phát hành (hành trình J5)

| ID | Phát hiện | Bằng chứng | Tác động | Đề xuất |
|---|---|---|---|---|
| A1 | Tác giả được "hotfix" nội dung Template (HTML/CSS/tên) tại chỗ; thay đổi áp dụng cho **mọi người cài** từ phiên kế tiếp, không qua release, không changelog, không thông báo | `_ensure_version_safe_template_mutation`, nhánh TEMPORARY #138 (`flashcard_content_service.py:1529-1545`) | Người cài bị đổi giao diện ngoài ý muốn; ngược với mô hình release/rebase đang dùng cho nội dung | Ngắn hạn: cảnh báo trong trình soạn "Template đang dùng bởi deck đã phát hành — N người cài sẽ thấy thay đổi" và bắt ghi chú thay đổi. Dài hạn: D-T2 / 6B |
| A2 | Tác giả **không thể** thêm hoặc xóa Template cho NoteType có deck đã phát hành (`409 SHARED_SCHEMA_VERSIONING_REQUIRED`, thông điệp tiếng Anh) | `flashcard_content_service.py:1547-1554` | Tác giả không thêm được cách học mới cho deck của mình | Đổi thông điệp; nêu rõ hướng tạm thời. Mở khóa cần 6B (#137, chưa bắt đầu theo [README](./README.md)) |
| A3 | UI không cho biết NoteType nào đang được deck đã phát hành dùng | `serialize_note_type` không có cờ tương ứng | Tác giả chỉ biết khi bị lỗi (A2) hoặc sau khi đã làm đổi của mọi người (A1) | Thêm cờ `has_released_dependents` + số người cài vào API NoteType |

## 3. Đối chiếu với quyết định decoupling đã duyệt

| Quyết định (canonical plan, 2026-08-24) | Backend | UI | Còn thiếu |
|---|---|---|---|
| Sửa/thay/xóa Template giữ 100% tiến độ | ✅ tiến độ theo Note; xóa Template giữ state Note | ⚠️ không có nút xóa; không nói gì về tiến độ | T4, S3 |
| Learner chọn Template/application trước phiên | ✅ API compositions, phiên đóng băng lựa chọn | ⚠️ bộ chọn tối thiểu | S2–S6 |
| Một NoteType có nhiều cách học | ✅ nhiều Template = nhiều composition | ⚠️ tạo được nhưng không quản lý được | T1–T7 |
| Overlay-only, không mutate nguồn | ✅ nội dung; ❌ Template chưa có overlay | ❌ không giải thích | D1–D5, D-T1 |
| Release bất biến cho deck chia sẻ | ⚠️ Template có nhánh hotfix tạm thời #138; versioning 6B chưa làm | ❌ không cảnh báo | A1–A3, D-T2 |

## 4. Thứ tự nâng cấp đề xuất (UI P8 xếp cuối)

| Đợt | Nội dung | Loại thay đổi | Phát hiện đóng | Ước lượng |
|---|---|---|---|---|
| **1. Phiên học an toàn (P0)** | Hạn lease và phiên hết hạn; màn sự cố đồng bộ (UX-A1, UX-A2 của [báo cáo trước](./UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md)) | Frontend | rủi ro mất câu trả lời thuộc P5/P7 đã xong | 3–5 ngày |
| **2. Template & cách học dùng được** | Dialog tạo Template (tên, sao chép, số Note, giải thích); đổi tên; xóa có xác nhận; chặn mất bản chưa lưu; dialog thay `window.confirm`; sửa nghĩa "Reset"; thông điệp lỗi tiếng Việt; bộ chọn: giải thích tiến độ dùng chung, xem trước, "Dùng lần trước" | Chủ yếu frontend; API đã có (trừ số đếm theo lựa chọn) | T1–T8, S2–S4, S6 | 4–6 ngày |
| **3. Minh bạch clone** | Nhãn nguồn gốc NoteType (cài từ chợ / dùng cho deck đã cài / deck đã phát hành đang dùng); nhãn "chỉ áp dụng cho thẻ tự thêm"; ẩn "Chia sẻ lên Kho" cho bản sao; hiện "Mẫu thẻ của tác giả" ở phiên/Browse; cảnh báo tác giả trước khi hotfix; cờ `has_released_dependents` | Frontend + API nhỏ (đọc) | N1–N3, D1, D3, A1 (cảnh báo), A2 (thông điệp), A3, S5 (câu chữ) | 3–4 ngày |
| **4. Nhất quán** | U2 của báo cáo trước (màu, thuật ngữ, hướng dẫn phím tắt, Việt hóa) + C0/C1 của [báo cáo tùy chỉnh nút và thuật toán](./STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) | Frontend | UX-D1..D6 | 2–3 ngày |
| **4b. Cài đặt ôn tập theo deck** | C2 (preset + cài đặt người dùng, chỉ tham số đang được đọc), sau đó C3 (giới hạn thẻ mới/ngày) và C4 (chế độ 2 nút) | Backend ghi + frontend | xem [báo cáo tùy chỉnh](./STUDY_BUTTONS_AND_ALGORITHM_CUSTOMIZATION_2026-09-30.md) §4 | 4–6 ngày (C2) |
| **5. Module hóa Template (thiết kế + backend)** | Thực hiện các quyết định đã chốt ở [điều tra Template/NoteType §14](../../architecture/template-notetype-decoupling-investigation.md#14-post-investigation-decision-record-and-remaining-questions): 6B version Template cho deck chia sẻ (#137), bản cài ghim phiên bản, fork install-local khi người cài sửa, Template độc lập có Slot và binding. Xem §5b | ADR + schema + UI | D1, D2, D4, D5, A1, A2 | lập kế hoạch riêng (§5b) |
| **6. Sau cùng: P8** | U3, P8-00, năng lực P8 đầu tiên | | theo báo cáo trước §4–§5 | |

Đợt 2 và 3 chủ yếu là frontend trên API đã có, nên cho giá trị nhanh mà không đụng P9. Đợt 5 chạm vào clone overlay và release, là vùng rủi ro cao theo `AGENTS.md`: phải đọc [`CLONE_CUTOVER_REPORT.md`](../../plans/completed/CLONE_CUTOVER_REPORT.md) và test cả trường hợp sở hữu trực tiếp lẫn clone đã cài; tuyệt đối không quay lại mô hình copy toàn bộ.

## 5. Quyết định cần chủ sản phẩm

> **Đính chính (2026-09-30):** D-T1 và D-T2 **đã được chủ sản phẩm chốt** trong [điều tra Template/NoteType §14](../../architecture/template-notetype-decoupling-investigation.md#14-post-investigation-decision-record-and-remaining-questions) (#10, #11, #12). Hai mục đó không còn là câu hỏi mở; việc còn lại là triển khai (§5b). Hành vi hotfix #138 hiện tại **trái** với quyết định #10.

| ID | Câu hỏi | Trạng thái / khuyến nghị |
|---|---|---|
| D-T1 | Người cài deck có được dùng Template riêng cho **thẻ gốc** không? | **Đã chốt (#11):** có. Khi người cài sửa giao diện, hệ thống fork một bản install-local, không ảnh hưởng tác giả hay người khác. Chưa triển khai; cần ADR vì liên quan composition, snapshot phiên và Connect `source_ord`; giữ overlay-only (không copy Note/Card) |
| D-T2 | Hotfix Template của tác giả có tiếp tục áp dụng tức thì cho mọi người cài không? | **Đã chốt (#10):** bản cài tham chiếu phiên bản **được ghim**; sửa thì fork (copy-on-write). Hotfix tại chỗ #138 là giải pháp tạm, trái quyết định này. Trước khi có 6B: bắt buộc cảnh báo và ghi chú (đợt 3) |
| D-T3 | Thẻ gốc và Note tự thêm trong deck đã cài có học chung một phiên được không? | #12 đã cho phép **dùng chung một Template** cho thẻ gốc và thẻ tự thêm. Việc gộp thành một lựa chọn trong phiên vẫn cần quyết định riêng (sửa chính sách P3-05) |
| D-T4 | Template mới bắt đầu từ đâu? | Sao chép Template đang chọn |
| D-T5 | Có cho xóa Template trong UI không? | Có, với dialog nêu số Card bị gỡ và khẳng định tiến độ Note được giữ; backend đã chặn Template mặc định/cuối cùng |

## 5b. "Module hóa Template toàn phần" nằm ở đâu trong kế hoạch

Nguồn gốc:
- đề xuất [`DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md`](../../plans/proposals/DECOUPLE_TEMPLATE_NOTE_TYPE_PROPOSAL.md) (`FLAMA-ARCH-2026-TPL-01`), gồm 3 tầng: Template độc lập có Slot, Binding ánh xạ Field → Slot, và Template Marketplace;
- 21 quyết định sản phẩm ở [điều tra Template/NoteType §14](../../architecture/template-notetype-decoupling-investigation.md#14-post-investigation-decision-record-and-remaining-questions).

[Canonical plan](../../architecture/study-interaction-trigger-algorithm-plan.md) hợp nhất ý tưởng này vào §5 (Template role), §9 (StudyMode) và §16.3. **Không có phase riêng tên "module hóa"**: nó bị chia nhỏ theo phase như bảng dưới.

| Thành phần | Phase phụ trách | Trạng thái (2026-09-30) | Bằng chứng |
|---|---|---|---|
| Tiến độ không còn thuộc Card/Template (sửa, thay, xóa Template giữ tiến độ) | Phase 5, Phase 6 | ✅ Xong trên production | [README](./README.md) Phase 5–6 |
| Composition/StudyMode, chọn Template trước phiên | Phase 3 | ✅ Xong (mức tương thích) | `app/services/study_composition_service.py` |
| Danh tính "application" (Template áp dụng vào NoteType, `source_ord`), nền cho áp dụng lặp | Phase 6 (D6-03) | ✅ Có bảng `study_applications`; ❌ UI áp dụng lặp lùi sang Phase 8 (D6-09) | `models/study_application.py` |
| Template **độc lập** (không thuộc NoteType), khai báo Slot; binding Field → Slot; một Template dùng cho nhiều NoteType (quyết định #3–#7) | Canonical Phase 3 có liệt kê, nhưng ghi rõ "Physical reusable definition/application tables remain deferred"; P6 đẩy "binding kind mới" sang **Phase 8** | ❌ Chưa làm: `templates.note_type_id` vẫn bắt buộc, binding duy nhất là `legacy-fielddef-direct` | `study_session_service.py:767`; [P6 plan](./P6_EXECUTION_PLAN_2026-09-29.md) dòng "Không thuộc Phase 6" |
| Version Template cho deck chia sẻ; cho tác giả thêm/xóa Template khi đã phát hành | **Track 6B** (#137, D6-08) | ❌ Chưa bắt đầu; tạm có hotfix #138 | `flashcard_content_service.py:1514-1554` |
| Bản cài ghim phiên bản; fork install-local khi người cài sửa (quyết định #1, #10, #11, #12) | **Chưa gán phase/task nào** | ❌ Chưa làm; phụ thuộc 6B | §2.4 báo cáo này |
| Template Marketplace (bán Template riêng, soft delete; quyết định #1, #2, #21) | Canonical §16.3 Priority 1 #13 ("before broad reuse/distribution"); **chưa gán phase** | ❌ Chưa làm | — |
| Đổi tên Field không làm gãy Template; hiện phụ thuộc và hỏi cập nhật alias; Field bị xóa thì Slot trống + cảnh báo (quyết định #19, #20) | Binding ổn định: cùng lõi Slot (Phase 8); dọn cơ chế theo tên: **Phase 9** | ❌ Chưa làm: đổi tên Field chỉ đổi khóa JSON của Note (`flashcard_content_service.py:1622-1662`); Template còn `{{TênCũ}}` render rỗng, **không cảnh báo** | `flashcard_content_service.py:618-632` |
| Nhập Anki: chuẩn hóa token thành input tái dùng (quyết định #13, #14) | Một phần ở Phase 6 (`source_ord` gắn application); phần chuẩn hóa token đi cùng lõi Slot | ⚠️ Một phần | `models/study_application.py:11-12` |
| Template JS chỉ nhận input khai báo (quyết định #16, #17: tạm cho đọc toàn bộ) | Phase 9 (retire legacy full-context ABI) | ⏸ Cố ý giữ tương thích | canonical §5.1 |

**Nhận xét cho thứ tự ưu tiên hiện hành (UI P8 xếp cuối):** phần lõi của module hóa (Template độc lập + Slot/binding) đang nằm trong Phase 8, còn fork cho người cài và Template Marketplace chưa có phase nào. Nếu muốn đáp ứng câu hỏi "clone deck tự sửa Template không ảnh hưởng người khác" (§1, câu 4b) mà không phải chờ tương tác mới của P8, nên tách một track riêng, tạm gọi **"Template Modularization"**, theo thứ tự:

1. **6B** — version Template cho deck chia sẻ; bản cài ghim phiên bản.
2. **Fork install-local** cho thẻ gốc, theo quyết định #11. Làm được trên `study_applications` hiện có mà không cần Slot.
3. **Template độc lập + Slot/binding + UI ánh xạ Field** (quyết định #3–#7, #19, #20).
4. **Template Marketplace.**

Bước 1–2 giải quyết D1, D2, D5, A1, A2. Bước 3 là nền để P8 thêm tương tác mới. Mỗi bước cần plan riêng theo mẫu P6 (quyết định, gate, work package, probe MySQL) và phải tuân guardrail overlay-only.

## 6. Kiểm chứng khi triển khai

- Test frontend: `python scripts/run_tests.py --module flashcards,study --frontend-only`. Khi thêm cờ API: `--module flashcards,marketplace --backend-only`.
- Hành trình trình duyệt (profile Chrome riêng theo `AGENTS.md`), mỗi hành trình với hai tài khoản tác giả/người cài:
  1. Tạo, đổi tên, xóa Template trên NoteType có Note; kiểm tra bộ chọn và tiến độ Note không đổi.
  2. Cài NoteType từ chợ, sửa Template; tài khoản tác giả không thấy thay đổi.
  3. Cài deck, sửa Template bản sao; kiểm tra nhãn giải thích và thẻ gốc giữ Template tác giả.
  4. Tác giả hotfix Template deck đã phát hành; kiểm tra cảnh báo, và phiên đang mở của người cài không đổi (P4-00).
  5. Tác giả thêm Template vào NoteType đã phát hành; kiểm tra thông điệp lỗi tiếng Việt.

## 7. Handoff

```text
Task ID: UIUX-COMPLETED-PHASES-JOURNEY
Primary outcome: trả lời 4 câu hỏi người dùng về Template/chế độ học/clone; thứ tự nâng cấp mới với UI P8 xếp cuối
Files changed: docs/task/decoupling/UIUX_COMPLETED_PHASES_USER_JOURNEY_AUDIT_2026-09-30.md (mới); ghi chú ưu tiên trong UIUX_GAP_AUDIT_PRE_P8_2026-09-30.md và README.md
Runtime change: none
Tests added or updated: none (điều tra)
Known limitations: S5 và hành vi hiển thị thực tế của J3–J5 cần xác minh trên trình duyệt với hai tài khoản
Follow-up: đợt 1–5 ở §4; quyết định D-T1..D-T5
```
