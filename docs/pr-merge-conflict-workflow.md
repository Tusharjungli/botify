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

## Button choice for run review conflicts

When the conflict header says the current side is the Botify feature branch and the incoming side is `main`, use this rule for the run-review PR:

- Click **Accept Current Change** for README conflicts that mention **Run Review** or the roadmap line with `run review`.
- Click **Accept Current Change** for README conflicts where the current side says the BTC chart uses stacked labels.
- Click **Accept Current Change** for `src/botify/app.py` conflicts that add `.review-list`, the **Run Review** panel, `renderReviewNotes(data.review_notes)`, `renderReviewNotes(...)`, `labelSlots`, `nextLabelY(...)`, stacked chart labels, `snapshot["review_notes"]`, or `_review_notes_payload(...)`.
- Click **Accept Current Change** for `tests/test_app.py` conflicts that add `review_notes = snapshot["review_notes"]` or assertions for `Small sample` and `Exposure` review-note labels.
- Do **not** click **Accept Both Changes** for these conflicts. It can duplicate UI sections, JavaScript functions, chart-label logic, or test assertions.
- Do **not** click **Accept Incoming Change** unless you intentionally want to remove the run-review panel and stacked chart-label improvement.

After accepting the current side for these conflicts, save the files and run:

```bash
git add readme.MD src/botify/app.py tests/test_app.py
PYTHONPATH=src pytest
git diff --check
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN" readme.MD src/botify/app.py tests/test_app.py
git status
```

## Fix pytest SyntaxError from conflict markers

If pytest fails with a message like this:

```text
SyntaxError: invalid syntax
File ".../tests/test_app.py", line 76
[line beginning with seven < characters and the branch name]
```

then the merge conflict was not fully resolved. Python is trying to parse Git conflict markers as code.

For the run-review conflict in `tests/test_app.py`, remove the marker lines and keep the feature-branch assertions. The resolved block should look like this:

```python
    snapshot = app.snapshot_with_controls()
    diagnostics = snapshot["diagnostics"]
    review_notes = snapshot["review_notes"]
    csv_body = app.trades_csv()

    assert diagnostics["gross_profit"] == 1.0
    assert diagnostics["gross_loss"] == 0.5
    assert diagnostics["profit_factor"] == 2.0
    assert diagnostics["expectancy"] == 0.25
    assert diagnostics["trend_flip_exits"] == 1
    assert any(note["label"] == "Small sample" for note in review_notes)
    assert any(note["label"] == "Exposure" for note in review_notes)
    assert "side,entry_price,exit_price,quantity,pnl,reason,opened_at,closed_at" in csv_body
    assert "LONG,80000,80100,0.01,1.0,target" in csv_body
    assert "SHORT,80200,80250,0.01,-0.5,trend_flip" in csv_body
```

Then run this from the repository root:

```bash
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN" readme.MD src/botify/app.py tests/test_app.py
PYTHONPATH=src pytest
```

On Windows PowerShell, use:

```powershell
$env:PYTHONPATH="src"
rg -n '<<<<<<<|=======|>>>>>>>' readme.MD src/botify/app.py tests/test_app.py
pytest
```

The `rg` command should print nothing. If it prints any file and line number, open that file and resolve the remaining conflict before running pytest again.

## Fix pytest SyntaxError from conflict markers in app.py

If pytest reports a syntax error in `src/botify/app.py` near `_diagnostics_payload` or `_review_notes_payload`, the app file still contains conflict markers. Remove the marker lines and keep the feature-branch code.

Around the diagnostics section, the resolved code should include this transition from diagnostics into review notes:

```python
    closed_trades = len(trades)
    expectancy = sum(trade.pnl for trade in trades) / closed_trades if closed_trades else 0.0
    return {
        "open_exposure": sum(position["notional"] for position in positions),
        "open_positions": len(positions),
        "long_positions": sum(1 for position in positions if position["side"] == "LONG"),
        "short_positions": sum(1 for position in positions if position["side"] == "SHORT"),
        "average_win": gross_profit / len(wins) if wins else 0.0,
        "average_loss": sum(losses) / len(losses) if losses else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": None if math.isinf(profit_factor) else profit_factor,
        "expectancy": expectancy,
        "trend_flip_exits": sum(1 for trade in trades if trade.reason == "trend_flip"),
        "grid_width_pct": ((grid[-1] - grid[0]) / price * 100) if grid and price else 0.0,
        "nearest_target_distance_pct": min(target_distances) if target_distances else None,
    }


def _review_notes_payload(snapshot: dict, diagnostics: dict) -> list[dict[str, str]]:
    notes = []
```

Also make sure `_snapshot_unlocked()` keeps both payload lines:

```python
    snapshot["diagnostics"] = _diagnostics_payload(snapshot)
    snapshot["review_notes"] = _review_notes_payload(snapshot, snapshot["diagnostics"])
```

After fixing `app.py`, run this from the repo root in Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
rg -n '<<<<<<<|=======|>>>>>>>' readme.MD src/botify/app.py tests/test_app.py
python -m compileall -q src tests
pytest
python test.py
git status
```

The `rg` command must print nothing before you run pytest.

## Keep local VS Code and GitHub in sync after conflict fixes

After tests pass locally, commit and push the resolved files:

```powershell
git status
git add readme.MD src/botify/app.py tests/test_app.py docs/pr-merge-conflict-workflow.md
git commit -m "Resolve dashboard conflict markers"
git push --force-with-lease origin HEAD
```

If Git says there is nothing to commit, only push:

```powershell
git push --force-with-lease origin HEAD
```

Then refresh the GitHub PR page. The branch in VS Code and GitHub will match after the push finishes successfully.

## Button choice for paper exchange lifecycle conflicts

When GitHub shows conflicts for the paper-exchange lifecycle PR and the conflict header says the current side is the Botify feature branch while the incoming side is `main`, use this rule:

- Click **Accept Current Change** for `docs/pr-merge-conflict-workflow.md` conflicts that mention paper exchange, app conflict marker fixes, pytest conflict marker fixes, diagnostics, CSV export, or run review.
- Click **Accept Current Change** for `readme.MD` conflicts that mention paper orders, fills, paper order lifecycle, richer local exchange emulator, or `/api/state` including paper orders and fills.
- Click **Accept Current Change** for `src/botify/app.py` conflicts that add **Open Paper Orders**, **Recent Paper Fills**, `orders`, `fills`, `open_orders`, `recent_fills`, or `canceled_orders` to the dashboard.
- Click **Accept Current Change** for `src/botify/engine.py` conflicts that add `PaperExchange`, `Order`, `exchange`, `process_price`, `_open_positions_from_fills(...)`, `open_orders`, `recent_fills`, or `canceled_orders`.
- Click **Accept Current Change** for `tests/test_engine.py` conflicts that add `test_engine_routes_entries_through_paper_exchange_orders` or assertions for `open_orders` / `recent_fills`.
- Do **not** click **Accept Both Changes** for these conflicts. It can duplicate dashboard sections, snapshot fields, exchange fill logic, or tests.
- Do **not** click **Accept Incoming Change** unless you intentionally want to remove the paper-exchange lifecycle feature.

After accepting the current side for these conflicts, save the files and run:

```bash
git add docs/pr-merge-conflict-workflow.md readme.MD src/botify/app.py src/botify/engine.py tests/test_engine.py
PYTHONPATH=src pytest
git diff --check
CONFLICT_PATTERN='<{7}|={7}|>{7}'
rg -n "$CONFLICT_PATTERN" docs/pr-merge-conflict-workflow.md readme.MD src/botify/app.py src/botify/engine.py tests/test_engine.py
git status
```

On Windows PowerShell:

```powershell
$env:PYTHONPATH="src"
git add docs/pr-merge-conflict-workflow.md readme.MD src/botify/app.py src/botify/engine.py tests/test_engine.py
pytest
git diff --check
rg -n '<<<<<<<|=======|>>>>>>>' docs/pr-merge-conflict-workflow.md readme.MD src/botify/app.py src/botify/engine.py tests/test_engine.py
git status
```

If tests pass and `rg` prints nothing, finish the merge or rebase, then push with `git push --force-with-lease origin HEAD`.
