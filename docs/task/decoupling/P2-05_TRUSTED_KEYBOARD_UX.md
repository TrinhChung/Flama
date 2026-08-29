# P2-05 — Trusted keyboard UX and threat model

> Phase: 2
>
> Priority: P1
>
> Status: TODO
>
> Dependency: P2-01 and P2-04
>
> Primary lane: Frontend Security / Browser

## Mục tiêu

Quyết định và, chỉ khi chứng minh an toàn, triển khai UX phím tắt khi focus nằm trong renderer iframe mà không cấp progress capability cho untrusted Template code.

## Nguyên tắc quyết định

Baseline an toàn được chấp nhận là: shortcut hoạt động trong trusted parent UI nhưng không hoạt động khi focus ở iframe. Không được tạo bridge yếu chỉ để đạt parity UX.

## Công việc chi tiết

1. Viết threat model cho:
   - iframe sandbox flags/origin;
   - bootstrap data visibility;
   - same-realm Template JS;
   - forged `postMessage`;
   - monkey-patching/event synthesis;
   - IME/editable controls/repeated keydown.
2. So sánh ít nhất hai phương án:
   - không bridge, documented limitation;
   - một browser-enforceable trusted mechanism/isolated realm nếu thực sự khả thi.
3. Reject rõ các phương án không chứng minh được trust:
   - nonce nằm trong DOM/bootstrap cùng iframe;
   - `event.source`/channel/instance ID đơn thuần;
   - child-supplied `isTrusted` claim;
   - raw command/action/rating messages.
4. Quyết định owner của keyboard mapping phải ở parent semantic Interaction runtime.
5. Nếu phương án an toàn được duyệt, implement contract nhỏ nhất và fail closed.
6. Nếu không có phương án đủ mạnh, giữ bridge disabled và hoàn tất task bằng documented no-bridge decision.
7. Browser acceptance matrix:
   - parent focus;
   - iframe focus;
   - input/textarea/contenteditable;
   - IME composition;
   - repeated keydown;
   - unrelated/forged frame messages.

## Output đầu ra bắt buộc

- Threat model/ADR có alternatives và quyết định.
- Safe implementation + tests, hoặc explicit no-bridge decision + documented UX limitation.
- Browser test evidence dùng isolated Chrome profile.
- Security regression tests cho forged messages.
- Handoff report.

## Acceptance criteria

- Renderer content không thể chọn action/rating hoặc trực tiếp gây progress write.
- Editable/IME input không bị shortcut capture sai.
- Nếu shortcut-in-iframe được hỗ trợ, trust proof phải dựa trên browser-enforced boundary, không dựa vào secret lộ trong untrusted realm.
- Nếu không chứng minh được, bridge phải tiếp tục disabled.

## Verification

```text
python scripts/run_tests.py --module study --frontend-only
```

Thực hiện real-browser verification bằng isolated profile theo `AGENTS.md`.

## Rollback

Rollback luôn quay về no-bridge baseline; không quay về `host_command` cũ.

## Không làm trong task này

- Không thay sandbox/CSP theo hướng nới quyền.
- Không đưa arbitrary Template automation vào parent.
- Không yêu cầu Phase 4/schema.
