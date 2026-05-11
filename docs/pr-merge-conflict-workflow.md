# PR merge-conflict workflow

Use this workflow when a pull request shows conflicts in files such as `readme.MD`, `src/botify/app.py`, or `tests/test_app.py`. The goal is to update one feature branch against the latest `main` once, resolve conflicts locally, run tests, and force-push the cleaned branch instead of repeatedly choosing **Accept current change**, **Accept incoming change**, or **Accept both changes** in the web editor.

## Why the conflicts keep happening

Conflicts usually appear when a PR branch is created from another unmerged PR branch, when multiple PRs edit the same lines, or when a branch is updated by merge commits instead of a clean rebase. Git then sees two different histories changing the same sections and asks you to choose which version should win.

## Recommended rule

Create every new PR branch from the latest `main`, not from an old feature branch or another open PR branch.

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c my-feature-branch
```

## Clean an existing conflicted PR branch

Run this from the feature branch that owns the PR:

```bash
git fetch origin
git rebase origin/main
```

If Git stops on a conflict:

1. Open each conflicted file and remove every conflict marker line (seven `<`, `=`, or `>` characters).
2. Keep the final intended content only. Do not blindly choose **Accept both changes** because that often duplicates README bullets, routes, tests, or imports.
3. Mark the file resolved and continue the rebase:

```bash
git add readme.MD src/botify/app.py tests/test_app.py
git rebase --continue
```

After the rebase completes, run checks and push the updated branch:

```bash
PYTHONPATH=src pytest
git diff --check
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN" readme.MD src/botify/app.py tests/test_app.py
git push --force-with-lease origin HEAD
```

Use `--force-with-lease`, not plain `--force`, so Git refuses to overwrite someone else's newer remote work by accident.

## If the branch history is already messy

If the PR branch contains reverted commits, duplicate work, or changes from another PR, make a clean replacement branch from `main` and cherry-pick only the commits needed for this PR:

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c clean-feature-branch
git cherry-pick <needed-commit-sha>
PYTHONPATH=src pytest
git diff --check
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN"
git push -u origin clean-feature-branch
```

Then open a new PR from `clean-feature-branch` and close the old conflicted PR.

## Team habits that prevent repeat conflicts

- Keep PRs small and focused.
- Avoid editing the same README section in multiple PRs at once.
- Do not branch a new PR from another PR branch unless you intentionally want a stacked PR.
- Rebase on `origin/main` before pushing PR updates.
- Resolve conflicts locally and run tests before pushing.

## Button choice for diagnostics and CSV export conflicts

When the conflict header says the current side is the Botify feature branch and the incoming side is `main`, use this rule for the diagnostics/CSV export PR:

- Click **Accept Current Change** for README conflicts that mention **Trade Diagnostics**, **Export trades CSV**, `GET /api/trades.csv`, or the roadmap line with diagnostics and CSV export.
- Click **Accept Current Change** for `src/botify/app.py` conflicts that add `csv`, `io`, `exportTrades()`, `Trade Diagnostics`, `factorClass()`, `renderDiagnostics(...)`, `/api/trades.csv`, `_send_csv(...)`, `_diagnostics_payload(...)`, or `trades_csv()`.
- Click **Accept Current Change** for `tests/test_app.py` conflicts that add `from botify.engine import Trade` or the diagnostics/CSV export test.
- Do **not** click **Accept Both Changes** for these conflicts. It can duplicate imports, UI blocks, routes, tests, or roadmap bullets.
- Do **not** click **Accept Incoming Change** unless you intentionally want to remove the diagnostics and CSV export feature.

After accepting the current side for these conflicts, save the files and run:

```bash
git add readme.MD src/botify/app.py tests/test_app.py
PYTHONPATH=src pytest
git diff --check
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN" readme.MD src/botify/app.py tests/test_app.py
git status
```

If the tests pass and `rg` prints no conflict markers, complete the merge or rebase:

```bash
# If Git says you are rebasing:
git rebase --continue

# If Git says all conflicts are fixed but you are merging:
git commit
```

Then push the resolved branch:

```bash
git push --force-with-lease origin HEAD
```
