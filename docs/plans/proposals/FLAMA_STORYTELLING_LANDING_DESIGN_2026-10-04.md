# Flama — Truyền lửa, cùng mở rộng tri thức

> Bản thiết kế v1 · 04/10/2026 · Trạng thái: đề xuất, chưa triển khai giao diện.
>
> Deliverable hiện tại là tài liệu này. Khi triển khai, tạo màn review riêng tại `/landing-story-preview`. Landing hiện tại tại `/` chỉ được thay thế sau khi chủ sản phẩm xem bản hoàn thiện và duyệt rõ ràng việc thay thế.

## 1. Ý tưởng chủ đạo

**Một người có thể tìm ra điều mới. Khi điều ấy được sẻ chia, cả cộng đồng có thể tiến xa hơn.**

Landing kể một hành trình bằng motion graphic liên tục: từ con người học cách sử dụng lửa, trao lửa cho nhau, đến truyền đạt, vun trồng, chế tạo, thắp sáng và những bước tiến như máy tính, AI. Các phát minh là hình ảnh về thành quả của tri thức được tiếp nối. Hành trình trở về với những con người đang học hỏi và góp tri thức trên Flama.

Ngọn lửa là ẩn dụ cho kiến thức. Người trao lửa vẫn giữ ngọn lửa của mình; người nhận có thể học thêm, bổ sung rồi trao tiếp. Đây là hành động thị giác quan trọng nhất: **chia sẻ làm tri thức lan rộng**.

Flama xuất hiện như nơi tiếp nối hành động đó hôm nay: học điều mình cần, chia sẻ điều mình biết, cùng phát triển kho tri thức chung cho cộng đồng, ở nhiều lĩnh vực.

Tên concept: **“Ngọn lửa được trao tiếp”**.

Thông điệp kết:

> **Học điều bạn cần. Chia sẻ điều bạn biết.**  
> Để mỗi người đi xa hơn, và cộng đồng cùng tiến lên.

Người xem cần nhớ ba điều: tri thức lớn lên qua sự tiếp nối; bất kỳ ai cũng có điều đáng chia sẻ; Flama giúp biến việc học và chia sẻ thành một hành trình chung.

## 2. Quyết định thiết kế cho bản preview

| Hạng mục | Hướng thiết kế v1 |
|---|---|
| Cách kể | Một hành trình hình ảnh nối liền; lời dẫn tiếng Việt ngắn, dễ đọc. |
| Điều khiển | Cuộn tự nhiên để dẫn nhịp; người xem quyết định tốc độ và có thể cuộn ngược. |
| Art style | Minh họa vector 2D có chiều sâu nhẹ, hình khối mềm, chất giấy rất nhẹ, ánh lửa ấm. |
| Nhân vật chính | Con người và cộng đồng; một đốm lửa làm điểm dẫn mắt xuyên suốt. |
| Không gian | Mở đầu tối và ấm; dần mở rộng, sáng hơn khi tri thức lan truyền. |
| Âm thanh | Bản đầu không cần âm thanh; toàn bộ câu chuyện hiểu được bằng hình và chữ. |
| Điểm kết | Mạng tri thức → các trang/thẻ học → logo lửa và sách Flama → ngọn lửa trao về phía người xem. |
| Review | Route riêng, truy cập được cả khi chưa đăng nhập và đã đăng nhập; không tự chuyển sang dashboard. |

Các lựa chọn này đủ để triển khai bản review đầu tiên. Có thể chỉnh nhịp, màu nền và mức độ chuyển động dựa trên bản preview thực tế.

## 3. Ngôn ngữ hình ảnh và nhận diện Flama

### 3.1. Một thế giới minh họa thống nhất

- Người, bàn tay, cây, công cụ và máy móc dùng cùng tỷ lệ, độ bo và cách đổ bóng. Nhân vật cách điệu nhưng có cử chỉ rõ ràng, tránh cảm giác icon đứng cạnh nhau.
- Bố cục có tiền cảnh, chủ thể và hậu cảnh; tạo chiều sâu bằng kích thước, độ sáng và chuyển động chậm, không cần dựng thế giới 3D.
- Một đường sáng màu lửa đi xuyên các cảnh. Nó có thể trở thành nét ký hiệu, đường nước, chuyển động bánh đà, dây tóc bóng đèn hoặc đường truyền dữ liệu.
- Mỗi cảnh có một hành động chính: tìm ra, trao, kể, vun trồng, cải tiến, thắp sáng, kết nối, bổ sung, đóng góp.
- Con người xuất hiện xuyên suốt. Phát minh luôn có dấu vết học hỏi, thử nghiệm và trao đổi giữa nhiều người.
- Khoảng trống quanh chữ rộng và ổn định. Chữ nằm trên vùng nền phẳng, tránh chồng lên chi tiết chuyển động.

Không dùng ảnh stock, nhiều phong cách minh họa lẫn nhau, nền hạt sáng dày đặc hoặc một loạt feature card để kể các chương chính. Minh họa cần thể hiện sự trao truyền thực sự, không chỉ đặt biểu tượng lửa bên cạnh nội dung.

### 3.2. Bảng màu

Nguồn nhận diện đang dùng: `frontend/src/index.css`, `frontend/src/shared/components/Brand.tsx`, `frontend/public/logo.png` và `frontend/public/flama-mark.svg`. `DESIGN.md` là hướng dẫn bổ sung; khi khác với code, giữ nhận diện thực tế trong code.

| Vai trò | Màu / nguồn | Cách dùng |
|---|---|---|
| Cam Flama | `--primary`: `oklch(0.635 0.215 35)` ở light; `oklch(0.70 0.21 40)` ở dark | Đốm lửa dẫn chuyện, điểm sáng tri thức, CTA. |
| Gradient thương hiệu | `from-primary via-orange-500 to-amber-500` | Giữ gradient hiện có của Brand; dùng cùng hướng sắc cho ánh lửa. |
| Sắc lửa minh họa | `#ef3303` → `#fe6808` → `#fea00e`, lấy từ `flama-mark.svg` | Đỏ cam ở chân lửa, cam ở thân, hổ phách ở điểm sáng. |
| Lõi lửa | `#fff4ec`, lấy từ `flama-mark.svg` | Lõi sáng nhỏ; hạn chế glow lớn. |
| Nền sáng ấm | `--background`, `--secondary`, `--muted` | Không gian học và cộng đồng ở đoạn kết. |
| Chữ và đường nét | `--foreground`, `--muted-foreground` | Màu đơn sắc, tương phản rõ. |
| Nền mở đầu, đề xuất | Than nâu `#211A17`, vùng sáng giấy `#FFF8EF` | Token riêng của story; cần kiểm tra tương phản trong preview. |

Cam và ánh lửa dẫn mắt thay vì phủ toàn bộ màn hình. Cảnh đầu có thể tối để thấy lửa, nhưng giữ cảm giác ấm và nhân văn. Hình ảnh máy tính và AI trong chuỗi phát minh vẫn thuộc bảng màu này; không chuyển thành một thế giới neon xanh/tím.

Giữ **logo `/logo.png` đang được Brand sử dụng**. Logo kết hợp ngọn lửa và các trang sách, phù hợp với đoạn kết. SVG minh họa có thể tiến dần về silhouette đó rồi nối sang logo thật; không âm thầm thay logo bằng `flama-mark.svg`.

Chữ kể chuyện và tiêu đề dùng màu đơn sắc. Wordmark Flama giữ gradient thương hiệu hiện có.

### 3.3. Typography và bố cục

- Dùng Geist Variable hiện có, hỗ trợ đầy đủ dấu tiếng Việt.
- Hero đề xuất: 48–72px desktop, 32–40px mobile, tối đa ba dòng. Đây là kích thước riêng của landing mới.
- Lời dẫn từng chương: 28–40px desktop, 22–28px mobile; một câu chính và tối đa một câu phụ.
- Body: 16–18px, line-height 1.5–1.7. Không dùng chữ quá nhỏ để giữ bố cục minh họa.
- Container phần nội dung tối đa khoảng 1280px; phần tranh có thể tràn bề ngang. Padding 20–24px mobile, 40–64px desktop.
- Desktop ưu tiên tranh khoảng 60% và chữ khoảng 40%; đổi phía có chủ đích khi chuyển cảnh. Mobile ưu tiên tranh phía trên, chữ phía dưới.

## 4. Storyboard — chín nhịp trong một câu chuyện

Các cảnh là liên tưởng nghệ thuật về sự tiếp nối tri thức, không phải timeline khảo cổ hay danh sách niên đại. Không gắn năm hoặc khẳng định ngôn ngữ chỉ xuất hiện sau khi biết dùng lửa. Động cơ hơi nước và bóng đèn là các hình ảnh đại diện cho những bước tiến.

### Cảnh 01 — Một đốm sáng

**Chữ chính:** “Một khám phá có thể bắt đầu từ một người.”

Không gian rộng, tối ấm. Một người quan sát, thử cách tạo và giữ lửa; đốm sáng nhỏ hiện lên giữa hai bàn tay. Ánh lửa làm rõ khuôn mặt và một người khác đang nhìn sang.

Hero luôn có một keyframe đọc được ngay khi tải, không phải chờ animation. Nhãn nhỏ “Flama · Cùng học, cùng chia sẻ” giúp người xem biết mình đang ở đâu. Có gợi ý “Cuộn để theo ngọn lửa” và liên kết “Đến với Flama” để đi thẳng đến đoạn cộng đồng.

**Nối cảnh:** Người đầu tiên đưa tay về phía người bên cạnh. Máy quay đi theo đốm sáng, không fade toàn màn hình.

### Cảnh 02 — Khi ngọn lửa được trao

**Chữ chính:** “Khi được sẻ chia, nó có thể sưởi ấm cả cộng đồng.”

Ngọn lửa thứ hai được thắp lên. Ngọn lửa đầu tiên vẫn sáng. Người nhận trao tiếp cho một người khác; máy quay mở rộng để thấy một vòng cộng đồng. Những bàn tay nối nhau tạo nhịp chuyển động dịu, không sao chép lửa hàng loạt ngay lập tức.

**Chi tiết cần thấy rõ:** Chia sẻ không làm người trao mất đi tri thức của mình.

**Nối cảnh:** Đường khói từ một đốm lửa kéo thành nét cong, đi vào cử chỉ kể chuyện của một người trong vòng cộng đồng.

### Cảnh 03 — Kể lại, ghi nhớ, cùng vun trồng

**Chữ nhịp A:** “Ta kể lại. Ta ghi nhớ.”  
**Chữ nhịp B:** “Để người đến sau không phải bắt đầu từ đầu.”

Nét khói thành lời nói cách điệu, dấu vẽ và ký hiệu. Một người chỉ cách làm; người khác lặp lại, thêm một nét, rồi truyền tiếp. Ký hiệu không phải chữ ngẫu nhiên khó đọc; dùng hình biểu đạt đơn giản và nhất quán.

Một điểm sáng trong ký hiệu rơi xuống thành hạt giống. Các nét mở thành luống đất, đường nước và cây. Nhiều người cùng chăm sóc; kinh nghiệm được truyền đi bằng cử chỉ và dấu chỉ dẫn. Một người sửa cách dẫn nước để cây ở luống bên cạnh cũng được tưới.

**Nối cảnh:** Vòng quay của bánh xe dẫn nước giữ tâm và hướng xoay, chuyển thành bánh đà của cảnh chế tạo. Đốm sáng vẫn nằm trên cùng quỹ đạo.

### Cảnh 04 — Những ý tưởng tiếp nối

**Chữ chính:** “Điều một người tìm ra trở thành điểm bắt đầu của người khác.”

Bàn tay trao một bản vẽ; người khác thêm chi tiết và thử lại. Bánh xe, bánh răng và động cơ hơi nước hình thành qua các bước cải tiến. Lửa xuất hiện ở nguồn nhiệt của máy, đồng thời đường sáng nối các bản vẽ để nhấn vào tri thức được chia sẻ.

Máy hoạt động sau sự phối hợp của nhiều người. Không đặt một “thiên tài” đứng riêng cạnh phát minh hoàn chỉnh.

**Nối cảnh:** Hơi nước kéo thành một đường cong, thu gọn về vị trí dây tóc của bóng đèn. Chuyển động bánh đà chậm lại khi vùng sáng mới mở ra.

### Cảnh 05 — Thắp sáng những khả năng

**Chữ chính:** “Ý tưởng nối tiếp ý tưởng. Những giới hạn dần được mở ra.”

Dây tóc sáng lên bằng sắc hổ phách. Ánh đèn lan đến những bàn làm việc: có người đọc, có người viết, có người trao đổi. Một chiếc đèn trở thành nhiều điểm sáng trong không gian cộng đồng.

Độ sáng nền tăng từ từ; ánh lửa không bị thay bằng một palette hoàn toàn khác. Có thể thêm chi tiết một bản ghi chú được chuyền qua nhiều bàn để nhắc lại hành động trao truyền.

**Nối cảnh:** Một điểm sáng của bóng đèn thành điểm ảnh trên màn hình. Các bàn làm việc dần chuyển thành những cửa sổ kết nối.

### Cảnh 06 — Tri thức vượt khoảng cách

**Chữ chính:** “Điều ta biết có thể đến với người chưa từng gặp.”

Một máy tính mở ra nhiều cửa sổ. Những người ở các vị trí khác nhau trao các mảnh kiến thức qua đường nối màu lửa. Mỗi người nhận một mảnh, học thêm, bổ sung một mảnh khác.

Các chủ đề có thể gợi bằng một từ tiếng Nhật, một công thức, một sơ đồ lập trình và một bản vẽ cây. Chúng thuộc cùng một ngôn ngữ đồ họa, thể hiện Flama dành cho nhiều lĩnh vực.

Cuối cảnh có một nhịp ngắn nối máy tính với hình tượng AI: các điểm ảnh thành mạng nút liên kết, kèm nhãn “AI” nhỏ để nhận ra bước tiến này. AI xuất hiện trong cùng chuỗi hình ảnh phát minh như động cơ và bóng đèn, không có giao diện hỏi đáp hoặc trình diễn chức năng sản phẩm.

**Nối cảnh:** Máy quay lùi khỏi hình tượng công nghệ, theo đường sáng màu lửa về những bàn tay đang trao tri thức cho nhau.

### Cảnh 07 — Tri thức được trao, bước tiến được mở

**Chữ chính:** “Những điều được sẻ chia mở đường cho những bước tiến mới.”

Máy quay mở rộng để thấy phía sau những bước tiến là nhiều con người đang tiếp nối hiểu biết của nhau. Một người góp cách làm, một người bổ sung kinh nghiệm, người nhận kết nối chúng thành một ý tưởng mới rồi trao tiếp. Các ngọn lửa được thắp thêm trong khi lửa của người trao vẫn sáng.

Những đóng góp nhỏ từ nhiều người tạo thành một mạng tri thức chung. Chủ thể của cảnh là bàn tay, con người và hành động chia sẻ; các phát minh vừa đi qua trở thành dấu vết ở hậu cảnh. Cảnh này làm rõ lý do Flama xuất hiện: một nơi để mọi người trao điều mình biết và cùng phát triển kho tri thức cộng đồng.

**Nối cảnh:** Những đường lửa nối các đóng góp thành các trang/thẻ học trong một không gian chung, sáng và ấm. Mạng cộng đồng giữ nguyên khi bước sang Flama.

### Cảnh 08 — Ngọn lửa hôm nay: Flama

**Chữ chính:** “Flama — cùng nhau thắp sáng kho tri thức chung.”

**Chữ phụ:** “Mỗi điều bạn học được, mỗi điều bạn chia sẻ, đều có thể trở thành điểm bắt đầu của một người khác.”

Các thẻ học hiện ra ở giữa cộng đồng. Một người nhận bộ thẻ, học và ghi nhớ; một người khác tạo nội dung từ hiểu biết của mình; một góp ý làm học liệu rõ hơn. Đốm lửa chuyển từ người sang thẻ rồi sang người tiếp theo.

Ba hành động được thể hiện trong cùng một bố cục:

- **Học:** nhận tri thức và biến thành điều mình hiểu.
- **Chia sẻ:** đưa điều mình biết đến những người khác.
- **Cùng phát triển:** bổ sung, góp ý và cải thiện học liệu chung.

Đây là đoạn nối vào sản phẩm. Có thể dùng một cụm thẻ minh họa sát UI thật, không mở ra bảng tính năng dài. Không đưa thuật ngữ nội bộ như NoteType hay logical overlay vào lời kể.

Đặt anchor `#flama-community` tại phần này. Chữ “kho tri thức chung” diễn đạt sứ mệnh cộng đồng; không hàm ý dữ liệu cá nhân tự động được công khai hoặc mọi học liệu đều miễn phí.

**Nối cảnh:** Các trang/thẻ hội tụ về hình sách, đường sáng kéo lên thành ngọn lửa. Hình cuối nối sang logo thật của Flama ở cùng vị trí.

### Cảnh 09 — Ngọn lửa tiếp theo là của bạn

**Chữ chính:** “Bạn biết một điều có thể giúp ai đó đi xa hơn.”

**Chữ kết:** “Học điều bạn cần. Chia sẻ điều bạn biết.”

Logo lùi nhẹ để nhường khoảng trống cho một bàn tay mở về phía người xem. Một ngọn lửa nhỏ được trao đến đó, trong khi các ngọn lửa của cộng đồng vẫn sáng ở phía sau. Bố cục dừng ổn định để người xem đọc và chọn hành động.

CTA chính với khách: **“Cùng truyền lửa”** → `/register`. Chữ phụ bên dưới: “Bắt đầu bằng việc học, rồi chia sẻ khi bạn sẵn sàng.”

CTA chính khi đã đăng nhập: **“Tiếp tục hành trình”** → `/dashboard`.

CTA phụ dẫn tới phần cộng đồng hoặc kho bộ thẻ theo trạng thái đăng nhập, như mục 7. Kết thúc chuyển động tại đây; không để CTA chạy theo hoặc trôi khỏi vùng nhìn.

## 5. Quy tắc chuyển cảnh liên tục

“Continuous animation” được hiểu là cùng một hành trình thị giác, có vật thể và cử chỉ nối cảnh. Các cảnh có thể nằm ở component khác nhau, nhưng người xem phải cảm thấy đang theo một ngọn lửa qua một thế giới thống nhất.

| Nối cảnh | Vật thể giữ liên tục | Phép chuyển |
|---|---|---|
| 01 → 02 | Đốm lửa giữa bàn tay | Theo tay trao, mở rộng khung nhìn. |
| 02 → 03 | Đường khói / đường sáng | Thành nét kể chuyện và ký hiệu, rồi một điểm thành hạt giống. |
| 03 → 04 | Bánh xe, tâm xoay và đốm sáng | Nối hình bánh xe dẫn nước với bánh đà. |
| 04 → 05 | Đường cong hơi nước | Thu về dây tóc bóng đèn, đồng thời chuyển vùng sáng. |
| 05 → 06 | Điểm sáng hổ phách | Thành điểm ảnh, mở thành mạng cửa sổ. |
| 06 → 07 | Đường sáng từ các hình tượng phát minh | Theo đường lửa về bàn tay trao tri thức, mở rộng ra cộng đồng. |
| 07 → 08 | Các đóng góp và mạng cộng đồng | Nối thành trang/thẻ học, giữ cộng đồng làm chủ thể khi Flama xuất hiện. |
| 08 → 09 | Trang sách và đường lửa | Hội tụ thành logo; bàn tay trao một ngọn lửa về phía người xem. |

Ở thời điểm nối, giữ ít nhất một trong ba yếu tố: vị trí đốm sáng, hướng chuyển động hoặc hình khối chủ thể. Cảnh mới bắt đầu xuất hiện trước khi cảnh cũ biến mất. Dùng morph ở những hình có cấu trúc phù hợp; ở các hình khác, dùng chuyển vị trí, nối hình và che/mở lớp để giữ tính liên tục.

Một chương chỉ có một chuyển động dẫn chuyện nổi bật. Hậu cảnh chuyển chậm hơn; ánh lửa dao động rất nhẹ. Không lắc camera, không zoom nhanh, không nhấp nháy và không lấy chuyển động hạt làm nội dung chính.

## 6. Nhịp cuộn, mobile và khả năng tiếp cận

### Desktop và tablet rộng

- Một sân khấu minh họa sticky; các đoạn văn theo từng chương nằm trong luồng DOM để đọc, tìm kiếm và điều hướng bằng bàn phím.
- Đặt mục tiêu ban đầu khoảng 8–10 chiều cao viewport cho toàn hành trình, sau đó chỉnh bằng review. Cảnh trao lửa, cộng đồng Flama và CTA có khoảng dừng dài hơn montage phát minh.
- Progress từng chương: khoảng 20% vào cảnh, 55% giữ hành động và đọc chữ, 25% nối cảnh. Đây là tỷ lệ khởi đầu để tuning, không phải thời gian tự chạy bắt buộc.
- Cuộn native, không chặn wheel/touch hay ép người xem dừng ở từng cảnh. Khi cuộn nhanh hoặc ngược, hình phải khớp vị trí hiện tại, không phát lại một chuỗi animation bị tồn đọng.
- Header gọn, logo và các lối vào rõ ràng. Mở đầu đã có đường đến đoạn Flama, không bắt người xem hoàn thành câu chuyện mới được đăng ký.

### Mobile

- Bố cục dọc, tranh và lời dẫn cùng hiện đủ trong các khối đọc. Các điểm nối hình vẫn liên tục nhưng giảm camera pan và độ dày chi tiết.
- Bản đầu ưu tiên cuộn native với cảnh theo luồng trang; không áp dụng một chuỗi pin dài trên màn nhỏ. Dùng `svh`/chiều cao ổn định để giảm nhảy cảnh khi thanh trình duyệt thay đổi.
- Giữ đầy đủ lửa → cộng đồng → truyền đạt/canh tác → động cơ/bóng đèn → máy tính/AI → tri thức được trao tiếp → Flama. AI chỉ là một nhịp trong chuỗi phát minh; ưu tiên không gian cho con người và hành động chia sẻ.
- Kiểm tra từ 320px; nút dễ chạm, tối thiểu 44px. Tranh không gây tràn ngang; chữ không bị che bởi bàn tay hay máy móc.

### Reduced motion và điều khiển

- Tôn trọng `prefers-reduced-motion`; bổ sung nút rõ tên **“Tắt chuyển động” / “Bật chuyển động”** trong preview.
- Khi tắt chuyển động, hiển thị các keyframe tĩnh theo trình tự, đủ lời dẫn và CTA; bỏ pin, parallax, morph và loop. Câu chuyện vẫn hoàn chỉnh.
- Nội dung kể chuyện là HTML thật với heading theo thứ tự. Tranh trang trí dùng `aria-hidden`; các nút điều khiển có tên và focus rõ.
- Không đọc lại lời dẫn qua live region mỗi lần người xem cuộn. Link “Đến với Flama” phải đưa đến phần có thể đọc và focus bằng bàn phím.
- Dừng các loop khi trang ở nền hoặc phần tranh ngoài vùng nhìn. Không tự phát âm thanh.
- Đo tương phản cho từng nền thực tế, đặc biệt chữ ở cảnh đầu tối và cảnh chuyển sang sáng.

## 7. Từ câu chuyện đến trải nghiệm sản phẩm

Sau cảnh kết, có một vùng thông tin ngắn và bình tĩnh: ba hành động Học / Chia sẻ / Cùng phát triển, FAQ gọn, đường dẫn hỗ trợ và pháp lý. Tính năng chỉ làm bằng chứng cho sứ mệnh, không chiếm lại trọng tâm trang.

| Người xem / vị trí | Hành động | Đích đề xuất |
|---|---|---|
| Mọi người, đầu trang | “Đến với Flama” | Anchor `#flama-community` trong preview. |
| Khách, header | “Đăng nhập” | `/login`. |
| Khách, CTA cuối | “Cùng truyền lửa” | `/register`. |
| Khách, CTA phụ | “Khám phá cách Flama kết nối tri thức” | Anchor `#flama-community`. |
| Đã đăng nhập, CTA cuối | “Tiếp tục hành trình” | `/dashboard`. |
| Đã đăng nhập, CTA phụ | “Khám phá bộ thẻ cộng đồng” | `/marketplace/decks`. |
| Footer | Hỗ trợ, điều khoản, bảo mật | `/support`, `/terms`, `/privacy`. |

Marketplace hiện nằm sau auth guard; không thiết kế CTA cho khách như thể có thể duyệt công khai ngay. Thao tác chia sẻ/đăng học liệu tiếp tục theo quyền và luồng hiện có; bản landing không mở rộng quyền.

FAQ đề xuất chỉ tập trung: Flama dành cho ai; học và chia sẻ bắt đầu thế nào; chia sẻ có tự công khai dữ liệu cá nhân không; nội dung cộng đồng có miễn phí không. Câu trả lời cần khớp behavior được kiểm tra khi triển khai.

Giữ thông tin hỗ trợ/nhà tài trợ đã được xác minh ở phần phụ phù hợp. Không thêm số lượng cộng đồng, nhận xét người dùng, logo đối tác hoặc cam kết tính năng chưa có bằng chứng. Thẻ minh họa trong preview dùng dữ liệu mẫu, không lấy nội dung riêng tư để trang trí.

## 8. Cách triển khai màn review độc lập

### Hiện trạng đã kiểm tra

- `frontend/src/App.tsx` định nghĩa React Router, mount `LandingPage` tại `/`. Chưa có route `/landing` hoặc `/landing-story-preview`.
- `frontend/src/pages/LandingPage.tsx` là landing hiện tại; người đã đăng nhập được redirect đến `/dashboard`.
- `frontend/src/layouts/AppLayout.tsx` có `PublicLayout` là hàm nội bộ, background, header, footer và mascot. Wrapper có `overflow-hidden`, cần tránh làm ancestor của sân khấu sticky mới.
- `app/spa.py` đã phục vụ SPA cho các navigation GET/HEAD phù hợp. Tạo route preview không cần API nghiệp vụ hoặc migration database mới.
- `frontend/package.json` hiện chưa có GSAP, Motion/Framer Motion, Lottie hoặc Three.js.

### Cấu trúc đề xuất, chưa phải file đã tồn tại

```text
frontend/src/features/landing-story/
  pages/LandingStoryPreviewPage.tsx
  components/StoryPreviewShell.tsx
  components/StoryStage.tsx
  components/StoryChapter.tsx
  components/StoryControls.tsx
  components/StoryCommunity.tsx
  components/StoryClosing.tsx
  hooks/useStoryProgress.ts
  hooks/useStoryMotionPreference.ts
  data/storyChapters.ts
  assets/                         # SVG minh họa riêng của story
  styles/story.css                # CSS giới hạn phạm vi story
```

Thêm lazy route `/landing-story-preview` ở nhánh riêng trong `App.tsx`, ngoài cây `AppLayout`, dùng `StoryPreviewShell`. Shell tái sử dụng Brand và UI primitives phù hợp, có header/footer riêng cho câu chuyện. Không sao chép auth redirect của landing hiện tại. Tranh và nội dung cơ bản không phải chờ bootstrap; trạng thái đăng nhập chỉ quyết định CTA phù hợp.

Hiển thị một nhãn review nhỏ “Bản xem trước landing mới” và link “Về trang hiện tại”. Không đưa nút phê duyệt giả vào UI; việc duyệt thay thế là quyết định của chủ sản phẩm sau review.

Toàn bộ style đặt dưới phạm vi story. Không đổi `LandingPage.tsx`, token global, Brand hay asset cũ để phục vụ bản preview. Không đưa route review vào điều hướng chính. Nếu cần `noindex`, áp dụng theo route và phục hồi khi rời trang; không sửa metadata chung trong `frontend/index.html` làm ảnh hưởng landing hiện tại. Route riêng và `noindex` không phải cơ chế giới hạn truy cập.

## 9. Hướng dựng motion và tài sản minh họa

Ưu tiên SVG tự dựng kết hợp CSS, Web Animations API và một bộ điều khiển progress qua `requestAnimationFrame`, phù hợp với dependency hiện có. Chốt khả năng dựng các chuyển cảnh khó bằng prototype trước khi quyết định có cần thư viện animation mới.

- Một progress chính xác định trạng thái của hành trình; từng cảnh nhận progress cục bộ. Không tạo chín scroll listener độc lập.
- Tách lời dẫn/content khỏi điều khiển animation. Không cập nhật React state toàn bộ trang theo mỗi frame; dùng ref/CSS custom properties cho giá trị liên tục.
- Ưu tiên `transform` và `opacity`; morph phức tạp chỉ đặt ở điểm nối quan trọng. Giảm filter blur/glow lớn, đặc biệt trên mobile.
- Chỉ kích hoạt cảnh hiện tại và cảnh liền kề; cleanup listener, observer và animation khi unmount. Thoát preview không để effect tác động các route khác.
- Lazy-load module story và các asset chưa cần ngay. Hero có kích thước dành sẵn, tranh tĩnh dự phòng và lời dẫn hiển thị sớm.
- Dữ liệu câu chuyện lưu một nguồn duy nhất cho motion mode và static mode, tránh hai bản copy khác nhau.

Tài sản cần dựng: nhân vật/bàn tay theo một bộ hình; lửa và điểm sáng; ký hiệu truyền đạt; hạt/cây/luống đất; bánh xe/bánh đà/động cơ; bóng đèn; máy tính/cửa sổ; hình tượng AI ngắn trong chuỗi phát minh; mạng đóng góp cộng đồng; thẻ/trang sách; keyframe cuối căn theo logo thật.

Trước hết dựng bộ keyframe đồng nhất, sau đó mới nối motion. Mỗi asset cần xác định điểm neo để cảnh sau tiếp nối vị trí/hình khối của cảnh trước. Không ghép chín minh họa rời rồi chỉ thêm fade-in.

Mục tiêu hiệu năng cho review: cuộn mượt trên thiết bị thử đại diện, không nhảy layout khi tải asset, không tải story vào trang hiện tại và không duy trì animation khi đã rời preview. Đây là mục tiêu cần đo khi có màn triển khai, chưa phải kết quả đã đạt.

## 10. Các bước triển khai và điểm duyệt

| Bước | Kết quả cần có | Điều kiện đi tiếp |
|---|---|---|
| 1. Bản thiết kế | Tài liệu này: concept, lời dẫn, storyboard, art direction, cách tách preview. | Đủ để dựng bản review đầu tiên; chi tiết có thể chỉnh trong preview. |
| 2. Keyframe + prototype | Dựng cảnh lửa đầu, trao lửa và đoạn thẻ/sách → logo; thử nối cảnh trên desktop/mobile. | Art style thống nhất và chuyển cảnh khả thi. |
| 3. Màn riêng hoàn chỉnh | `/landing-story-preview` có đủ chín nhịp, CTA, mobile và static mode. | Tự kiểm tra toàn hành trình trước khi gửi link review. |
| 4. Review và chỉnh | Chủ sản phẩm xem màn, góp ý; chỉnh copy, tranh và nhịp trên cùng route riêng. | Màn hoàn thiện đáp ứng checklist bên dưới. |
| 5. Duyệt thay thế | Chủ sản phẩm duyệt rõ ràng việc dùng bản mới làm landing chính. | Chỉ lúc này mới thay route `/` và xử lý chuyển giao/rollback. |

**Hoàn thiện preview không đồng nghĩa đã được phép thay landing.** Trong quá trình làm bản review, `/` vẫn dùng bản cũ. Khi được duyệt, việc đưa bản mới vào `/` cần giữ behavior đăng nhập/CTA đã thống nhất và có cách quay lại bản cũ.

## 11. Checklist nghiệm thu bản preview

### Nội dung và cảm xúc

- [ ] Người xem hiểu truyền lửa là truyền tri thức và thấy rõ người trao vẫn giữ lửa.
- [ ] Câu chuyện có sử dụng lửa, cộng đồng, ngôn ngữ/ký hiệu, canh tác, động cơ hơi nước, bóng đèn, máy tính và AI.
- [ ] Mỗi bước tiến có con người học hỏi, trao đổi hoặc bổ sung; AI chỉ là hình ảnh về một bước tiến, không có đoạn PR hoặc demo tính năng AI của Flama.
- [ ] Đoạn lịch sử nối tự nhiên vào Flama; người xem hiểu Flama làm gì ở cảnh cộng đồng.
- [ ] Có cảm giác một hành trình nối liền, không phải slideshow icon hoặc video rồi đến bảng tính năng.
- [ ] Logo, sắc cam/đỏ/hổ phách và tinh thần chia sẻ hiện diện xuyên suốt.

### Trải nghiệm và khả năng truy cập

- [ ] Cuộn nhanh/ngược và resize không làm mất cảnh, lệch chữ hay chờ animation phát hết.
- [ ] Có thể đi ngay đến đoạn Flama; CTA cuối đứng ổn định và các link đi đúng đích.
- [ ] Mobile 320px, 390px, tablet và desktop đều đọc được đầy đủ, không tràn ngang.
- [ ] Keyboard, focus, reduced motion và nút tắt chuyển động đều dùng được; static mode kể đủ câu chuyện.
- [ ] Preview xem được khi đăng nhập và chưa đăng nhập; không tự redirect người review.
- [ ] Thoát route không để listener/loop/style/metadata tác động trang khác.

### Tách biệt và kiểm tra kỹ thuật

- [ ] `/` và landing hiện tại không bị thay đổi trong giai đoạn preview; global brand/style không bị sửa theo story.
- [ ] Khi triển khai, chạy `npm run lint` và `npm run build` trong `frontend/`; chỉ chạy test module liên quan khi thay đổi chạm behavior có test.
- [ ] Kiểm tra navigation trực tiếp/reload route preview qua Vite và bản build do Flask phục vụ; không cần đổi startup/schema để có màn review.
- [ ] Kiểm tra thực tế animation, chuyển cảnh, tương phản và hiệu năng; các mục chưa kiểm chứng được ghi rõ trong kết quả review.
- [ ] Mọi phiên Chrome dùng để test/profiling phải có profile riêng qua `--user-data-dir`, theo `AGENTS.md`.
- [ ] Chưa có thay thế landing chính hoặc triển khai production khi chưa được duyệt rõ ràng.

## 12. Nguồn tham chiếu trong repository

- [Landing đang dùng](../../../frontend/src/pages/LandingPage.tsx).
- [Router thực tế](../../../frontend/src/App.tsx) và [layout thực tế](../../../frontend/src/layouts/AppLayout.tsx).
- [Brand](../../../frontend/src/shared/components/Brand.tsx), [logo hiện tại](../../../frontend/public/logo.png), [SVG lửa](../../../frontend/public/flama-mark.svg).
- [Design tokens](../../../frontend/src/index.css), [design guide](../../../DESIGN.md), [dependencies và lệnh kiểm tra](../../../frontend/package.json).
- [Hướng dẫn kiến trúc frontend](../../../frontend/docs/COMPONENT_ARCHITECTURE.md), đối chiếu lại đường dẫn bằng code vì một số mô tả cấu trúc đã cũ.
- [SPA delivery](../../../app/spa.py) và [repo guardrails](../../../AGENTS.md).

Tài liệu này ghi nhận hướng thiết kế và phạm vi triển khai tiếp theo. Chưa có asset story, route preview hoặc kết quả kiểm thử giao diện được tạo trong lượt viết tài liệu.
