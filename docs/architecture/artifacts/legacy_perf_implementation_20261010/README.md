# Synthetic implementation checks — 10/10/2026

Run from the repository root:

```powershell
.venv/Scripts/python.exe docs/architecture/artifacts/legacy_perf_implementation_20261010/probe.py
```

`results.json` contains historical BEFORE measurements copied from the preserved
[audit result](../legacy_perf_audit_20261010/results.json), plus new AFTER measurements.
The script records the baseline SHA-256, Git HEAD, dirty-worktree state, measured
source hashes and its own hash. It rejects a run if measured source changes
during execution. BEFORE values are not reruns of old runtime code.

The directly comparable fixture stays the same: 1,000 foreign decks; 600 NoteTypes
(100 published, 500 private); 100 templates with about 16 KiB HTML each; then
1,000 Notes with Word plus a 4 KiB Body for duplicate checks. The compatibility
list/template responses retain exactly the original JSON-equivalent size.

| Path | Historical BEFORE | AFTER |
|---|---|---|
| Statistics, learner without owned decks/progress | 3 SELECT; 1,000 Deck objects | 2 SELECT; 0 Deck objects |
| Marketplace full compatibility list | 403 SELECT; 600 NoteType objects; 1,854,201 B | 402 SELECT; 100 NoteType objects; same full payload |
| React Marketplace compact page, 24/100 | Full compatibility list above | 3 SELECT; 24 NoteType objects; 41,823 B |
| Template Library full compatibility list | 3 SELECT; 100 templates; 1,698,842 B | Same query/object/payload counts |
| React Template Library compact page, 24/100 | Full compatibility list above | 5 SELECT; 24 templates; 12,964 B |
| Duplicate helper called 50 times | 50 SELECT; 50,000 Note hydrations | 50 identity SELECT; 0 Note hydrations |
| Duplicate helper with one request lookup shared across 50 checks | Previous helper loop above | 1 identity SELECT; 0 Note hydrations |

The compact Template Library fixture intentionally has old empty/null
`input_schema`: one batched HTML read preserves inferred inputs. This explains
the extra compatibility query; HTML is omitted from the response.

An additional actual `canAddNotes` dispatcher batch validates 50 successful
checks. It adds two FieldDefs and, if absent, a matching template **after** the
comparable probes. The current batch performs 7 SELECT with 0 Note hydrations,
but accessible deck/model resolution still hydrates the publisher's 1,001 Decks
and 600 NoteTypes once. There is no historical transport baseline for this
additional case; its timing cannot be compared to the old duplicate-only helper.

All data lives in SQLite memory. No configured application database, environment
file or production data is read. Local one-shot timings are diagnostics, not
production p95 or browser timings. JSON bytes are uncompressed equivalents,
not network transfers. These probes cover owned/direct paths; focused tests
cover clone release/overlay correctness separately.
