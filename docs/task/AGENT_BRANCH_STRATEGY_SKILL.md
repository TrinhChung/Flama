# Skill — Chiến lược nhánh cho AI Agent (Tri / San)

## Mục đích

Tài liệu này là quy tắc làm việc chung cho các AI agent như **Tri** và **San** khi thực hiện task trong repository Flama.

Mục tiêu là:

- không làm hỏng `master`;
- tránh hai agent ghi đè công việc của nhau;
- mỗi thay đổi có phạm vi nhỏ, review được và rollback được;
- luôn có checkpoint trên Git để agent khác hoặc lượt chạy sau có thể tiếp tục;
- `develop` luôn là nhánh tích hợp chính cho công việc đang phát triển;
- `master` chỉ nhận code đã được tích hợp, test và chủ động release.

---

# 1. Quy tắc cốt lõi

```text
master
  ↑
  │ release / promotion only
  │
develop
  ↑
  │ PR / merge sau test
  │
work branch
```

### Bắt buộc

1. **Không commit trực tiếp vào `master`.**
2. **Không tạo task branch từ `master`** cho công việc bình thường.
3. Mọi feature/fix/refactor/test/hardening/investigation phải bắt đầu từ `develop` mới nhất.
4. PR của task bình thường phải target `develop`.
5. Chỉ promotion/release mới đi từ `develop` → `master`.
6. Agent không tự merge `develop` → `master` nếu không có yêu cầu rõ ràng từ người quản lý repository.
7. Không để thay đổi quan trọng chỉ tồn tại local khi kết thúc phiên làm việc.

---

# 2. Vai trò của từng nhánh

## `master`

`master` đại diện cho trạng thái production/release ổn định.

Không dùng `master` làm nơi tích hợp công việc hàng ngày.

```text
master = release line
```

Agent chỉ được tác động tới `master` khi task ghi rõ đây là release/promotion/hotfix production và có chỉ đạo cụ thể.

### Cấm

```text
git checkout master
# sửa code
git commit
git push origin master
```

---

## `develop`

`develop` là nhánh tích hợp chính.

```text
develop = source of truth cho development hiện tại
```

Mỗi task mới phải lấy trạng thái mới nhất từ đây.

Trước khi làm:

```bash
git fetch origin
git checkout develop
git pull --ff-only origin develop
```

Sau đó mới tạo work branch.

---

## Work branch

Mỗi task độc lập nên có branch riêng.

Ví dụ:

```text
develop
  ↓
fix/oauth-callback-preservation
  ↓
PR → develop
```

Không gom nhiều vấn đề không liên quan vào cùng một branch.

---

# 3. Quy tắc dành riêng cho Tri và San

Tri và San phải coi Git là cơ chế handoff chính.

## Không cùng sửa một branch nếu không có handoff rõ ràng

Mặc định:

```text
Tri → branch A
San → branch B
```

Không nên:

```text
Tri ─┐
     ├→ cùng push branch X
San ─┘
```

trừ khi task yêu cầu phối hợp và đã ghi rõ agent nào đang giữ ownership hiện tại.

## Khi tiếp tục task của agent khác

Trước tiên phải kiểm tra:

- task document;
- branch hiện tại;
- open PR;
- commit mới nhất;
- test status;
- phần đã hoàn thành;
- phần còn lại.

Nếu branch cũ vẫn là checkpoint hợp lệ và chưa merge, **tiếp tục branch đó** thay vì tạo branch mới gây duplicate work.

Ví dụ:

```text
Tri làm:
fix/google-login-linking

Tri dừng giữa task và đã push checkpoint
        ↓
San tiếp tục chính branch đó
```

Nếu muốn đổi ownership thì cập nhật task doc hoặc PR description trước khi tiếp tục.

---

# 4. Branch naming

Ưu tiên tên ngắn nhưng thể hiện đúng loại công việc.

## Prefix khuyến nghị

```text
feat/<task>
fix/<task>
refactor/<task>
test/<task>
docs/<task>
chore/<task>
hardening/<task>
investigation/<task>
hotfix/<task>
```

Ví dụ:

```text
feat/google-login
fix/oauth-next-redirect
hardening/oauth-scope-validation
investigation/claude-mcp-oauth
docs/claude-connector-guide
test/mcp-refresh-token
```

Nếu cần phân biệt ownership giữa nhiều agent đang làm song song, có thể thêm agent vào task slug:

```text
feat/tri-google-login
investigation/san-claude-cimd
```

Không dùng tên mơ hồ:

```text
fix/test
update/code
new-feature
branch1
tri-work
```

---

# 5. Một task lớn phải chia thành branch nhỏ

Không tạo một branch khổng lồ cho cả roadmap.

Sai:

```text
feature/all-oauth-improvements
```

Đúng:

```text
hardening/oauth-scope-model
fix/oauth-userinfo-scope-check
feat/google-login-identity-model
feat/google-login-callback
feat/claude-connector-guide
```

Mỗi branch nên:

- giải quyết một vấn đề cụ thể;
- có test độc lập;
- review độc lập;
- rollback độc lập;
- không chứa cleanup ngoài scope.

---

# 6. Quy trình bắt đầu một task

Agent phải làm theo thứ tự:

```text
1. Fetch remote
2. Checkout develop
3. Pull develop mới nhất
4. Đọc task docs
5. Xem open PR / branch liên quan
6. Xem recent commits liên quan
7. Xác nhận task chưa được agent khác hoàn thành
8. Tạo hoặc tiếp tục đúng work branch
9. Bắt đầu sửa
```

Không được chỉ dựa vào memory/context cũ của agent.

Repository mới nhất mới là nguồn sự thật.

---

# 7. Khi task đang có branch chưa merge

Nếu task đã có branch:

```text
fix/oauth-callback
```

và vẫn chưa merge, agent phải đánh giá trước khi tạo branch khác.

### Tiếp tục branch cũ khi

- task vẫn cùng scope;
- branch không bị bỏ;
- checkpoint hiện tại hợp lệ;
- không có PR khác supersede nó.

### Tạo branch mới khi

- phần mới là task độc lập;
- branch cũ đã merge;
- branch cũ bị abandoned và có lý do rõ ràng;
- cần tách phần unsafe/experimental khỏi phần có thể merge.

Không tạo các branch song song kiểu:

```text
fix/oauth-v1
fix/oauth-v2
fix/oauth-final
fix/oauth-final2
```

mà không ghi rõ branch nào là authoritative.

---

# 8. Đồng bộ với `develop`

Nếu work branch tồn tại lâu và `develop` thay đổi đáng kể, agent phải cập nhật branch trước khi merge.

Ưu tiên lịch sử dễ hiểu và tránh rewrite branch đang dùng chung.

### Branch chỉ do một agent sở hữu

Có thể rebase nếu an toàn:

```bash
git fetch origin
git rebase origin/develop
```

### Branch đang được nhiều agent/handoff dùng

Ưu tiên merge `develop` vào branch để tránh force-push làm mất commit người khác:

```bash
git fetch origin
git merge origin/develop
```

Không force-push branch shared nếu chưa chắc chắn.

---

# 9. Quy tắc commit

Commit phải là checkpoint có ý nghĩa.

Ưu tiên Conventional Commit style:

```text
feat: ...
fix: ...
refactor: ...
test: ...
docs: ...
chore: ...
```

Ví dụ:

```text
feat(auth): add Google identity model
fix(oauth): preserve authorize next URL after login
test(mcp): cover refresh token rotation
docs(task): add Claude connector investigation
```

Không dùng commit message vô nghĩa:

```text
update
fix
changes
wip2
ok
final
```

Một checkpoint chưa hoàn thiện vẫn có thể commit nếu cần handoff, nhưng message phải nói rõ trạng thái:

```text
chore(auth): checkpoint Google callback validation
```

và task doc phải ghi phần còn lại.

---

# 10. Kết thúc mỗi phiên làm việc

Một scheduled run hoặc một phiên agent không được kết thúc với code quan trọng chỉ nằm local.

Mục tiêu cuối phiên:

```text
working state
    ↓
tests
    ↓
task/docs updated
    ↓
commit
    ↓
push
```

Nếu task hoàn tất và đủ điều kiện merge:

```text
push branch
→ PR target develop
→ CI/test green
→ merge develop
```

Nếu task chưa hoàn tất nhưng checkpoint an toàn:

```text
commit checkpoint
→ push branch
→ cập nhật task doc
→ KHÔNG merge
```

Task doc phải ghi tối thiểu:

```text
Status:
Completed:
Remaining:
Current branch:
Last commit:
Tests run:
Known blockers:
Next recommended step:
```

---

# 11. Điều kiện merge vào `develop`

Chỉ merge khi:

- scope task đã hoàn thành;
- test liên quan xanh;
- không có known regression nghiêm trọng;
- migration nếu có đã được kiểm tra;
- docs/task state đã cập nhật;
- branch đã đồng bộ đủ mới với `develop`;
- diff không chứa thay đổi ngoài scope.

Nếu một phần còn dang dở nhưng branch vẫn có giá trị, giữ branch để tiếp tục; không merge chỉ để "cho sạch branch".

---

# 12. Pull Request strategy

PR bình thường:

```text
work branch → develop
```

Ví dụ:

```text
fix/oauth-next-redirect
       ↓
PR base: develop
```

PR nên mô tả:

- vấn đề;
- thay đổi chính;
- test đã chạy;
- migration/config impact;
- risk;
- rollback nếu cần.

Không tạo PR task bình thường trực tiếp vào `master`.

---

# 13. Promotion từ `develop` sang `master`

Đây là release action, không phải task action.

Flow:

```text
feature/fix branches
        ↓
      develop
        ↓
 integration / regression / deploy readiness
        ↓
 PR develop → master
        ↓
      release
```

Agent chỉ thực hiện promotion này khi có yêu cầu rõ ràng.

Trước promotion cần kiểm tra tối thiểu:

- CI của `develop`;
- migration;
- production config/env impact;
- critical regression tests;
- pending high-risk PR;
- deploy notes.

Không dùng `master` làm shortcut chỉ vì task cần deploy nhanh.

---

# 14. Hotfix production

Hotfix là ngoại lệ, không phải flow thường xuyên.

Nếu production trên `master` có lỗi nghiêm trọng cần sửa ngay và có chỉ đạo làm hotfix:

```text
master
  ↓
hotfix/<issue>
  ↓
PR → master
```

Sau khi hotfix vào `master`, **phải đưa cùng fix trở lại `develop`** để tránh regression ở release sau.

```text
hotfix → master
   └──→ develop
```

Không để lịch sử thành:

```text
master có fix
but develop không có fix
```

Nếu không có yêu cầu hotfix rõ ràng, vẫn dùng flow bình thường từ `develop`.

---

# 15. Docs-only changes

Mặc định docs cũng nên theo branch → `develop` nếu là thay đổi đáng kể.

Tuy nhiên một tài liệu task/checkpoint đơn giản có thể commit trực tiếp vào `develop` **khi người quản lý repository yêu cầu rõ ràng**.

Ngay cả trong trường hợp đó:

```text
allowed: develop
forbidden: master
```

Không coi exception docs là lý do để commit source code trực tiếp vào `develop` một cách tùy tiện.

---

# 16. Database migration strategy

Một migration phải thuộc đúng branch của thay đổi schema.

Không để:

```text
branch A sửa model
branch B tạo migration cho model đó
```

trừ khi task được tách có chủ đích.

Khi nhiều branch cùng tạo migration:

- kiểm tra migration heads;
- resolve conflict trước khi merge;
- không sửa migration đã production-apply một cách tùy tiện;
- tạo migration tiếp theo nếu cần correction.

---

# 17. Không trộn investigation và implementation nếu chưa rõ root cause

Với task chưa xác định đúng hướng, ưu tiên:

```text
investigation/<topic>
```

hoặc chỉ cập nhật investigation doc.

Sau khi có kết luận mới tách implementation:

```text
feat/<topic>
fix/<topic>
hardening/<topic>
```

Ví dụ Claude MCP:

```text
investigation/claude-mcp-oauth
       ↓ kết luận
feat/claude-cimd
```

Không implement một protocol lớn chỉ vì UI client có option tương ứng.

---

# 18. Quy tắc tránh scope creep

Nếu đang làm:

```text
fix/google-login-callback
```

và thấy thêm một vấn đề unrelated trong deck service:

Không sửa chung.

Thay vào đó:

1. ghi issue/task mới;
2. hoàn thành branch hiện tại;
3. tạo branch riêng sau.

Một branch càng nhỏ thì càng dễ review, rollback và handoff.

---

# 19. Nếu test fail

Phải phân loại:

```text
A. Fail do branch hiện tại
B. Fail đã tồn tại trên develop
C. Fail do môi trường/flaky
```

Không được bỏ qua test fail mà không ghi lý do.

Nếu fail do branch hiện tại:

```text
không merge
```

Nếu fail đã tồn tại trên `develop`, ghi evidence và đánh giá liệu task có an toàn để merge hay không.

---

# 20. Nếu xảy ra conflict giữa Tri và San

Không giải quyết bằng cách overwrite file của agent kia.

Flow:

```text
1. Fetch latest remote
2. Xác định branch/commit authoritative
3. Đọc cả hai diff
4. Preserve logic hợp lệ của cả hai phía
5. Resolve conflict
6. Chạy test
7. Commit conflict resolution
8. Push
```

Nếu hai agent vô tình implement cùng task, chọn một branch làm canonical rồi cherry-pick/merge phần có giá trị từ branch còn lại.

Không để hai PR cùng sửa cùng logic kéo dài không cần thiết.

---

# 21. Rollback strategy

Mỗi task branch phải đủ nhỏ để có thể revert riêng.

Nếu commit đã merge vào `develop` gây regression:

ưu tiên `git revert` thay vì rewrite history của `develop`.

```text
bad commit
   ↓
git revert <sha>
```

Không force-push `develop` để xóa lịch sử đã chia sẻ.

---

# 22. Branch cleanup

Sau khi PR đã merge và không còn cần branch:

- có thể xóa remote work branch;
- không xóa branch chưa merge nếu còn checkpoint cần handoff;
- trước khi xóa phải chắc commit đã tồn tại trong `develop` hoặc đã được lưu ở branch thay thế.

---

# 23. Decision tree nhanh cho agent

```text
Có task mới?
   ↓
Checkout latest develop
   ↓
Task đã có branch chưa?
   ├─ Có → branch còn hợp lệ?
   │        ├─ Có → tiếp tục branch đó
   │        └─ Không → ghi lý do và tạo branch mới
   │
   └─ Chưa → tạo branch từ develop

Làm xong?
   ├─ Chưa nhưng checkpoint an toàn
   │      → test phần đã làm
   │      → update task doc
   │      → commit + push
   │      → không merge
   │
   └─ Xong
          → test
          → update docs
          → PR → develop
          → merge khi green

Có cần master?
   ├─ task bình thường → KHÔNG
   └─ release/hotfix được yêu cầu rõ → theo release/hotfix flow
```

---

# 24. Ví dụ cho Tri

Tri nhận task Google login:

```text
develop
  ↓
feat/google-login-identity-model
  ↓ merge

develop
  ↓
feat/google-login-oauth-flow
  ↓ merge

develop
  ↓
test/google-login-regression
```

Không nên:

```text
master
  ↓
tri-google-all
```

---

# 25. Ví dụ cho San

San nhận task Claude Connector investigation:

```text
develop
  ↓
investigation/claude-mcp-oauth
```

Nếu investigation cho thấy chỉ cần docs:

```text
develop
  ↓
docs/claude-connector-guide
```

Nếu sau đó cần CIMD:

```text
develop
  ↓
feat/claude-cimd
```

Không trộn investigation + CIMD + DCR + UI guide vào một branch nếu các phần có thể review độc lập.

---

# 26. Checklist trước khi push

- [ ] Tôi đang ở đúng branch.
- [ ] Branch được tạo từ `develop` hoặc là continuation hợp lệ.
- [ ] Tôi không sửa ngoài scope.
- [ ] Tôi không chứa secret/token/credential trong commit.
- [ ] Test liên quan đã chạy.
- [ ] Task/status doc đã cập nhật nếu cần handoff.
- [ ] Commit message mô tả đúng thay đổi.
- [ ] Push target không phải `master`.

---

# 27. Checklist trước khi merge vào `develop`

- [ ] Task đã hoàn thành đủ scope.
- [ ] Tests xanh hoặc mọi exception đã được chứng minh rõ.
- [ ] Không có unresolved conflict.
- [ ] Không chứa debug code hoặc secret.
- [ ] Migration/config đã được đánh giá.
- [ ] Task docs đã cập nhật trạng thái.
- [ ] Diff đủ nhỏ và review được.
- [ ] PR target là `develop`.

---

# 28. Quy tắc cuối cùng

Nếu không chắc nên làm gì, ưu tiên lựa chọn ít rủi ro hơn:

```text
không đụng master
→ lấy develop mới nhất
→ branch nhỏ
→ test
→ checkpoint
→ push
→ PR vào develop
```

Git phải luôn chứa đủ trạng thái để **Tri, San hoặc một agent khác có thể tiếp tục công việc mà không cần dựa vào context riêng của agent trước**.
