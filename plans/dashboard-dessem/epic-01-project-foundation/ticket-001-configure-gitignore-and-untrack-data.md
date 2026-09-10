# ticket-001 Configure `.gitignore` and untrack the input data

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `docker-linux-server-architect`
> Commands run in WSL bash at the repository root `/home/carlosribeiro/git/plotador-dessem`.

## Context

### Background

The repository currently versions its own input data: `git ls-files exemplo | wc -l` returns 240
Parquet files, and `**/__pycache__/**` is tracked as well. The feature spec requires that the
synthesis folders never be versioned. The spec also suggested ignoring `logo/` and `*.md`, which the
developer **rejected** (see `planning-context.md` decision 11): the ONS logo and all Markdown files
must stay under version control. Nothing else in the repository has a `.gitignore`, so the `.venv`,
tool caches, logs, output and generated dashboards created by the following tickets would all become
untracked noise.

### Relation to Epic

This is the first ticket of the foundation epic and the only one that touches git plumbing. It runs
before `ticket-002` creates `.venv`, `.mypy_cache` and `.ruff_cache`, so those directories are
ignored from the moment they appear rather than being cleaned up afterwards.

### Current State

Verified on 2026-09-10 at the repository root:

- No `.gitignore` exists.
- `git ls-files exemplo | wc -l` prints `240`; the tracked paths are
  `exemplo/2024-03-03|04/caso_{oficial,gurobi}/sintese/*.parquet`.
- `git status --short` reports those 240 files as **unstaged deletions** (` D`), plus untracked
  entries: `exemplo/sintese/`, `exemplo/caso_oficial/`, `exemplo/caso_gurobi/`, `logo/`,
  `UsoCorreto da Marca_VR_dezembro2018.pdf`, `plano_dashboard_dessem.md`, `plans/` and `.claude/`.
- `logs/` and `output/` do not exist.

The 240 worktree deletions are **intentional** (master plan open question 4, resolved 2026-09-10):
the developer flattened `exemplo/` on purpose and later rebuilt a scenario-first tree under
`exemplo/caso_oficial/` and `exemplo/caso_gurobi/` (untracked, ignored from this ticket on). This
ticket changes the **index** only; `git rm -r --cached exemplo` leaves the 240 removals **staged**
for this ticket's own commit. Nothing is restored or deleted from disk.

## Specification

### Requirements

1. Create `.gitignore` at the repository root with English comments, covering: `exemplo/`, `*.pdf`, `.claude/settings.local.json`,
   `__pycache__/`, `*.py[cod]`, `.venv/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`,
   `*.egg-info/`, `logs/*`, `output/*`, `dashboard_dessem.html` and `*.html` at the root, plus a
   negation keeping `**/.gitkeep` tracked.

   > **Amended 2026-09-10** (developer decision at gate G7 during execution): the two runtime
   > directories use the **content** patterns `logs/*` and `output/*`, not the directory patterns
   > `logs/` and `output/`. A trailing-slash directory pattern makes git prune the directory without
   > listing it, so per `gitignore(5)` — "It is not possible to re-include a file if a parent
   > directory of that file is excluded" — the mandated final `!**/.gitkeep` negation could never
   > re-include `logs/.gitkeep` or `output/.gitkeep`, and requirement 4 below would be unreachable.
   > With `logs/*` the directory is still listed, so the existing final negation is sufficient and no
   > extra per-directory negation lines are needed.
2. `logo/` and `*.md` must **not** be ignored.
3. Remove `exemplo/**` and every `__pycache__` directory from the git index without touching the
   working tree, using `git rm -r --cached`.
4. Create `logs/.gitkeep` and `output/.gitkeep` so both runtime directories exist in a fresh clone.
5. Stage exactly `.gitignore`, `logs/.gitkeep` and `output/.gitkeep` (the `exemplo` and `__pycache__`
   removals are already staged), commit with a conventional message in Portuguese focused on the why
   (`chore: ...`), ending with the line
   `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`,
   and push to `origin main`. Never `git add -A`.

### Inputs

The repository working tree. No arguments, no configuration.

### Outputs and Behavior

Three new tracked files (`.gitignore`, `logs/.gitkeep`, `output/.gitkeep`), an index from which the
240 `exemplo` entries and all `__pycache__` entries have been removed, and an untouched working tree
apart from the two new directories. All of it lands in one commit pushed to `origin main`.

### Error Handling

If `git rm -r --cached exemplo` reports `did not match any files`, the index is already clean;
report it and continue. Do not use `git rm` without `--cached`, and do not run `git checkout`,
`git clean` or `git add -A`. If `git push` is rejected, report the error verbatim and stop; never
force-push.

## Dependencies

- **Blocked By**: none
- **Blocks**: `ticket-002-create-pyproject-and-package-skeleton.md`

## Acceptance Criteria

- [ ] Given the repository root, when `git check-ignore -v exemplo/sintese/EST.parquet` is run, then
      it exits 0 and prints a rule sourced from `.gitignore`.
- [ ] Given the repository root, when `git ls-files exemplo | wc -l` is run, then it prints `0`.
- [ ] Given the repository root, when
      `git check-ignore -q logo/MarcasONS_Secundarias_verticais_Verde.png; echo $?` is run, then it
      prints `1`, and the same command for `plano_dashboard_dessem.md` also prints `1`.
- [ ] Given the repository root, when `git status --short -- logs output` is run, then its only
      output lines are the two `logs/.gitkeep` and `output/.gitkeep` additions, and
      `git status --short -- exemplo | grep -vc '^D '` prints `0` (only staged deletions remain).
- [ ] Given the repository root, when
      `git ls-files | grep -c __pycache__` is run, then it prints `0`.
- [ ] Given the commit has been made and pushed (the five criteria above are evaluated before it),
      when `git status --short` and `git log origin/main -1 --name-status` are run, then the first
      prints nothing and the second lists `.gitignore`, `logs/.gitkeep` and `output/.gitkeep` as
      added and only `exemplo/**` and `__pycache__` paths as deleted.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `.gitignore` with grouped, commented sections in this order: Python artifacts, virtual
   environment, tool caches, packaging, project runtime directories, input data, generated
   dashboards, then the `!**/.gitkeep` negation last so it wins.
2. Untrack the input data and caches, index only:

   ```bash
   cd /home/carlosribeiro/git/plotador-dessem
   git rm -r --cached --quiet exemplo
   git ls-files | grep '__pycache__' | tr '\n' '\0' | xargs -0 -r git rm --cached --quiet
   ```

3. Create the placeholders:

   ```bash
   mkdir -p logs output && touch logs/.gitkeep output/.gitkeep
   ```

4. Verify with the first five acceptance-criteria commands and report their output verbatim.
5. Stage the three new files by path, commit (`chore: ignora dados de entrada e caches e os remove
   do índice`, plus the `Co-Authored-By` line), run `git push origin main`, then run the sixth
   criterion.

### Key Files to Create/Modify

- `.gitignore` (create)
- `logs/.gitkeep` (create, empty)
- `output/.gitkeep` (create, empty)

### Patterns to Follow

- `.gitignore` comments in English, per Rigoroso mode.
- Ignore directories with a trailing slash (`exemplo/`, not `exemplo`) — **except** the two runtime
  directories that must keep a tracked placeholder, which use the content form `logs/*` and
  `output/*` so the final `!**/.gitkeep` negation can still apply (see the amendment under
  requirement 1).
- Keep the `!**/.gitkeep` negation as the final line of the file.

### Pitfalls to Avoid

- `git rm -r exemplo` **without** `--cached` would delete the developer files on disk. Always pass
  `--cached`.
- Do not add `logo/` or `*.md` to `.gitignore`: the spec suggestion was explicitly rejected.
- Ignoring `*.html` globally would also ignore any future test fixture; restrict the rule to the
  repository root (`/*.html`) plus `output/`.
- `git check-ignore` exits 1 when a path is **not** ignored, which is the expected result for the
  logo and the Markdown files. Do not treat that exit code as a failure.

### Out of Scope

- Deleting `exemplo/sintese/` or any other data from disk.
- Any branch operation or force-push: commit and push on `main` only.
- The legacy `Leitura/`, `Plotadores/` and `main_*.py` files, which stay tracked until ticket-038.

## Testing Requirements

### Unit Tests

None: this ticket produces no Python code.

### Integration Tests

Manual verification through the six acceptance-criteria commands (the first five before the commit,
the sixth after the push), executed at the repository root in WSL bash, with their output pasted
into the completion report. Additionally confirm, before committing, that
`git status --short | grep -c '^D  exemplo'` prints `240` (the removals are staged, index only)
and, after the push, that `ls exemplo` still lists `caso_gurobi`, `caso_oficial` and `sintese`,
proving the working tree was not modified.

## Definition of Done

- [ ] `.gitignore`, `logs/.gitkeep` and `output/.gitkeep` exist with the content described above.
- [ ] All six acceptance criteria commands produce the stated output.
- [ ] Before the commit, `git status --short | grep -c '^D  exemplo'` prints `240`; after the push,
      `ls exemplo` still lists `caso_gurobi`, `caso_oficial` and `sintese`.
- [ ] Exactly one commit was created and pushed to `origin main`; `git status --short` is empty.

## Effort Estimate

**Points**: 1 · **Confidence**: High · **Agent time**: about 15 minutes
