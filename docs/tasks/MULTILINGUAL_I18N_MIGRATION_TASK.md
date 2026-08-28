# Task: Migrate Flama to a multilingual application (i18n)

## Goal

Chuyển Flama từ trạng thái UI/text đang phụ thuộc hoặc hard-code theo một ngôn ngữ, đặc biệt là tiếng Nhật, sang kiến trúc **đa ngôn ngữ (internationalization/i18n)** có thể mở rộng lâu dài.

Mục tiêu không phải chỉ thay một số chuỗi tiếng Nhật bằng tiếng Anh, mà phải loại bỏ việc hard-code ngôn ngữ trong application UI và tạo một cơ chế chung để Flama có thể hỗ trợ nhiều locale.

Các ngôn ngữ ban đầu nên có khả năng hỗ trợ ít nhất:

- Japanese (`ja`)
- English (`en`)
- Vietnamese (`vi`)

Không bắt buộc phải dịch hoàn chỉnh toàn bộ ba ngôn ngữ trong một lần nếu scope quá lớn. Ưu tiên xây nền tảng i18n đúng trước, sau đó migrate UI theo từng phần nhỏ.

## Current problem to investigate

Rà soát toàn bộ frontend và các phần backend có text hiển thị cho người dùng để xác định:

- chuỗi UI đang hard-code bằng tiếng Nhật;
- chuỗi UI đang hard-code bằng tiếng Anh hoặc ngôn ngữ khác;
- label, button, dialog, validation message, empty state, notification/toast, error message và navigation text chưa đi qua lớp translation;
- logic đang ngầm giả định locale Nhật;
- format ngày giờ, số, timezone hoặc các giá trị khác đang gắn cứng theo locale;
- text do backend trả về nhưng được frontend hiển thị trực tiếp;
- các khu vực có thể bị bỏ sót như auth, settings, study, deck/note management, marketplace, billing, admin và error pages.

Không chỉ search một vài literal tiếng Nhật. Cần xác định **boundary nào chịu trách nhiệm cho localization** và tránh để frontend/backend mỗi nơi tự xử lý theo cách riêng.

## Target behavior

Sau khi hoàn thành migration, kiến trúc mong muốn nên gần với:

```text
User
  ↓
selected/preferred locale
  ↓
i18n layer
  ↓
translation resource
  ├── ja
  ├── en
  └── vi
  ↓
React UI
```

Application code không nên chứa trực tiếp text phụ thuộc ngôn ngữ khi text đó là UI copy.

Ví dụ, tránh:

```tsx
<Button>保存</Button>
```

và chuyển sang một abstraction tương đương:

```tsx
<Button>{t("common.save")}</Button>
```

Tên key và thư viện cụ thể cần được lựa chọn dựa trên kiến trúc frontend hiện tại; không bắt buộc dùng chính ví dụ trên.

## Requirements

### 1. Establish an i18n foundation

Chọn và tích hợp một giải pháp i18n phù hợp với React/Vite hiện tại.

Giải pháp phải hỗ trợ tối thiểu:

- locale resources tách khỏi component;
- language switching;
- fallback locale;
- interpolation;
- pluralization khi cần;
- lazy loading hoặc cách tổ chức resource không làm bundle khó quản lý;
- format date/time/number theo locale khi phù hợp.

### 2. Locale resolution

Xác định rõ thứ tự chọn locale, ví dụ:

```text
explicit user preference
        ↓
previous locally persisted preference
        ↓
browser language
        ↓
default locale
```

Nếu user đã đăng nhập và Flama có nơi phù hợp để lưu preference, nghiên cứu việc lưu locale theo user thay vì chỉ phụ thuộc local browser state.

Locale không hợp lệ phải fallback an toàn, không làm crash application.

### 3. Language selector

Bổ sung cách để user đổi ngôn ngữ trong UI ở vị trí phù hợp, ưu tiên Settings hoặc application shell.

Việc đổi locale cần có hiệu lực nhất quán trên toàn application và được giữ lại cho lần truy cập sau.

### 4. Remove hard-coded UI language

Migrate text UI sang translation resources.

Không yêu cầu migrate toàn bộ application trong một commit lớn. Hãy chia theo feature/module hoặc nhóm component để các thay đổi có thể review và test độc lập.

Ví dụ:

```text
i18n foundation
  ↓
app shell/navigation
  ↓
auth
  ↓
decks/flashcards
  ↓
study
  ↓
settings
  ↓
marketplace/billing/admin
```

Agent phải tự xác định thứ tự phù hợp dựa trên code hiện tại.

### 5. Backend/API boundary

Rà soát các API response đang trả message dạng human-readable và frontend hiển thị trực tiếp.

Ưu tiên để API trả về **stable error/status code** và frontend quyết định text theo locale khi đó là UI-facing message.

Không cần ép toàn bộ backend phải trở thành hệ thống translation riêng nếu không có lý do rõ ràng.

Ví dụ kiến trúc mong muốn:

```json
{
  "code": "DECK_NOT_FOUND"
}
```

thay vì frontend phụ thuộc hoàn toàn vào một message cố định như:

```json
{
  "message": "デッキが見つかりません"
}
```

Các thay đổi API phải cân nhắc backward compatibility.

### 6. Do not localize user content

Phân biệt rõ:

```text
application UI text  → localized
user-created content → giữ nguyên
learning content     → giữ nguyên theo dữ liệu
```

Không được tự động dịch deck name, note content, flashcard field hoặc nội dung học do user tạo chỉ vì application locale thay đổi.

### 7. Testing

Bổ sung regression coverage cho các hành vi quan trọng:

- default locale hoạt động;
- đổi locale hoạt động;
- preference được persist;
- unsupported locale fallback đúng;
- missing translation key không làm UI hỏng;
- ít nhất các shared/common UI quan trọng render đúng ở các locale được hỗ trợ;
- date/number formatting không bị hard-code theo Nhật nếu locale khác được chọn.

Khi migrate từng feature, cập nhật test liên quan thay vì đợi tới cuối migration.

## Delivery strategy

Đây là task lớn và **không nên thực hiện trong một commit hoặc một branch khổng lồ**.

Trước khi code, hãy audit hiện trạng và chia task thành các phần nhỏ có thể merge độc lập.

Một hướng chia hợp lý có thể là:

```text
Part 1: audit + i18n architecture decision
Part 2: i18n runtime/foundation
Part 3: locale preference + language selector
Part 4+: migrate từng feature khỏi hard-coded strings
Final: cleanup + regression coverage
```

Thứ tự thực tế có thể thay đổi nếu code hiện tại cho thấy boundary khác hợp lý hơn.

Mỗi phần phải:

- có scope rõ ràng;
- tránh refactor không liên quan;
- có test phù hợp;
- cập nhật docs/checkpoint nếu task chưa hoàn thành;
- tuân theo branch strategy chung của repository.

## Acceptance criteria

Task được coi là hoàn thành khi:

- Flama có một i18n architecture chung và có tài liệu đủ để mở rộng;
- UI không còn phụ thuộc vào việc hard-code tiếng Nhật làm ngôn ngữ duy nhất;
- user có thể chọn locale được hỗ trợ;
- locale được resolve và persist nhất quán;
- shared UI và các feature chính đã dùng translation resources thay vì literal language-specific strings;
- unsupported/missing locale có fallback rõ ràng;
- user-generated và learning content không bị dịch nhầm;
- test regression cho i18n path quan trọng đã có;
- có thể thêm một ngôn ngữ mới chủ yếu bằng cách thêm translation resource, không phải sửa hàng loạt component business logic.

## Non-goals

Task này không yêu cầu:

- machine-translate toàn bộ learning content;
- dịch deck/note của user;
- xây translation management platform riêng;
- đưa tất cả ngôn ngữ trên thế giới vào ngay từ đầu;
- rewrite frontend chỉ để làm i18n.

Mục tiêu chính là làm cho **ngôn ngữ trở thành một concern có abstraction rõ ràng**, thay vì tiếp tục gắn cứng tiếng Nhật trong application code.
