# Parallel workflow for Artur and Zakhar

## Branches

- Integration branch: `integration/arthur-zakhar`
- Artur branch: `dev/artur`
- Zakhar branch: `dev/zakhar`

## Task ownership

Ralph reads [`task-owners.json`](/home/artur/projects/one-two-one/task-owners.json) and gives each developer only their own tasks.

- `artur`: backend/core pipeline tasks
- `zakhar`: auth/frontend/media/review tasks

## Merge rule

Both developers work only in their own branches. Shared branch for integration is `integration/arthur-zakhar`.

1. Finish one task or a small dependency-complete batch in personal branch.
2. Push personal branch to origin.
3. Merge personal branch into `integration/arthur-zakhar`.
4. Second developer rebases onto `origin/integration/arthur-zakhar` before the next `ralph.sh` run.

This keeps dependency flow linear and avoids duplicate task claims.

## Artur commands

Run once in the main checkout:

```bash
bash scripts/setup_parallel_worktrees.sh
git push -u origin integration/arthur-zakhar dev/artur dev/zakhar
```

Work cycle for Artur:

```bash
cd ../one-two-one-artur
git fetch origin
git rebase origin/integration/arthur-zakhar
./ralph.sh 1 codex artur
git push origin dev/artur
```

After a finished task or dependency batch:

```bash
cd ../one-two-one-integration
git fetch origin
git merge --no-ff origin/dev/artur
git push origin integration/arthur-zakhar
```

## What Zakhar should do

Zakhar works in his own clone or worktree on branch `dev/zakhar`.

If he has a fresh clone:

```bash
git fetch origin
git checkout -b dev/zakhar origin/dev/zakhar
```

Work cycle for Zakhar:

```bash
git fetch origin
git rebase origin/integration/arthur-zakhar
./ralph.sh 1 claude zakhar
git push origin dev/zakhar
```

After a finished task or dependency batch, he tells Artur:

```text
Готово, смержи origin/dev/zakhar в integration/arthur-zakhar.
```

Or merges it himself if you both agreed to do that directly.

## Conflict policy

- `tasks.json` and `progress.md` merge only through `integration/arthur-zakhar`.
- Before a new Ralph run, always rebase personal branch onto the latest integration branch.
- If a task is `in_progress`, it stays with the same developer until completion or manual reassignment.
