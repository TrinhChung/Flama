# Task: Thiết kế onboarding người dùng mới — auto session, khảo sát sở thích, gợi ý Deck và Dashboard Tour

> **Trạng thái:** [x] ĐÃ HOÀN THÀNH (Completed)  
> **Ngày hoàn thành:** 2026-08-30  
> **Target branch:** `develop`  
> **Commits:** `12a8db2`, `d28b078`

## Mục tiêu

Thiết kế lại toàn bộ luồng **người dùng mới sau khi đăng ký tài khoản** để giảm ma sát, giúp người dùng nhìn thấy giá trị của Flama ngay trong phiên đầu tiên và hiểu cách sử dụng Dashboard.

Luồng mục tiêu:

```text
Đăng ký tài khoản
    ↓
Tạo session đăng nhập ngay
    ↓
Onboarding / khảo sát nhanh nhu cầu học tập
    ↓
Lưu Learning Profile / Personalization Profile
    ↓
Đi đến Marketplace Deck đã được filter/recommend theo nhu cầu
    ↓
Người dùng xem / cài Deck phù hợp hoặc bỏ qua
    ↓
Đi đến Dashboard
    ↓
Dashboard Tour
    ↓
Menu / Navigation Tour
    ↓
Hoàn tất onboarding
```

Không yêu cầu người dùng sau khi đăng ký phải quay lại `/login` và nhập lại email/password.

---

## Bối cảnh hiện tại cần kiểm tra

Hiện frontend registration đang có flow đại loại:

```text
register success
→ toast
→ navigate('/login')
```

Cần thay đổi flow này ở cả backend và frontend để registration success tạo ra **authenticated session hợp lệ**, không chỉ thay redirect ở frontend.

Dashboard hiện đã có empty-state onboarding khi tài khoản chưa có Deck. Cần nghiên cứu cách tái sử dụng hoặc thay thế phần này để onboarding mới thống nhất, thay vì tồn tại nhiều onboarding rời rạc.

Sidebar hiện có nhiều nhóm chức năng như:

- Học tập
- Học liệu
- Nhập & Đồng bộ
- Phần mở rộng
- Cài đặt
- Admin đối với tài khoản có quyền

Dashboard/menu tour phải bám theo navigation thực tế và quyền của user, không hard-code một danh sách khác dễ bị lỗi thời.

---

# 1. Đăng ký xong phải có session ngay

## Yêu cầu

Sau khi backend tạo user thành công:

- tạo authenticated session theo cùng cơ chế an toàn đang dùng ở login;
- trả về trạng thái user hiện tại và các dữ liệu frontend cần bootstrap;
- frontend cập nhật auth state/cache;
- redirect thẳng sang onboarding;
- không bắt user đăng nhập lại.

Ví dụ:

```text
POST /register
    ↓
create user
    ↓
create/login session
    ↓
return authenticated user
    ↓
/onboarding
```

Không được implement kiểu frontend tự giả định đã login trong khi backend chưa tạo session.

## Security investigation

Cần kiểm tra:

- login hiện tạo session/cookie ở đâu;
- CSRF/session rotation;
- remember-me nếu có;
- login rate limit;
- email verification nếu hệ thống đang hoặc sẽ hỗ trợ;
- OAuth registration/login;
- session fixation protection.

Nếu có email verification, cần tách rõ:

```text
Authenticated account
!=
Verified email
```

Có thể cho user có session ngay nhưng giới hạn các action yêu cầu verified email nếu policy của Flama cần như vậy.

OAuth signup cũng phải đi cùng onboarding nếu đây là user mới, không được chỉ áp dụng cho email/password registration.

---

# 2. Tạo New User Onboarding riêng

Nghiên cứu route phù hợp, ví dụ:

```text
/onboarding
/onboarding/interests
/onboarding/goals
/onboarding/decks
```

Không bắt buộc chia thành nhiều URL nếu wizard một trang hợp lý hơn.

Onboarding phải:

- nhanh;
- ít câu hỏi;
- có progress rõ;
- mobile friendly;
- cho phép Back;
- cho phép Skip ở các phần không bắt buộc;
- không biến thành một form hồ sơ dài;
- không hỏi những dữ liệu chưa có mục đích sử dụng rõ ràng.

Mục tiêu chính là có đủ tín hiệu để **cá nhân hóa Deck discovery**, không phải thu thập càng nhiều dữ liệu càng tốt.

---

# 3. Nghiên cứu Learning Profile / Personalization Profile

Cần nghiên cứu chi tiết cấu trúc dữ liệu phù hợp với Flama trước khi code.

Tham khảo pattern onboarding/personalization của các sản phẩm học tập, content discovery và marketplace như:

- Duolingo;
- Quizlet;
- Coursera;
- Khan Academy;
- Anki ecosystem;
- YouTube/Spotify/Netflix ở góc nhìn chọn sở thích ban đầu;
- các learning marketplace khác nếu phù hợp.

Không copy UI. Mục tiêu là xác định **những tín hiệu nào thực sự giúp Flama lọc và recommend Deck tốt hơn**.

## Các nhóm dữ liệu cần nghiên cứu

### 3.1. Lĩnh vực quan tâm

Cho phép multi-select.

Ví dụ:

- Tiếng Nhật
- Tiếng Anh
- Tiếng Hàn
- Ngoại ngữ khác
- JLPT
- TOEIC
- IELTS
- Kanji
- Từ vựng
- Ngữ pháp
- IT / lập trình
- AWS / Cloud
- Kinh doanh
- Kiến thức phổ thông
- lĩnh vực khác dựa trên taxonomy thực tế của Marketplace

**Không hard-code một taxonomy onboarding tách biệt với taxonomy Deck hiện tại.**

Cần nghiên cứu mapping trực tiếp tới hệ thống taxonomy/category/tag hiện có để sau này admin thêm category mới thì recommendation có thể mở rộng.

### 3.2. Nội dung / loại kiến thức muốn học

Ví dụ:

- từ vựng;
- Kanji;
- ngữ pháp;
- thuật ngữ chuyên ngành;
- câu hỏi / đáp án;
- luyện thi;
- kiến thức ghi nhớ dài hạn.

Chỉ hỏi nếu dữ liệu này có thể map được với Deck metadata.

### 3.3. Trình độ hiện tại

Ví dụ theo từng domain phù hợp:

```text
Mới bắt đầu
Sơ cấp
Trung cấp
Nâng cao
```

Hoặc với Japanese:

```text
Chưa học
N5
N4
N3
N2
N1
Trên N1
```

Với English có thể dùng framework khác nếu taxonomy hiện tại hỗ trợ.

Không ép toàn bộ lĩnh vực vào một thang level chung nếu điều đó làm dữ liệu sai nghĩa.

### 3.4. Trình độ / mục tiêu hướng tới

Ví dụ:

```text
Hiện tại: JLPT N3
Mục tiêu: JLPT N2
```

hoặc:

```text
Hiện tại: TOEIC 550
Mục tiêu: TOEIC 800
```

Mục tiêu này có thể là tín hiệu recommendation mạnh hơn sở thích chung.

### 3.5. Mục đích học

Nghiên cứu xem có giá trị hay không với recommendation:

- thi chứng chỉ;
- học ở trường;
- phục vụ công việc;
- giao tiếp;
- sinh sống ở nước ngoài;
- mở rộng kiến thức;
- tự tạo học liệu / creator.

Không bắt buộc hỏi nếu chưa dùng được trong ranking.

### 3.6. Ngôn ngữ giải thích mong muốn

Nếu Deck có metadata phù hợp, có thể hỏi:

- tiếng Việt;
- tiếng Nhật;
- tiếng Anh;
- song ngữ.

Ví dụ user học tiếng Nhật nhưng muốn nghĩa tiếng Việt thì ưu tiên Deck JP-VI thay vì JP-JP.

Chỉ triển khai khi marketplace metadata đủ tin cậy để filter.

### 3.7. Learning cadence — research only

Có thể nghiên cứu thêm:

- số phút muốn học mỗi ngày;
- số ngày/tuần;
- deadline kỳ thi.

Nhưng **không đưa vào phase đầu nếu chỉ dùng để trang trí**.

Nếu thu thập thì phải có use case thực tế như:

- reminder;
- study plan;
- target progress;
- recommended workload.

---

# 4. Thiết kế dữ liệu Personalization riêng, không nhét tùy tiện vào User

Cần nghiên cứu model/schema phù hợp.

Một hướng tham khảo:

```text
User
└── LearningPreference / PersonalizationProfile
    ├── interests[]
    ├── learning_domains[]
    ├── current_levels[]
    ├── target_levels[]
    ├── goals[]
    ├── preferred_explanation_languages[]
    ├── onboarding_status
    ├── onboarding_version
    ├── completed_at
    └── updated_at
```

Không bắt buộc dùng schema trên.

Các lựa chọn taxonomy nên tham chiếu ID/entity hiện có nếu có thể, thay vì lưu string tự do không đồng bộ.

Cần hỗ trợ user thay đổi sở thích sau này trong Settings/Profile/Personalization.

Onboarding không phải nguồn dữ liệu bất biến.

---

# 5. Onboarding state phải có version và resumable

Không chỉ lưu một boolean `is_onboarded`.

Nghiên cứu state như:

```text
NOT_STARTED
IN_PROGRESS
PERSONALIZED
DECK_DISCOVERY
TOUR_PENDING
COMPLETED
SKIPPED
```

Có thể đơn giản hơn nếu phù hợp.

Cần lưu tối thiểu:

- onboarding version;
- current/completed step;
- completed_at;
- skipped state nếu có.

Mục tiêu:

- reload browser không mất tiến trình;
- logout/login lại có thể resume;
- sau này Flama thay onboarding version có thể biết user nào đã xem version nào;
- không tự chạy lại tour mỗi lần vào dashboard.

---

# 6. Sau khảo sát → Deck Discovery được cá nhân hóa

Sau khi user hoàn thành phần preferences, chuyển sang màn Marketplace Deck với filter/recommendation đã áp dụng.

Ví dụ:

```text
Japanese + JLPT
Current: N3
Target: N2
Vocabulary + Grammar
Vietnamese explanation

→ Marketplace
   - Japanese
   - JLPT N2
   - Vocabulary / Grammar
   - JP-VI ưu tiên
```

Không nhất thiết tất cả điều kiện đều là hard filter.

Cần nghiên cứu tách:

### Hard filter

Điều kiện không nên vi phạm, ví dụ:

- language/domain;
- user explicitly chọn category;
- content compatibility khi chắc chắn.

### Soft ranking / recommendation signal

Dùng để ưu tiên nhưng không loại hoàn toàn:

- target level;
- popularity;
- rating;
- quality/verified status;
- số lượt install;
- freshness;
- creator reputation nếu sau này có;
- mức độ khớp với nhiều interests.

Không tạo một recommendation engine phức tạp ngay phase đầu nếu metadata hiện tại chưa đủ.

Phase đầu có thể là deterministic filtering + scoring rõ ràng và test được.

---

# 7. UX ở màn Deck Recommendation / Marketplace

Màn này phải cho user hiểu vì sao đang thấy các Deck đó.

Ví dụ header:

```text
Deck phù hợp với mục tiêu của bạn
JLPT N2 · Từ vựng · Ngữ pháp
```

Có thể có chips/filter để user thay đổi ngay.

Yêu cầu:

- cho phép bỏ filter;
- cho phép xem toàn bộ Marketplace;
- không khóa user trong recommendation;
- có thể chỉnh lại sở thích;
- Deck card dùng component Marketplace hiện có, không tạo card onboarding riêng nếu không cần;
- tránh auto-install nhiều Deck mà user chưa chọn.

## Hành động chính

Nghiên cứu CTA phù hợp:

```text
[Cài Deck]
[Xem chi tiết]
[Tiếp tục tới Dashboard]
```

Nếu user chưa cài Deck nào, có thể khuyến khích chọn ít nhất một Deck nhưng vẫn cho phép Skip.

Không bắt user phải chọn Deck mới được dùng Flama.

---

# 8. Khi nào chuyển sang Dashboard

Sau một trong các trường hợp:

- user cài thành công ít nhất một Deck và chọn tiếp tục;
- user đã có Deck từ flow khác;
- user chủ động Skip recommendation;
- không tìm thấy Deck phù hợp.

Sau đó:

```text
/dashboard
```

và bắt đầu Dashboard Tour nếu user chưa hoàn thành tour version hiện tại.

Nếu không có Deck, Dashboard empty state phải vẫn hợp lý và dẫn user quay lại Marketplace.

---

# 9. Dashboard Tour

Tạo product tour để giải thích nhanh cấu trúc Dashboard.

Không làm tour 15–20 bước bắt user đọc quá nhiều.

Mục tiêu chỉ giải thích các điểm người mới cần để bắt đầu học.

## Các bước nên nghiên cứu

### Step 1 — Dashboard / Deck list

Giải thích đây là nơi quản lý các Deck đã cài/tạo.

### Step 2 — Chọn Deck

Cho user biết cần chọn Deck để thao tác/học.

### Step 3 — Study

Giải thích nút bắt đầu học Deck đã chọn.

### Step 4 — Stats

Giải thích nơi xem tiến độ/thống kê.

### Step 5 — Browse

Giải thích cách duyệt/search card trong Deck.

### Step 6 — Create Deck / Import nếu phù hợp

Không cần nhấn mạnh cho user chỉ muốn học. Có thể đưa vào tour nâng cao hoặc menu tour.

### Step 7 — Study heatmap/activity

Chỉ đưa vào tour nếu có giá trị rõ ràng với người mới.

Tour cần spotlight đúng DOM element và có:

- Next;
- Back;
- Skip;
- Finish.

Không chặn toàn bộ UI nếu user muốn thoát tour.

---

# 10. Navigation / Sidebar Menu Tour

Sau phần Dashboard chính, hướng dẫn ngắn về cấu trúc menu.

Sidebar hiện chia theo nhóm nên tour nên giải thích **nhóm chức năng**, không nhất thiết highlight từng menu item một nếu quá dài.

Ví dụ:

### Học tập

- Tổng quan;
- Thống kê;
- Duyệt thẻ.

### Học liệu

- Loại thẻ;
- Deck đã cài;
- Kho shared deck / Marketplace;
- Kho note type;
- Đăng học liệu.

### Nhập & Đồng bộ

- Anki sync;
- CSV/TSV import.

### Phần mở rộng

- audio;
- Yomitan;
- MCP;
- các integration khác.

### Cài đặt

- profile;
- wallet nếu đã tách theo task khác;
- orders;
- feedback;
- personalization nếu thêm mới.

Không đưa menu Admin vào tour của user bình thường.

Tour phải đọc navigation thực tế hoặc sử dụng cùng một source/config để tránh tình trạng menu đổi nhưng tour không đổi.

---

# 11. Tour phải adaptive theo desktop/mobile và permission

Không được assume mọi element luôn tồn tại.

Ví dụ hiện Dashboard có button/action bị ẩn hoặc khác nhau giữa desktop/mobile.

Tour engine cần:

- skip step nếu target không render;
- hỗ trợ sidebar collapsed;
- tự mở sidebar trên mobile nếu cần;
- không crash khi component chưa mount;
- không highlight element của feature user không có quyền;
- không tour Admin menu cho non-admin;
- xử lý route transition nếu tour có nhiều route.

Nghiên cứu thư viện tour phù hợp với React hiện tại, ví dụ driver.js, react-joyride hoặc giải pháp khác.

Không chọn library chỉ vì phổ biến; cần kiểm tra:

- React compatibility;
- accessibility;
- mobile;
- dynamic target;
- controlled state;
- bundle size;
- maintenance status;
- khả năng custom theo design system Flama.

---

# 12. Cho phép chạy lại Tour

User phải có cách mở lại hướng dẫn sau này.

Nghiên cứu đặt tại:

```text
Help / Hướng dẫn
→ Tour Dashboard
→ Tour Menu
```

hoặc trong `/guide` theo hệ thống Guide đã được lên task.

Không được thiết kế tour thành thứ chỉ có thể xem đúng một lần.

Có thể có action:

```text
Xem lại hướng dẫn Dashboard
```

---

# 13. Liên kết với hệ thống `/guide`

Tour chỉ giải thích nhanh **“cái gì nằm ở đâu”**.

Không nhét tài liệu dài vào tooltip.

Nếu user cần hướng dẫn chi tiết, tour hoặc menu có thể dẫn sang `/guide/...` tương ứng.

Ví dụ:

```text
Tour: Đồng bộ Anki nằm ở đây
→ "Tìm hiểu thêm"
→ /guide/anki-sync
```

Điều này phải tương thích với task Information Architecture cho Guide đã có.

---

# 14. Recommendation không được phụ thuộc hoàn toàn vào onboarding

Learning Profile chỉ là tín hiệu ban đầu.

Sau này có thể nghiên cứu thêm signal thực tế:

- Deck user đã cài;
- Deck user thường học;
- search history;
- category thường xem;
- level progression;
- ratings/saves;
- explicit follow/favorite.

Nhưng phase hiện tại chỉ cần chuẩn bị architecture để onboarding preference không trở thành một hệ thống dead-end.

Không triển khai tracking hành vi vượt quá mục đích nếu chưa có policy/privacy rõ ràng.

---

# 15. Empty recommendation / fallback

Phải xử lý khi không có Deck khớp chính xác.

Fallback ví dụ:

```text
Exact target level
    ↓ none
Same domain + nearby level
    ↓ none
Same domain + popular/high-quality
    ↓ none
Marketplace trending / recently curated
```

Không để màn trống chỉ vì filter quá chặt.

UI phải nói rõ recommendation đang được mở rộng.

---

# 16. Analytics cho onboarding funnel

Cần instrument để biết onboarding có thực sự giúp user hay chỉ làm tăng drop-off.

Tối thiểu nghiên cứu các event:

```text
registration_completed
onboarding_started
onboarding_interest_selected
onboarding_preferences_completed
onboarding_skipped
deck_recommendation_viewed
recommended_deck_detail_opened
recommended_deck_installed
deck_discovery_skipped
dashboard_first_view
dashboard_tour_started
dashboard_tour_skipped
dashboard_tour_completed
navigation_tour_completed
```

Không log dữ liệu nhạy cảm không cần thiết.

Các metric nên xem:

- registration → onboarding completion rate;
- onboarding → first deck install rate;
- time to first deck install;
- time to first study session;
- tour completion/skip rate;
- D1/D7 activation nếu analytics hiện tại hỗ trợ.

Mục tiêu cuối không phải “user hoàn thành form”, mà là:

> user có Deck phù hợp và bắt đầu học nhanh hơn.

---

# 17. Definition of activation

Cần thống nhất một activation event cho user mới.

Nghiên cứu một trong các định nghĩa:

```text
Installed first deck
```

hoặc tốt hơn:

```text
Completed first study/review session
```

Onboarding funnel nên được tối ưu hướng tới activation này.

Không dùng `onboarding_completed` làm metric sản phẩm duy nhất.

---

# 18. API / Backend investigation

Trước khi triển khai cần kiểm tra:

- registration API hiện tại;
- login/session service;
- bootstrap endpoint;
- OAuth login flow;
- User model;
- profile/settings model;
- taxonomy/category/tag model;
- marketplace deck metadata;
- difficulty/level metadata;
- language metadata;
- marketplace filtering/search API;
- deck install API;
- analytics/event system;
- existing Redis/job system nếu recommendation cần async sau này.

Sau đó xác định rõ:

- field/model mới;
- migration;
- API onboarding/preferences;
- API recommendation hoặc reuse marketplace search;
- frontend route;
- auth redirect rules;
- tour state storage.

---

# 19. Frontend architecture

Nghiên cứu tách component/feature rõ ràng, ví dụ:

```text
features/onboarding/
    api
    types
    hooks
    pages
    components
    tour
```

Không nhét toàn bộ wizard + recommendation + tour vào `RegisterPage` hoặc `DashboardPage`.

Dashboard chỉ nên expose stable tour anchors/data attributes khi cần.

Ví dụ:

```html
data-tour="dashboard-decks"
data-tour="dashboard-study"
data-tour="dashboard-stats"
```

Không dựa vào fragile CSS selector như `div:nth-child(...)`.

---

# 20. UX rules

- Không hỏi lại thông tin user vừa cung cấp lúc signup.
- Tổng onboarding ban đầu nên ngắn, ưu tiên 2–4 bước có giá trị cao.
- Multi-select thay vì form text khi taxonomy đã có.
- Có progress indicator.
- Có Skip nhưng không làm Skip trở thành CTA chính.
- Sau khi chọn preference phải thấy lợi ích ngay qua recommendation.
- Không auto-subscribe/auto-install content ngoài ý muốn.
- User có thể chỉnh personalization về sau.
- Tour có thể Skip và chạy lại.
- Không bắt user hoàn thành toàn bộ tour mới được sử dụng app.
- Responsive desktop/mobile.
- Accessibility: focus management, keyboard navigation, screen-reader labels cho wizard/tour.

---

# 21. Luồng đề xuất để prototype

```text
1. Register
   ↓
2. Session được tạo ngay
   ↓
3. "Bạn muốn học gì?"
   [Tiếng Nhật] [Tiếng Anh] [IT] [...]
   ↓
4. Câu hỏi context theo domain
   Japanese example:
   Current: N3
   Goal: N2
   Focus: Vocabulary + Grammar
   Explanation: Vietnamese
   ↓
5. "Deck phù hợp với bạn"
   Marketplace list đã filter/rank
   ↓
6. User install 1+ deck hoặc Skip
   ↓
7. Dashboard
   ↓
8. Tour Deck → Study → Stats
   ↓
9. Tour nhanh các nhóm Sidebar
   ↓
10. Finish
```

Đây chỉ là prototype direction. Trước khi code phải đối chiếu taxonomy và metadata thật của Flama.

---

# 22. Deliverables

- Sửa registration để tạo authenticated session ngay.
- Điều hướng new user sang onboarding thay vì `/login`.
- Onboarding state/version.
- Learning/Personalization Profile schema.
- API đọc/cập nhật preferences.
- UI khảo sát sở thích, domain, level hiện tại, target level và các trường thực sự cần thiết.
- Mapping preferences với taxonomy/metadata Marketplace.
- Deck discovery/recommendation màn đầu tiên.
- Fallback khi recommendation không có kết quả.
- Cho phép user sửa filter và browse toàn Marketplace.
- Điều hướng Dashboard sau install/skip.
- Dashboard Tour.
- Sidebar/Navigation Tour.
- Adaptive desktop/mobile/permission.
- Skip/resume/replay tour.
- Liên kết tới `/guide` khi cần hướng dẫn sâu.
- Analytics onboarding funnel.
- Tests backend/frontend cho các flow chính.
- Tài liệu ngắn giải thích recommendation rule phase đầu.

---

# 23. Acceptance criteria

- [x] Đăng ký thành công không còn bắt người dùng đăng nhập lại.
- [x] Sau registration, request authenticated tiếp theo nhận đúng user/session.
- [x] User mới được đưa vào onboarding đúng một lần theo onboarding version/state.
- [x] OAuth-created new user cũng đi qua onboarding tương ứng.
- [x] User có thể chọn nhiều lĩnh vực quan tâm.
- [x] Có thể lưu current level và target level theo domain khi phù hợp.
- [x] Preference sử dụng taxonomy/metadata có nguồn rõ ràng, không tạo hệ category song song không cần thiết.
- [x] Sau onboarding, Marketplace hiển thị Deck được filter/rank dựa trên preference.
- [x] User có thể bỏ filter hoặc xem toàn bộ Marketplace.
- [x] User có thể cài Deck từ recommendation flow.
- [x] User có thể Skip mà không bị khóa khỏi Flama.
- [x] Sau bước Deck discovery, user được dẫn tới Dashboard.
- [x] Dashboard tour giải thích tối thiểu Deck list, Study, Stats và navigation chính.
- [x] Tour không crash nếu target element không tồn tại hoặc bị ẩn trên mobile.
- [x] Tour không hiển thị chức năng user không có permission.
- [x] User có thể Skip tour.
- [x] User có thể chạy lại tour từ Help/Guide/Settings phù hợp.
- [x] Refresh/login lại giữa onboarding có thể resume hợp lý.
- [x] Onboarding không tự bật lại mỗi lần vào Dashboard sau khi đã completed/skipped.
- [x] Có analytics để đo registration → first deck install → first study activation.
- [x] Có test cho session-after-register, onboarding state, preference persistence, recommendation mapping và tour completion state.

---

# 24. Không làm trong task này nếu chưa có dependency

- AI recommendation phức tạp;
- machine-learning recommender;
- tự động tạo study plan dài hạn;
- notification/reminder engine mới;
- behavioral profiling diện rộng;
- auto-install Deck;
- badge/gamification onboarding;
- bắt user hoàn thành onboarding mới được sử dụng Flama.

Ưu tiên phase đầu: **ít ma sát → hiểu nhu cầu → đưa đúng Deck → user bắt đầu học → hiểu Dashboard**.
