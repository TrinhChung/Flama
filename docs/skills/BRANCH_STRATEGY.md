# Skill — Branch Strategy cho Tri và San

## Mục đích

Tài liệu này là quy tắc làm việc chung cho **Tri** và **San** khi xử lý task trong repository Flama.

Mục tiêu:

- không làm bẩn `master`;
- tránh hai agent giẫm code của nhau;
- mỗi thay đổi có phạm vi nhỏ, review được và rollback được;
- luôn để repository ở trạng thái có thể tiếp tục từ Git;
- mọi thay đổi bình thường đi qua `develop` trước khi lên release.

---

## 1. Vai trò của các nhánh chính

### `master`

`master` là nhánh release/production.

Quy tắc:

- Không làm task trực tiếp trên `master`.
- Không commit trực tiếp vào `master`.
- Không push code task trực tiếp vào `master`.
- Không tạo feature/fix branch từ `master` cho công việc bình thường.
- Chỉ merge vào `master` khi một tập thay đổi trên `develop` đã đủ điều kiện release.

Luồng bình thường:

```text
feature/fix branch
      ↓
develop
      ↓
release verification
      ↓
master
```

### `develop`

`develop` là integration branch chính cho công việc hằng ngày.

Mọi task bình thường phải bắt đầu từ `develop` mới nhất.

```text
develop
   ↓
task branch
   ↓
test
   ↓
PR / merge
   ↓
develop
```

Nếu chỉ sửa tài liệu nhỏ theo yêu cầu trực tiếp và không cần isolation riêng, có thể commit thẳng vào `develop`. Với thay đổi code, mặc định phải dùng branch riêng.

---

## 2. Quy trình bắt đầu một task

Trước khi sửa code:

```bash
git checkout develop
git fetch origin
git pull --ff-only origin develop
```

Sau đó kiểm tra:

```bash
git status
git log --oneline -10
```

Phải xác nhận:

- đang ở `develop`;
- working tree sạch;
- đã lấy code mới nhất;
- task chưa được agent khác hoàn thành;
- task không conflict với branch đang active của agent khác.

Sau đó mới tạo branch.

---

## 3. Mỗi task độc lập dùng một branch riêng

Không gom nhiều vấn đề không liên quan vào cùng branch.

Ví dụ đúng:

```text
develop
  ├─ fix/oauth-refresh-token
  ├─ feat/claude-mcp-connector
  ├─ refactor/payment-reconciliation
  └─ test/mcp-oauth-regression
```

Ví dụ không nên:

```text
fix/everything
feature/update
tri-work
san-temp
```

Tên branch phải cho biết branch đang làm gì.

### Prefix khuyến nghị

```text
feat/<short-name>       feature mới
fix/<short-name>        bug fix
refactor/<short-name>   refactor không đổi behavior chính
test/<short-name>       test/regression coverage
docs/<short-name>       documentation
chore/<short-name>      maintenance/tooling
hardening/<short-name>  security/architecture hardening
```

---

## 4. Tri và San không dùng chung một branch để làm song song

Nếu Tri và San cùng tham gia một chủ đề lớn, phải chia thành task nhỏ.

Ví dụ:

```text
Claude MCP Connector
        ↓
Tri: investigation OAuth flow
San: UI documentation design
```

Branch:

```text
Tri → docs/claude-oauth-investigation
San → feat/claude-connector-guide
```

Không làm:

```text
Tri + San
   ↓
feat/claude-mcp
```

rồi cả hai push vào cùng branch mà không có coordination rõ ràng.

Nếu task B phụ thuộc task A, ưu tiên:

```text
A merge vào develop
        ↓
B tạo/rebase từ develop mới
```

thay vì xếp nhiều branch phụ thuộc chồng lên nhau.

---

## 5. Không bắt đầu branch từ branch cũ của agent khác

Mặc định branch phải được tạo từ `develop`.

```bash
git checkout develop
git pull --ff-only origin develop
git checkout -b fix/example
```

Chỉ base branch B trên branch A khi dependency là bắt buộc và đã được ghi rõ trong task.

Nếu không có lý do rõ ràng:

```text
branch A
   ↓
branch B
   ↓
branch C
```

là không được khuyến khích vì làm review, rollback và merge phức tạp.

---

## 6. Chia task nhỏ để mỗi branch có một mục tiêu

Một branch tốt nên trả lời được một câu:

> Branch này giải quyết vấn đề gì?

Nếu câu trả lời chứa nhiều `và`, task có thể đang quá lớn.

Ví dụ task lớn:

```text
Hoàn thiện OAuth cho MCP
```

Nên chia:

```text
1. normalize OAuth scopes
2. enforce userinfo scopes
3. add Claude connector compatibility tests
4. add connector documentation
5. implement client metadata support nếu cần
```

Mỗi phần có thể test, commit và merge độc lập.

---

## 7. Quy tắc commit

Commit phải nhỏ, có nghĩa và phản ánh đúng thay đổi.

Ví dụ:

```text
fix(oauth): preserve authorize params after login

test(mcp): cover refresh token flow

docs(mcp): add Claude connector investigation
```

Không dùng commit message kiểu:

```text
update
fix
work
wip123
final final
```

Một commit không nhất thiết chỉ sửa một file, nhưng phải phục vụ một mục đích rõ ràng.

---

## 8. Không để thay đổi chỉ tồn tại local

Khi kết thúc một lượt làm việc, đặc biệt với agent/scheduled run:

```text
working state
     ↓
tests
     ↓
docs/task status updated
     ↓
commit
     ↓
push
```

Không được kết thúc với code quan trọng chỉ nằm local.

Nếu task chưa hoàn thành nhưng đã đạt checkpoint an toàn:

1. chạy test phù hợp;
2. cập nhật task doc với trạng thái hiện tại;
3. commit checkpoint;
4. push branch;
5. ghi rõ phần tiếp theo cần làm.

Ví dụ trạng thái trong task doc:

```text
Status: IN PROGRESS

Completed:
- OAuth discovery verified
- PKCE authorize flow verified

Remaining:
- refresh token test
- Claude callback verification

Continue from branch:
feat/claude-mcp-oauth
```

---

## 9. Test trước khi merge

Không merge chỉ vì code compile hoặc nhìn có vẻ đúng.

Tối thiểu phải chạy:

- test liên quan trực tiếp đến phần sửa;
- regression test cho behavior có nguy cơ bị ảnh hưởng;
- lint/typecheck/build nếu thay đổi frontend hoặc tooling yêu cầu.

Nếu test suite có lỗi có sẵn không liên quan, phải ghi rõ:

```text
Existing failure:
<test name>

Reason considered unrelated:
<evidence>
```

Không được gọi branch là "ready" nếu test mới do chính branch gây ra đang fail.

---

## 10. Merge target mặc định luôn là `develop`

PR của task bình thường:

```text
head: feat/example
base: develop
```

Không:

```text
head: feat/example
base: master
```

trừ khi task được chỉ định rõ là production hotfix.

Sau khi merge:

```bash
git checkout develop
git pull --ff-only origin develop
```

và xác nhận thay đổi đã có trên `develop` trước khi bắt đầu task phụ thuộc tiếp theo.

---

## 11. Khi nào mới merge `develop` → `master`

`master` chỉ nhận release từ `develop` khi:

- các task cần release đã merge vào `develop`;
- test bắt buộc xanh;
- migration/deployment impact đã được kiểm tra;
- không còn branch bắt buộc phải merge trước release;
- release scope được xác định rõ.

Luồng:

```text
develop
   ↓
PR release
   ↓
master
```

Không dùng `master` làm integration branch hằng ngày.

---

## 12. Hotfix production

Hotfix là ngoại lệ, không phải workflow mặc định.

Chỉ dùng khi production trên `master` có lỗi cần sửa ngay và không thể chờ release bình thường.

Flow khuyến nghị:

```text
master
  ↓
hotfix/<name>
  ↓
test
  ↓
PR → master
  ↓
production fix
```

Sau đó **bắt buộc đồng bộ fix trở lại `develop`**:

```text
hotfix/master
      ↓
develop
```

để lần release sau không làm mất hotfix.

Không tự quyết định dùng hotfix flow nếu task không thực sự khẩn cấp.

---

## 13. Xử lý conflict

Nếu branch bị conflict vì `develop` đã thay đổi:

1. fetch `develop` mới nhất;
2. hiểu thay đổi upstream trước;
3. rebase hoặc merge `develop` vào branch theo quy ước của repository;
4. resolve conflict theo behavior mới nhất;
5. chạy lại test;
6. không chọn `ours/theirs` mù.

Không force-push branch dùng chung với agent khác nếu chưa coordination.

---

## 14. Task docs là checkpoint chung giữa agent

Tri và San phải coi `docs/task/` là nơi truyền trạng thái công việc giữa các lượt/agent.

Ví dụ:

```text
docs/task/Tri/
docs/task/San/
```

Task doc nên ghi:

- mục tiêu;
- branch đang dùng;
- trạng thái;
- phần đã hoàn thành;
- evidence/test đã chạy;
- blocker;
- phần tiếp theo;
- commit/PR liên quan khi hữu ích.

Một agent khác phải có thể đọc task doc + Git history và tiếp tục mà không cần context riêng của agent trước.

---

## 15. Không sửa phạm vi ngoài task nếu không cần

Trong khi làm task:

- không opportunistic refactor module không liên quan;
- không đổi formatting diện rộng;
- không rename nhiều file nếu task không yêu cầu;
- không nâng dependency chỉ vì tiện;
- không sửa một lỗi khác phát hiện tình cờ trong cùng branch nếu nó có thể tách riêng.

Nếu phát hiện vấn đề mới:

```text
phát hiện
   ↓
ghi vào task/issue mới
   ↓
xử lý branch riêng
```

Điều này giữ diff nhỏ và giảm regression.

---

## 16. Quy tắc dành cho investigation task

Investigation không đồng nghĩa với phải sửa code.

Flow:

```text
đọc code/spec
   ↓
reproduce / test
   ↓
thu evidence
   ↓
kết luận root cause / compatibility
   ↓
đề xuất task implementation riêng nếu cần
```

Không biến một investigation branch thành feature branch lớn mà không cập nhật scope.

Nếu chỉ cần cập nhật kết quả investigation vào docs, có thể kết thúc bằng docs-only commit/PR.

---

## 17. Quy tắc dành cho migration/schema/auth/security

Các thay đổi có blast radius cao phải chia nhỏ hơn bình thường.

Ví dụ:

- OAuth/token lifecycle;
- database migration;
- permissions;
- payment;
- deployment/startup;
- authentication/session;
- MCP authorization.

Phải có:

- backward compatibility assessment;
- regression tests;
- rollback consideration;
- migration ordering nếu có schema change;
- không gộp nhiều security behavior vào một commit khó review.

---

## 18. Checklist trước khi push

- [ ] Branch được tạo từ `develop` mới nhất, trừ hotfix được chỉ định rõ.
- [ ] Không đang làm việc trực tiếp trên `master`.
- [ ] Branch chỉ giải quyết một phạm vi rõ ràng.
- [ ] Không có secret/token/credential thật trong diff.
- [ ] Test liên quan đã chạy.
- [ ] Không có debug code/log tạm không cần thiết.
- [ ] Task doc đã cập nhật nếu task kéo dài nhiều lượt.
- [ ] Commit message mô tả đúng thay đổi.

---

## 19. Checklist trước khi merge vào `develop`

- [ ] Task đạt Definition of Done.
- [ ] Test bắt buộc xanh.
- [ ] Diff không chứa thay đổi ngoài scope.
- [ ] Migration/config/env impact đã được ghi rõ.
- [ ] Docs cần thiết đã cập nhật.
- [ ] Không còn TODO bắt buộc để behavior hiện tại hoạt động đúng.
- [ ] Branch không phụ thuộc một branch chưa merge mà không được ghi rõ.

---

## 20. Quy tắc ngắn gọn phải nhớ

```text
1 task
  = 1 mục tiêu rõ
  = 1 branch riêng
  = test riêng
  = commit/PR review được
```

```text
NORMAL WORK:
develop → task branch → develop → master(release)
```

```text
KHÔNG:
master → làm feature trực tiếp
```

```text
KẾT THÚC MỖI LƯỢT:
test → docs/status → commit → push
```

Nếu không chắc nên merge vào đâu: **mặc định là `develop`, không phải `master`.**
