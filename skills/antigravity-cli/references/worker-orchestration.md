# Antigravity CLI Worker Orchestration

Use `agy` as an external implementation worker only for concrete, bounded work that can be reviewed from repository artifacts and command output.

## Task contract

Give every worker:

- the exact repository and working directory;
- one objective and explicit out-of-scope boundaries;
- files or modules it owns;
- repository instructions it must read, especially `AGENTS.md` and applicable skills;
- behavior that must remain unchanged;
- acceptance criteria and focused tests;
- a prohibition on commits, pushes, resets, production writes, and unrelated cleanup unless the user explicitly requested them;
- a final report containing files changed, tests run, failures, risks, and remaining work.

Use print mode for bounded tasks whose final report is sufficient. Use an interactive or continued conversation only when iterative feedback is genuinely needed.

Example shape:

```powershell
agy --print $taskPrompt `
    --model gemini-3.7-flash-high `
    --effort high `
    --mode accept-edits `
    --output-format text
```

Do not place secrets in `$taskPrompt`, logs, or committed artifacts.

## Shared-worktree safety

- Do not run two code-writing workers against overlapping files in one worktree.
- Prefer separate Git worktrees for parallel workers. Otherwise run workers sequentially and assign non-overlapping ownership.
- Inspect `git status` before and after every worker. Existing changes belong to the user or another worker and must not be discarded.
- Review the complete diff and rerun relevant tests locally before accepting a worker's result.
- A worker's success message is evidence to inspect, not proof that the task is complete.

## Quota-aware execution

Use `$antigravity-manager-api` to read the active `agy` account and quota before a long task or after a quota-related failure. Interpret quota by the model family the task will use:

- Gemini models use the Gemini quota group.
- Claude and GPT models use the Claude/GPT quota group.
- Consider the account near exhaustion when the applicable five-hour or weekly `remaining_fraction` is at or below `0.10`, or when the provider explicitly rejects the request for quota exhaustion.

Do not rotate merely because another account has more quota. Do not refresh quota automatically unless cached data is clearly stale and the user has authorized refresh.

Before estimating batch cost or choosing a reasoning tier, read
[`quota-benchmark.md`](quota-benchmark.md). It contains the dated Flama benchmark, model-routing
baseline, historical masked-account snapshot, and the ledger fields to record for future
representative runs. Never treat its account percentages as live quota.

## Automatic `agy` account rotation

The user has authorized account switching for the `agy` target when the active account reaches the near-exhaustion condition above.

Rotation procedure:

1. Wait for the current `agy` process to finish or fail. Never switch credentials during an active generation or tool operation.
2. Read all Manager accounts and exclude disabled, proxy-disabled, validation-blocked, forbidden, or missing-quota accounts.
3. For the required model family, choose the eligible account with the highest minimum of its five-hour and weekly remaining fractions. Prefer an account that is not already the active `agy` account.
4. If the best candidate is ambiguous or no eligible account has more than `0.10` remaining, stop and report the quota blocker.
5. Switch only the CLI target using `accountId` with `target_ide = 'agy'`. Do not change Classic or Antigravity IDE.
6. Verify with `agy models` and one minimal model response before resuming the task.
7. Retry the interrupted task at most once after a verified account switch. Do not create an account-rotation loop.
8. Report that a rotation occurred, naming the selected account and relevant remaining quota without exposing credentials.

Account rotation changes external state but must never expand the assigned task's authority.

## Completion

After the worker returns:

1. Inspect its changed files and compare them with assigned ownership.
2. Reject unrelated edits or duplicate abstractions.
3. Run focused tests and `git diff --check`.
4. Record unresolved risks and remaining tasks.
5. Do not mark an architecture phase complete solely from a worker report.
