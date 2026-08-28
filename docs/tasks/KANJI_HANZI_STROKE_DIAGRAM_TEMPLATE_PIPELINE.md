# Task: Kanji/Hanzi stroke diagram cho Card Template

## Mục tiêu

Bổ sung khả năng hiển thị **sơ đồ thứ tự nét (stroke-order diagram)** cho chữ Hán trong các Card Template của Flama, hỗ trợ tối thiểu:

- tiếng Nhật: Kanji
- tiếng Trung: Hanzi, bao gồm Simplified và Traditional khi nguồn dữ liệu hỗ trợ

Người tạo Note Type / Template không phải tự upload từng ảnh stroke. Template chỉ cần chọn một **field nguồn**, ví dụ `Expression`, `Word`, `Vocabulary`, sau đó backend sẽ:

1. đọc giá trị field;
2. tách các Kanji/Hanzi có trong chuỗi;
3. xác định bộ dữ liệu stroke phù hợp theo locale/ngôn ngữ;
4. resolve hoặc tạo SVG tương ứng;
5. trả về các media URL nội bộ của Flama;
6. renderer hiển thị các diagram trong card.

Ví dụ:

```text
Field: Expression
Value: 勉強する
Locale: ja

Backend extract:
[勉, 強]

Output render:
勉 -> /media/proxy/<asset-id-1>
強 -> /media/proxy/<asset-id-2>
```

```text
Field: Word
Value: 学习中文
Locale: zh-CN

Backend extract:
[学, 习, 中, 文]
```

Không xử lý kana, latin, số hoặc ký tự punctuation thành stroke diagram.

---

# 1. Research nguồn dữ liệu / thư viện

Trước khi implementation cần xác minh lần cuối license, coverage và chất lượng dữ liệu. Không đưa dependency vào production chỉ dựa trên demo.

## 1.1 Japanese Kanji: ưu tiên research KanjiVG

Nguồn tham khảo:

- https://kanjivg.tagaini.net/
- https://github.com/KanjiVG/kanjivg

KanjiVG cung cấp từng Kanji dưới dạng SVG và lưu stroke theo đúng thứ tự trong các SVG path.

Đặc điểm phù hợp với Flama:

- dữ liệu Japanese Kanji chuyên biệt;
- SVG vector có thể scale tùy kích thước;
- mỗi character có file dựa theo Unicode codepoint;
- có stroke number data;
- có decomposition/radical metadata có thể tận dụng về sau.

### License cần lưu ý

KanjiVG hiện công bố license **CC BY-SA 3.0**.

Do có điều kiện attribution/share-alike, trước khi đưa asset được derive từ KanjiVG vào Marketplace hoặc cho user export cần:

- xác định chính xác phạm vi attribution;
- ghi source/license metadata cho dataset;
- bổ sung license notice nếu cần;
- kiểm tra implications đối với SVG được Flama generate lại từ KanjiVG;
- không giả định rằng code của Flama phải cùng license, nhưng phải đánh giá riêng phần dữ liệu/derivative asset.

License review là acceptance criterion, không để đến sau implementation mới xử lý.

## 1.2 Chinese Hanzi: ưu tiên research Make Me a Hanzi / Hanzi Writer Data

Nguồn tham khảo:

- https://github.com/skishore/makemeahanzi
- https://github.com/chanind/hanzi-writer-data
- https://hanziwriter.org/

Make Me a Hanzi cung cấp stroke-order vector data cho hơn 9,000 simplified/traditional characters.

`hanzi-writer-data` đóng gói dữ liệu theo từng character thành JSON nên có thể thuận tiện hơn khi backend Flama cần lookup theo character.

Hanzi Writer bản thân là JS renderer/animation library. Phase 1 không bắt buộc phải dùng Hanzi Writer ở frontend nếu Flama chỉ cần static stroke-order diagram.

### License cần lưu ý

- Hanzi Writer source code: MIT.
- Character data của Hanzi Writer / Make Me a Hanzi: license riêng, chủ yếu dựa trên **Arphic Public License**.

Phải giữ rõ sự khác nhau giữa **license của library** và **license của data**.

## 1.3 Hanzi Writer cho Japanese không phải lựa chọn mặc định Phase 1

Có project `hanzi-writer-data-jp`, nhưng hiện mô tả Japanese data là experimental và có dependency/license từ animCJK + Make Me a Hanzi.

Không ưu tiên dùng nó thay KanjiVG cho Japanese nếu KanjiVG đáp ứng coverage/chất lượng tốt hơn.

Có thể giữ làm phương án fallback/research.

## 1.4 Recommendation ban đầu

Phase 1 nên research theo hướng:

```text
Japanese (ja)
    -> KanjiVG

Chinese Simplified (zh-CN)
    -> Make Me a Hanzi / hanzi-writer-data

Chinese Traditional (zh-TW / zh-HK)
    -> Make Me a Hanzi / hanzi-writer-data
       + xác minh coverage/variant thực tế
```

Không dùng cùng một stroke dataset cho mọi locale một cách mù quáng.

Một Unicode ideograph có thể có glyph/stroke convention khác giữa Nhật và Trung Quốc. Do đó **locale phải là input quan trọng của resolver**.

---

# 2. Không suy đoán Japanese/Chinese chỉ từ character

Ví dụ `直`, `骨`, `令` hoặc nhiều CJK ideograph khác có thể dùng ở nhiều locale.

Backend không được thấy một ký tự Han rồi tự kết luận:

```text
KanjiVG
```

hoặc:

```text
Chinese data
```

Resolver cần biết locale từ một trong các nguồn sau, theo thứ tự ưu tiên nghiên cứu:

1. option được Template chỉ định rõ;
2. language/locale của Note Type;
3. language metadata của Deck;
4. language metadata của field nếu hệ thống sau này hỗ trợ;
5. fallback cấu hình rõ ràng.

Nếu không xác định được locale, cần có behavior rõ, ví dụ không render hoặc dùng `auto` nhưng phải document limitations.

Không silently chọn Chinese hoặc Japanese data nếu điều đó có thể tạo stroke order sai.

---

# 3. Template UX

Người dùng không nên phải viết code backend hoặc URL SVG bằng tay.

Trong màn tạo/chỉnh sửa Card Template cần nghiên cứu một helper/component dạng:

```text
Stroke Diagram

Source field: Expression
Language: Japanese
Style: Progressive / Stroke Number / Basic
Size: Small / Medium / Large
```

Sau khi chọn, editor insert một directive/helper vào template.

Syntax cuối cùng cần phù hợp với template engine hiện tại và không phá Mustache/Chevron.

Một syntax candidate để thảo luận:

```text
{{flama:stroke-diagram field="Expression" locale="ja"}}
```

hoặc một representation structured khác.

Đây chỉ là candidate. Không implement parser theo syntax trên trước khi kiểm tra architecture hiện tại.

## Requirement quan trọng

Không biến helper này thành cơ chế chạy arbitrary backend function từ user-authored template.

Chỉ có các helper được allowlist, ví dụ:

```text
stroke-diagram
```

với schema parameter cố định.

---

# 4. Input của helper

Helper nhận ít nhất:

- `field`: tên field nguồn;
- `locale`: `ja`, `zh-CN`, `zh-TW`, ... hoặc cơ chế resolve locale;
- `style/mode`: optional;
- `size`: optional;
- `deduplicate`: optional.

Ví dụ conceptual API:

```python
render_stroke_diagrams(
    field_name="Expression",
    field_value="日本語を勉強する",
    locale="ja",
    mode="progressive",
)
```

Output logically:

```python
[
    {"char": "日", "asset_id": "...", "url": "/media/proxy/..."},
    {"char": "本", "asset_id": "...", "url": "/media/proxy/..."},
    {"char": "語", "asset_id": "...", "url": "/media/proxy/..."},
    {"char": "勉", "asset_id": "...", "url": "/media/proxy/..."},
    {"char": "強", "asset_id": "...", "url": "/media/proxy/..."},
]
```

Không trả external CDN URL trực tiếp vào card.

---

# 5. Backend: tách Kanji/Hanzi từ field

Tạo service/helper dùng chung, không copy regex vào nhiều route.

Ví dụ conceptual:

```text
CjkCharacterExtractor
StrokeDiagramService
StrokeDatasetProvider
StrokeAssetService
```

## 5.1 Normalize input

Field có thể chứa:

- plain text;
- HTML/richtext;
- ruby/furigana;
- whitespace;
- punctuation;
- mixed Japanese/English;
- Chinese + pinyin;
- line break.

Cần xác định canonical text extraction trước khi scan Unicode.

Không scan raw HTML tag rồi vô tình lấy character từ attribute/markup.

## 5.2 Unicode extraction

Không chỉ regex một range `\u4E00-\u9FFF` rồi coi là hoàn thành.

Cần research coverage phù hợp cho:

- CJK Unified Ideographs;
- CJK Extension blocks nếu dataset hỗ trợ;
- CJK Compatibility Ideographs;
- variation selectors/IVS nếu xuất hiện;
- surrogate/codepoint handling chính xác.

Chỉ return character mà selected dataset thực sự support.

Unsupported character không được làm fail cả card.

## 5.3 Preserve order

Default preserve thứ tự xuất hiện trong field.

Ví dụ:

```text
日本語日本
```

Có thể hỗ trợ:

```text
deduplicate=false
-> 日 本 語 日 本

deduplicate=true
-> 日 本 語
```

Default cần nghiên cứu theo UX. Với vocabulary card, deduplicate có thể hợp lý hơn để tránh diagram lặp lại.

## 5.4 Giới hạn số character

Không để user truyền một đoạn văn dài rồi backend render hàng trăm SVG trong một card.

Cần có hard limit configurable, ví dụ nghiên cứu mức 8-16 character/helper.

Nếu vượt limit:

- truncate có indicator; hoặc
- không render và báo preview warning.

Không gây timeout hoặc response size quá lớn.

---

# 6. Stroke Dataset Provider abstraction

Không viết logic trực tiếp kiểu:

```python
if locale == "ja": open("kanjivg/...")
```

rải khắp renderer.

Nên có abstraction:

```text
StrokeDatasetProvider
├── KanjiVGProvider
└── MakeMeAHanziProvider
```

Contract conceptual:

```python
supports(character, locale)
get_character(character, locale)
get_strokes(character, locale)
get_metadata(character, locale)
```

Metadata nên chứa tối thiểu:

```text
character
unicode_codepoint
locale
provider
provider_version
stroke_count
license/source
```

Mục tiêu là sau này có thể thay dataset hoặc thêm provider khác mà không đổi Card Template contract.

---

# 7. SVG strategy

User requirement ban đầu nghiêng về server dùng stroke data để tạo sẵn SVG. Đây cũng là hướng phù hợp với renderer hiện tại.

## 7.1 Không render raw third-party SVG trực tiếp nếu chưa sanitize

SVG là active document format và có thể chứa:

- script;
- event handler;
- external resource;
- `foreignObject`;
- link;
- CSS/url reference.

Ngay cả khi nguồn upstream tin cậy, Flama vẫn nên normalize/sanitize hoặc tự generate SVG từ stroke-path data.

## 7.2 Preferred architecture

```text
Dataset
   ↓
Stroke paths + order metadata
   ↓
Flama SVG generator
   ↓
Canonical safe SVG
   ↓
Managed Media Asset
   ↓
/media/proxy/<asset-id>
```

SVG generator chỉ emit một subset rất nhỏ, ví dụ:

```text
svg
g
path
line
text (nếu cần stroke number)
rect (grid/background)
```

Không emit script/event/external URL.

## 7.3 Diagram modes cần research

Tối thiểu nên xem xét:

### `basic`

Một character hoàn chỉnh + stroke numbers.

### `progressive`

Hiển thị progression:

```text
stroke 1
stroke 1-2
stroke 1-3
...
completed
```

Đây là dạng phù hợp nhất với khái niệm "stroke diagram" cho học tập.

### `grid`

Background kiểu ô vuông / cross guideline.

### Future: `animated`

Animation stroke order.

Phase 1 không bắt buộc animation nếu static SVG đáp ứng use case chính.

---

# 8. Pre-generate vs lazy generation

Cần benchmark và quyết định rõ.

## Option A - pre-generate toàn bộ

Build/deploy job generate SVG cho toàn bộ supported characters.

Ưu điểm:

- runtime rất nhanh;
- không phát sinh generation trong study request;
- dễ CDN/cache.

Nhược điểm:

- nhiều asset;
- deployment/data package lớn;
- cần regenerate khi version/style đổi.

## Option B - lazy generate + persistent cache

Lần đầu gặp character:

```text
resolve cache
-> miss
-> generate SVG
-> store asset
-> cache/index
-> return URL
```

Các lần sau reuse cùng asset.

Ưu điểm:

- chỉ generate character thực sự dùng;
- storage nhỏ hơn lúc đầu.

Nhược điểm:

- first-hit latency;
- concurrency race cần xử lý.

## Recommendation cần benchmark

Khả năng hợp lý cho Flama:

- import/index dataset khi deploy;
- generate SVG deterministic và rất nhanh trên backend;
- persistent cache theo key;
- pre-warm common Kanji/Hanzi nếu cần.

Không gọi Internet/CDN mỗi lần render card.

---

# 9. Cache key / deterministic asset

SVG phải deterministic để reuse giữa user/deck.

Ví dụ key:

```text
stroke:{provider}:{provider_version}:{locale}:{codepoint}:{mode}:{style_version}
```

Ví dụ:

```text
stroke:kanjivg:2026xxxx:ja:52C9:progressive:v1
```

Hai user có cùng `勉` không được tạo hai asset vật lý giống nhau.

Cần unique constraint hoặc distributed lock để tránh race khi nhiều request generate cùng character.

---

# 10. Storage / media integration

Không tạo một hệ thống serving file thứ hai nếu Media Asset hiện tại có thể dùng lại.

Stroke SVG nên được lưu/đăng ký vào media layer Flama với metadata như:

```text
kind: stroke_diagram
character: 勉
locale: ja
source: kanjivg
source_version: ...
mode: progressive
style_version: 1
content_type: image/svg+xml
```

Card template nhận:

```text
/media/proxy/<asset-id>
```

thay vì:

```text
https://third-party-cdn/.../勉.svg
```

Điều này giúp:

- renderer CSP tiếp tục chặt;
- không phụ thuộc third-party availability;
- cache/CDN của Flama kiểm soát được;
- có source/license metadata;
- export/migration dễ quản lý hơn.

---

# 11. Tương thích với Card Template Sandbox hiện tại

Kiến trúc renderer hiện tại chạy user-authored template trong sandbox iframe và CSP giới hạn media về các URL được Flama allowlist.

Hiện sanitizer/template path cho media phù hợp nhất với `<img src="/media/proxy/...">`; inline arbitrary SVG không nên được mở chỉ để thực hiện feature này.

Vì vậy Phase 1 ưu tiên output dạng:

```html
<div class="flama-stroke-diagrams">
  <figure class="flama-stroke-character">
    <div>勉</div>
    <img src="/media/proxy/<asset-id>" alt="Stroke order for 勉">
  </figure>
</div>
```

Không thay CSP thành:

```text
connect-src *
img-src *
```

và không cho template fetch trực tiếp jsDelivr/GitHub/CDN.

---

# 12. Backend renderer integration

Cần nghiên cứu `app/services/flashcard_renderer.py` và template compilation hiện tại.

Renderer đang dùng Mustache/Chevron. Feature này cần được implement như một **allowlisted Flama template helper / preprocessing directive**, không phải arbitrary Python/JS evaluation.

Suggested flow:

```text
Template source
   ↓
Parse Flama helper directives
   ↓
Validate helper schema + source field exists
   ↓
Read field value
   ↓
Extract CJK characters
   ↓
Resolve stroke asset IDs
   ↓
Generate safe HTML with /media/proxy URLs
   ↓
Continue standard template render + sanitizer
   ↓
Renderer payload allowlists generated asset URLs
```

Cần bảo đảm các generated stroke asset cũng được đưa vào renderer media allowlist giống image/diagram media hiện tại.

---

# 13. Không biến stroke diagram thành field data của từng Note nếu không cần

Stroke diagram là deterministic derivative của:

```text
character + locale + style
```

Không nên lưu HTML/SVG copy vào mỗi Note.

Ví dụ 100,000 notes chứa `日` nên cùng tham chiếu một stroke asset `日/ja/...`.

Note chỉ giữ vocabulary hiện tại.

Template helper resolve diagram ở render layer.

Nếu cần materialize asset relationship để export/offline, hãy thiết kế riêng thay vì copy blob vào note field.

---

# 14. Marketplace / shared Note Type

Shared Note Type có thể chứa stroke helper.

Khi user publish/install template:

- helper config phải được serialize cùng template;
- không serialize machine-specific asset ID nếu asset có thể resolve lại;
- dependency `stroke-diagram` phải được validate;
- preview Marketplace phải render giống Study;
- nếu source dataset không có character, UI degrade gracefully.

Template publisher không cần bundle hàng nghìn SVG vào shared Note Type package.

---

# 15. Template editor UX

Cần thêm UI giúp người dùng không phải nhớ syntax.

Ví dụ trong Template Editor:

```text
Insert
  └─ Stroke Diagram
       Source field: [Expression ▼]
       Language:     [Japanese ▼]
       Style:        [Progressive ▼]
       Size:         [Medium ▼]
       Deduplicate:  [x]
```

Preview phải dùng sample value của field để cho creator nhìn ngay kết quả.

Nếu sample:

```text
Expression = 食べる
```

preview chỉ render `食`.

Nếu:

```text
Expression = hello
```

preview hiển thị empty state nhẹ hoặc không render component, không tạo error toàn template.

---

# 16. Chinese locale / simplified / traditional

Cần test riêng:

- `zh-CN`
- `zh-TW`
- có thể `zh-HK` nếu sản phẩm support.

Không convert Simplified <-> Traditional ngầm định trong stroke resolver.

Nếu input là `學` thì lookup `學`.

Nếu input là `学` thì lookup `学`.

Conversion là feature khác và không thuộc scope mặc định của stroke diagram.

---

# 17. Error handling

Các trường hợp không được làm card fail hoàn toàn:

- field không tồn tại;
- field empty;
- không có CJK character;
- unsupported character;
- provider data thiếu;
- SVG generation failure;
- asset storage failure;
- cache corrupted.

Trong production Study:

- degrade gracefully;
- log structured error;
- phần field còn lại của card vẫn render.

Trong Template Editor/Preview:

- hiển thị warning cụ thể để creator sửa config.

Ví dụ:

```text
Stroke diagram: field "Expression2" không tồn tại.
```

hoặc:

```text
Không có dữ liệu stroke Japanese cho 𠮟.
```

---

# 18. Performance

Không được query DB/storage một lần cho từng character nếu có thể batch.

Ví dụ field có 8 Kanji:

```text
日本語能力試験
```

backend nên:

1. extract toàn bộ;
2. batch resolve cache/index;
3. generate missing assets;
4. batch load media metadata;
5. render.

Cần benchmark impact lên:

- Study next-card latency;
- Marketplace preview;
- Note Type live preview;
- bulk rendering/export nếu có.

Nên có in-memory cache cho dataset parsing/index và persistent cache cho generated asset.

---

# 19. Security

## SVG

- Không trust arbitrary SVG upload/source.
- Không preserve `<script>`.
- Không event handler.
- Không `<foreignObject>`.
- Không external href/resource.
- Không CSS `url(...)` external.
- Không JavaScript URL.
- Validate MIME/content khi serve.

## Template helper

- field name phải thuộc Note Type hiện tại;
- locale nằm trong allowlist;
- mode nằm trong allowlist;
- size có range giới hạn;
- character count có hard limit;
- không cho user truyền filesystem path/URL/provider path.

Ví dụ tuyệt đối không cho dạng:

```text
{{stroke url="https://..."}}
```

hoặc:

```text
{{stroke file="../../etc/..."}}
```

## Dataset update

Dataset source/version phải pin, checksum và review khi update.

Không download `latest` tùy ý trong production startup.

---

# 20. Licensing / attribution model

Tạo metadata cho từng provider, ví dụ conceptual:

```python
StrokeProviderInfo(
    id="kanjivg",
    name="KanjiVG",
    version="...",
    homepage="...",
    license="CC-BY-SA-3.0",
)
```

```python
StrokeProviderInfo(
    id="makemeahanzi",
    name="Make Me a Hanzi",
    version="...",
    homepage="...",
    license="Arphic Public License",
)
```

Research nơi hiển thị attribution phù hợp:

- `/licenses` hoặc About/Open-source licenses;
- metadata của generated asset;
- export package nếu license yêu cầu;
- docs/developer notice.

Không nhét attribution lặp lại dưới từng card nếu license không yêu cầu kiểu đó; nhưng phải đảm bảo requirement license thực tế được đáp ứng.

---

# 21. Suggested technical components

Tên cuối cùng có thể thay đổi theo convention repo.

Backend candidate:

```text
app/services/strokes/
├── extractor.py
├── service.py
├── svg_renderer.py
├── providers/
│   ├── base.py
│   ├── kanjivg.py
│   └── makemeahanzi.py
└── licenses.py
```

Possible responsibilities:

### `extractor.py`

- plain text extraction;
- Unicode CJK extraction;
- preserve order/dedupe;
- limit.

### `providers/*`

- dataset lookup;
- stroke path data;
- source/version metadata.

### `svg_renderer.py`

- generate canonical SVG;
- grid/stroke numbers/progressive style;
- no active SVG content.

### `service.py`

- cache key;
- media asset lookup/create;
- provider routing by locale;
- batch resolution.

Không bắt buộc đúng folder structure này nếu codebase có service organization phù hợp hơn.

---

# 22. API requirement

Feature chính nên được server-side renderer resolve trực tiếp, không bắt buộc browser gọi N API cho N Kanji.

Nếu cần public/internal API để debug hoặc reuse, nghiên cứu endpoint kiểu:

```text
GET /api/v1/strokes/ja/勉
```

hoặc:

```text
POST /api/v1/strokes/resolve
{
  "locale": "ja",
  "text": "勉強する",
  "mode": "progressive"
}
```

Nhưng Template Study path không nên phụ thuộc vào frontend fetch sau khi iframe đã render, vì renderer CSP hiện deliberately chặn arbitrary connect và card cần render ổn định/offline-friendly hơn.

---

# 23. Admin / maintenance

Không cần admin UI lớn ở Phase 1, nhưng cần operational visibility.

Nghiên cứu ít nhất:

- provider version đang dùng;
- số supported characters;
- generated asset count;
- cache hit/miss;
- generation failures;
- unsupported character count;
- regenerate assets theo `style_version` hoặc provider update.

Có thể có management command:

```text
flama strokes index
flama strokes verify
flama strokes prewarm --locale ja
flama strokes regenerate --style-version v2
```

Tên command tùy CLI hiện tại.

---

# 24. Tests

## Extractor

Japanese:

```text
勉強する -> 勉, 強
食べ物 -> 食, 物
JLPT日本語N1 -> 日, 本, 語
```

Chinese:

```text
学习中文 -> 学, 习, 中, 文
學習中文 -> 學, 習, 中, 文
```

Mixed:

```text
APIを勉強する2026 -> 勉, 強
```

Test HTML/ruby input nếu field type cho phép.

## Locale routing

- `ja` -> Japanese provider;
- `zh-CN` -> Chinese provider;
- `zh-TW` -> Chinese/traditional-capable provider;
- unknown locale -> defined fallback/error.

## SVG security

Assert generated SVG không chứa:

```text
script
foreignObject
onload=
onclick=
http://
https://
javascript:
```

## Renderer

- helper field valid;
- invalid field;
- empty field;
- unsupported character;
- multiple Kanji;
- duplicate behavior;
- media URL được đưa vào renderer allowlist;
- Study/Preview/Marketplace cùng output contract.

## Caching

- cùng character/config reuse cùng asset;
- concurrent requests không tạo duplicate physical asset;
- style/provider version thay đổi tạo cache key mới.

---

# 25. Phase plan

## Phase 0 - Investigation

- Xác minh license.
- Đo coverage Japanese/Chinese.
- So sánh quality sample 100-300 characters phổ biến.
- Kiểm tra size dataset.
- Chọn storage/import strategy.
- Chốt helper syntax/structured config.

## Phase 1 - Static Japanese Kanji

- KanjiVG provider.
- extractor.
- safe SVG generator.
- media asset integration.
- template helper.
- Template Editor insert UI.
- preview/study/Marketplace support.

Có thể rollout Japanese trước để giảm scope.

## Phase 2 - Chinese Hanzi

- Make Me a Hanzi / Hanzi Writer Data provider.
- `zh-CN` / `zh-TW` routing.
- Simplified/traditional tests.

## Phase 3 - Rich diagram options

- progressive layout nâng cao;
- grid styles;
- stroke highlight;
- configurable numbering.

## Phase 4 - Animation / handwriting practice research

Nghiên cứu Hanzi Writer hoặc renderer tương tự cho:

- animated stroke order;
- play/pause;
- handwriting quiz.

Phase này cần review lại sandbox/bridge/CSP và không được mở arbitrary external script/network access.

---

# 26. Out of scope ban đầu

Không bắt buộc trong task đầu:

- handwriting recognition;
- chấm điểm nét user vẽ;
- OCR chữ viết tay;
- radical dictionary đầy đủ;
- automatic simplified/traditional conversion;
- AI nhận diện Kanji;
- hỗ trợ Hangul;
- render mọi CJK Extension character nếu upstream không có data.

---

# 27. Deliverables

- Báo cáo research KanjiVG / Make Me a Hanzi / Hanzi Writer Data.
- License decision/documentation.
- Provider abstraction.
- CJK character extractor.
- Locale-aware resolver.
- Safe deterministic SVG generator.
- Generated stroke SVG integration với Flama media layer.
- Cache/deduplication.
- Template helper nhận một source field.
- UI insert/config helper trong Template Editor.
- Live Preview support.
- Study renderer support.
- Marketplace Shared Note Type/Deck preview support.
- Error/fallback handling.
- Unit/integration/security tests.
- Documentation cho template creator.

---

# 28. Acceptance criteria

- Người tạo Template có thể chọn một field như `Expression` và thêm Stroke Diagram mà không tự upload image.
- Backend tách đúng Kanji/Hanzi từ field, bỏ kana/latin/punctuation.
- Japanese và Chinese sử dụng provider/locale phù hợp, không infer mù từ Unicode character.
- Với `勉強する`, Japanese helper resolve tối thiểu `勉` và `強`.
- Với `学习中文`, Chinese helper resolve các Hanzi tương ứng nếu dataset support.
- Stroke diagram được serve qua media URL nội bộ của Flama, không cần browser gọi CDN bên thứ ba.
- Card renderer không cần nới `connect-src` hoặc cho arbitrary external image/script.
- Generated SVG không chứa active/external content nguy hiểm.
- Cùng character + locale + style reuse cùng generated asset.
- Unsupported character không làm fail toàn card.
- Template Preview, Study và Marketplace Preview có behavior thống nhất.
- Có character/render limit chống abuse và card quá nặng.
- Dataset/provider version được pin và có source/license metadata.
- License requirements của dataset được document trước production rollout.
- Tests cover extractor, locale routing, SVG security, renderer integration và caching.
