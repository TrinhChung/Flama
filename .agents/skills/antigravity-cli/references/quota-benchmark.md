# Antigravity quota benchmark and routing baseline

Use this file to estimate `agy` worker cost before dispatch. Treat every number as a dated
measurement, not a billing guarantee or a replacement for live quota from
`$antigravity-manager-api`.

## Benchmark snapshot — 2026-08-28 JST

Environment:

- repository: `D:\Project\nihongo`;
- CLI: local `agy.exe`;
- quota family: Gemini Models;
- the Manager `is_current` account was `t***@gmail.com`, but that flag may represent the
  Classic target rather than the `agy` target; account attribution is therefore provisional;
- Manager quota was refreshed after the login probe and after each benchmark task;
- both assignments were read-only and left `git status` clean.

| Run | Model | Assignment | Wall time | Observed five-hour delta | Observed weekly delta |
|---|---|---|---:|---:|---:|
| Login probe | `gemini-3.7-flash-low` | Return exactly `AGY_LOGIN_OK` | 10.7 s | about 0.111 percentage points | about 0.019 percentage points |
| Small scout | `gemini-3.7-flash-low` | Inventory the existing change-password surface, maximum 12 bullets | about 38 s | about 0.564 percentage points | about 0.094 percentage points |
| Architecture scout | `gemini-3.7-flash-high` | Audit the smallest MySQL 8 CI gate, maximum 15 bullets | about 88 s | about 1.609 percentage points | about 0.268 percentage points |
| Small backend coding, two attempts | `gemini-3.7-flash-medium` | Implement and test the backend change-password slice; first headless attempt was permission-denied, second succeeded | about 5.3 min combined | about 5.95 percentage points on inferred CLI target A3 | about 1.01 percentage points on inferred CLI target A3 |

In this sample, the high-reasoning architecture scout used about `2.86x` the observed quota
of the low-reasoning small scout in both quota windows. The medium coding row is an upper-bound
for one successful task because it includes a failed permission attempt. The sample is
intentionally small. Manager refresh granularity, prompt context, repository reads, tool calls,
concurrent usage, and the difference between Classic and `agy` account targets can change the
observed delta. Do not attribute a delta to a specific account unless the CLI target has been
verified or exactly one eligible account changed consistently during the run.

## Model routing baseline

- Use `gemini-3.7-flash-low` for file inventories, documentation scans, ownership maps,
  contract summaries, and other bounded read-only scouting.
- Benchmark `gemini-3.7-flash-medium` on the first small coding assignment before using it
  for batch estimates. It was not measured in the 2026-08-28 run.
- Reserve `gemini-3.7-flash-high` for security boundaries, migrations, payment transaction
  logic, shared-deck overlay behavior, study architecture, and difficult integration review.
- Use Claude/GPT quota only for an intentional cross-review or when Gemini output is not
  reliable enough for the task. Do not consume it merely to balance percentages.
- Do not extrapolate read-only measurements directly to large coding assignments. Record a
  new benchmark after the first representative edit-and-test task.

## Account snapshot — 2026-08-28 JST

This table is historical context only. Always query live quota before a long task or any
rotation decision. Blank five-hour quota means the account did not expose a complete bucket
and must be excluded from automatic selection until refreshed and validated.

| Label | Masked account | Gemini 5h | Gemini week | Claude/GPT 5h | Claude/GPT week | Snapshot note |
|---|---|---:|---:|---:|---:|---|
| A1 | `c***@gmail.com` | 92.7% | 5.9% | 100.0% | 32.8% | Do not use for Gemini long work at this snapshot |
| A2 | `s***@gmail.com` | unavailable | unavailable | unavailable | unavailable | Exclude until quota is complete |
| A3 | `m***@gmail.com` | 99.4% before the coding run; 93.5% after | 84.8% before; 83.8% after | 100.0% | 66.0% | Inferred `agy` target for the medium coding run; attribution is not independently verified |
| A4 | `2***@vnu.edu.vn` | unavailable | 100.0% | unavailable | 100.0% | Exclude until five-hour buckets are complete |
| A5 | `d***@gmail.com` | unavailable | 100.0% | unavailable | 100.0% | Exclude until five-hour buckets are complete |
| A6 | `l***@gmail.com` | 100.0% | 83.3% | 100.0% | 66.3% | Second complete Gemini fallback at this snapshot |
| A7 | `t***@gmail.com` | 96.5% | 82.7% | 100.0% | 62.7% | Manager `is_current` account; not proof of the active `agy` target |

Do not switch from A7 merely because A3 or A6 had more quota in this snapshot. Follow the
worker orchestration rule: rotate only when the applicable five-hour or weekly remaining
fraction is at or below `0.10`, or after an explicit quota-exhaustion response. Recompute the
best eligible account from live data at that time.

## Benchmark ledger

For each representative worker run, record these fields in the task report or the next dated
section of this file:

| Field | Required value |
|---|---|
| Date/time | Include timezone |
| Task ID | Stable assignment identifier |
| Account | Masked email or non-secret label |
| Model | Exact `agy models` identifier |
| Work type | Scout, coding, test, review, or integration |
| Wall time | Seconds or minutes |
| Quota before/after | Five-hour and weekly values for the applicable model family |
| Delta | Percentage-point change in both windows |
| Repository state | Files changed and whether `git status` remained clean |
| Validation | Tests or checks run |
| Outcome | Accepted, needs review, failed, or quota-blocked |

Never store Manager API keys, account IDs, tokens, cookies, unmasked credentials, or raw
credential responses in this file.
