# ticket-038 Remove the legacy scripts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `docker-linux-server-architect`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: last ticket of the epic and of the plan, strictly after ticket-037. It must
> NEVER be reordered before ticket-035**, which needs `Plotadores/` in the working tree as the
> parity check's reference implementation. Epic-04 learnings section 10 item 3 records this
> explicitly, and `.implementation-state.json`'s epic-05 refinement inputs repeat it.
> **Git safety is a requirement of this ticket, not a background rule.** Never `git add -A`. Never
> `git rm`, `git checkout` or `git clean`. Never force-push. Never commit `exemplo/`, generated
> HTML, `logs/`, `.venv/`, `.claude/settings.local.json` or secrets. Requirement 3 gives the exact
> deletion procedure, and it uses `rm` on an **enumerated** list of thirteen paths followed by
> `git add --` on those same thirteen paths — never a glob, never a recursive pattern.
> **Never touch anything under `exemplo/`.**

## Context

### Background

Master plan goal 6 and decision 12 make this the last act: "Legacy `Leitura/`, `Plotadores/` and
`main_*.py` are deleted after the parity check passes." The scripts being removed are the tool this
project replaces — seven plotter modules producing 21 single-chart HTML files from a hard-coded
Windows path, five driver modules that work through star imports and import-time side effects, and
one reader module with module-level mutable state.

The removal is safe, and refinement measured why rather than assuming it:

- **Nothing *imports* them, and the sixteen places that *name* them are all prose.** The sweep of
  requirement 6 returns exactly sixteen matches, re-measured at dispatch time: fifteen in
  `tests/test_parity.py` and one in `README.md`.
  **Amendment, spec defect 25 (orchestrator, at dispatch):** this bullet originally claimed the
  sweep "returns **no match**", which was true when epic 5 was refined and false by the time this
  ticket ran. **ticket-035 falsified it** by creating `tests/test_parity.py`, whose legacy
  constants are transcribed with a `file:line` provenance comment each, and **ticket-036** by
  writing the README's Legacy scripts subsection. Both are deliberate and both must survive this
  deletion: the provenance comments are the parity check's audit trail, and ticket-035's Definition
  of Done already proved that module passes with `Leitura/` and `Plotadores/` moved aside, so the
  comments are provably comments rather than references. What the sweep must establish is therefore
  not *silence* but that **every match is prose about the deleted code rather than a live
  dependency on it** — no `import`, no `subprocess`, no path opened, no packaging entry, no
  documentation instruction to run them. Requirement 6 and acceptance criterion 3 carry the
  corrected expectation. Note also that `grep -rn` without `-I` reports binary matches in
  `tests/__pycache__/*.pyc`, which are untracked compiled copies of `test_parity.py`'s own
  docstrings; pass `-I --exclude-dir=__pycache__` rather than treating them as findings.
- **They do not run anyway.** Measured: `.venv/bin/python -c "import Leitura.leitor_arquivos"`
  raises `FileNotFoundError: [Errno 2] No such file or directory:
  'C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo'`, because
  `Leitura/leitor_arquivos.py:9` hard-codes that path and iterates it at module level on line 13.
  All twelve of the other legacy modules carry `from Leitura.leitor_arquivos import *`, so every one
  of them fails at import in this environment. Deleting code that cannot execute removes no
  capability.
- **They are outside every quality gate.** `pyproject.toml` scopes `mypy` to `files = ["src"]`,
  `pytest` to `testpaths = ["tests"]`, and the project's documented gate runs
  `ruff check src tests` and `ruff format --check src tests`. So keeping them costs nothing
  mechanically — which is exactly why the decision has to be made on evidence rather than on
  friction.

**The delete-outright-versus-move-to-`legacy/` question, and the argument that settles it.**
`.implementation-state.json`'s epic-05 refinement inputs record a real objection to deleting
outright: the cost-chart presentation decision is still open and "its only evidence is
`Plotadores/Custos.py`", so deleting leaves that evidence in git history — recoverable, but not
discoverable by someone reading the working tree. **ticket-035 resolved the objection by removing
its premise.** Its parity report transcribes the legacy behaviour into a versioned document: all
seven plotter modules, all twelve `write_html` call sites, the 21 runtime output filenames, every
Y-axis and figure title with a `file:line` reference, the verbatim scalar formulas, the four
implementation defects found while reading, and the `(R$)`-versus-`10^3 R$` unit divergence. Once
that document exists, the evidence is in the working tree as prose, and a `legacy/` directory of
non-executing code would add nothing but a second place to look. **Ruling: delete outright**, and
make the parity report's existence a precondition that requirement 2 verifies before anything is
removed.

**The `__pycache__` question is already answered and must be dropped rather than re-investigated.**
Measured: `git ls-files | grep -c __pycache__` returns `0`, and `.gitignore` line 2 is
`__pycache__/`. ticket-001 handled it. There is nothing for this ticket to do there.

### Relation to Epic

The plan's closing ticket. Everything it depends on is already true: ticket-035 produced the
transcription, ticket-036 wrote the README's Legacy scripts subsection in a form that survives this
removal, and ticket-037 was the last behavioural change. Its whole content is verification plus
thirteen deletions plus one README sentence, which is why it is one point and why the effort is
dominated by checking rather than by editing.

### Current State

`git ls-files` names exactly **thirteen** tracked legacy paths, measured:

```text
Leitura/leitor_arquivos.py
Plotadores/CMO_sbm.py
Plotadores/Custos.py
Plotadores/Ghid_SIN.py
Plotadores/Ghid_sbm.py
Plotadores/Gter_SIN.py
Plotadores/Gter_sbm.py
Plotadores/Tempo.py
main_cmo.py
main_custos.py
main_ghid.py
main_gter.py
main_tempo.py
```

`Leitura/` and `Plotadores/` contain no other tracked file and no tracked `__pycache__`; both
directories disappear when their last file does, since git tracks files rather than directories. On
disk, an untracked `__pycache__/` may appear inside `Leitura/` or `Plotadores/` if anyone has
imported them; it is gitignored, and removing it is optional housekeeping rather than a requirement.

`plano_dashboard_dessem.md` is tracked at the repository root and is **not** part of this removal.
`planning-context.md`'s Sources table names it as "Feature spec — `plano_dashboard_dessem.md`
(repo root)", the master plan's required-reading block points at the plan directory beside it, and
`.gitignore` deliberately keeps `*.md` versioned (decision 11). Moving it would break two
cross-references for no benefit. **Ruling: it stays where it is**, and the outline's third key
decision is closed.

`README.md` after ticket-036 carries a **Legacy scripts** subsection written, by that ticket's
requirement 6, to be true both before and after this removal: it states what the parity report
holds and where to look rather than whether the directories are present. This ticket adds the
removal commit reference to it and changes nothing else in the file.

Repository hygiene state at refinement time, to be **re-measured** rather than trusted:
`git status --porcelain` was clean at the start of the epic-05 refinement and then carried the
epic-04 boundary review's edits, which that boundary commits. `git ls-files` reports 141 tracked
files; `git ls-files exemplo` reports **0**, so nothing under `exemplo/` is tracked and this ticket
cannot touch it by accident through a staging command.

## Specification

### Requirements

1. **Pre-flight, before deleting anything.** Run `git status --porcelain` and require it to be
   empty. If it is not, **stop and report** the exact output without deleting, staging or
   committing anything: the removal must be a commit of its own, and a dirty tree means some other
   work is mid-flight. An untracked, gitignored `__pycache__` directory is the only tolerated
   exception, and even then it must be named in the report.
2. **Verify the transcription exists.** Confirm that
   `plans/dashboard-dessem/epic-05-parity-report.md` exists and that its legacy-inventory section
   names all seven `Plotadores` modules, `Leitura/leitor_arquivos.py`, the five `main_*.py`
   drivers, the 21 runtime output filenames and every Y-axis and figure title with a `file:line`
   reference. If any of that is missing, **stop and report**: the ruling to delete outright rests
   entirely on that document existing, and deleting before it does would lose the only working-tree
   evidence for an open developer decision.
3. **Delete exactly the thirteen paths of Current State, by the following procedure and no other.**
   Re-derive the list with `git ls-files Leitura Plotadores main_cmo.py main_custos.py main_ghid.py
   main_gter.py main_tempo.py` and confirm it returns thirteen paths. Then remove them from the
   working tree with `rm` applied to that **enumerated** list — one explicit path per argument,
   never a glob, never `rm -r` on a pattern — and stage the deletions with `git add --` on the same
   enumerated list. Do **not** use `git rm`: the prohibition exists because a mistyped path set
   destroys work with no working-tree copy left, while `rm` on an enumerated list followed by an
   explicit `git add --` is auditable at both steps. Do **not** use `git add -A`, `git add .`,
   `git checkout` or `git clean` at any point.
4. **Add the removal note to the README's Legacy scripts subsection**, in English: one sentence
   naming the commit that removed the thirteen files and one showing how to recover a single file
   from history, for example
   `git show <sha>^:Plotadores/Custos.py`. Change nothing else in `README.md`, and do not restate
   the parity report's content — point at it.
5. **Verify nothing broke.** After deleting, run the full gate: `.venv/bin/ruff check src tests`,
   `.venv/bin/ruff format --check src tests`, `.venv/bin/mypy src` and
   `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing`. Every one must exit 0, the
   collected test count must equal the count measured immediately **before** the deletion, and total
   coverage must be at or above **85 percent**, the Epic 5 floor. Run
   `.venv/bin/pytest tests/test_parity.py -q` explicitly as well: ticket-035's Definition of Done
   already proved that module passes with `Plotadores/` moved aside, and this is the real event it
   was proved against.
6. **Re-run the reference sweep after deleting**, with
   `grep -rnI --exclude-dir=__pycache__ "Plotadores\|Leitura/\|main_custos\|main_tempo\|main_ghid\|main_gter\|main_cmo\|leitor_arquivos" src/ tests/ docs/ README.md CLAUDE.md pyproject.toml`,
   and require that **every match is prose about the deleted code, never a live dependency on it**.
   The expected set, measured immediately before the deletion, is **sixteen matches in exactly two
   files**: fifteen in `tests/test_parity.py` (the `file:line` provenance comments and docstrings
   recording where each legacy constant was transcribed from) and one in `README.md` (the Legacy
   scripts subsection ticket-036 wrote), becoming seventeen once requirement 4 adds the recovery
   sentence. A match in `src/`, `docs/`, `CLAUDE.md` or `pyproject.toml`, or any match anywhere that
   is an `import`, a `subprocess` call, an opened path or a packaging entry rather than a comment,
   docstring or documentation sentence, is a dangling reference and must be reported, not silently
   fixed. Quote the sweep's full output in the completion report so the classification is auditable
   rather than asserted. **Amendment, spec defect 25 (orchestrator, at dispatch):** requirement 6
   originally demanded that the README's recovery example be the *only* match, which no state of
   this repository can satisfy — see the amended Background bullet for why, and do not attempt to
   reach the original wording by editing `tests/test_parity.py` or `README.md`.
7. **Commit exactly this ticket's own change**, staged by explicit path: the thirteen deletions,
   `README.md`, `plans/dashboard-dessem/.implementation-state.json` and
   `plans/dashboard-dessem/README.md`. One conventional commit in Portuguese focused on the *why*,
   ending with the attribution line the executing session's directive specifies
   (`planning-context.md` decision 17, as amended at the start of `/implement-plan`). Push to
   `origin main` with a plain `git push`; never `--force`, never `--force-with-lease`.
8. Do **not** move `plano_dashboard_dessem.md`, do **not** create a `legacy/` directory, do **not**
   investigate `__pycache__` (measured: nothing tracked, `.gitignore` line 2 covers it), and do
   **not** delete, move or modify anything outside the thirteen enumerated paths plus the four files
   requirement 7 stages.

### Inputs

`git ls-files` for the authoritative path list; `git status --porcelain` for the pre-flight gate;
`plans/dashboard-dessem/epic-05-parity-report.md` for the transcription check;
`README.md`'s Legacy scripts subsection for the note; the four gate commands for the post-deletion
verification.

### Outputs and Behavior

Thirteen files removed from the working tree and the index, `Leitura/` and `Plotadores/` gone,
`main_*.py` gone from the repository root, one README sentence added naming the removal commit and
the recovery command, the full gate green with an unchanged test count, and one pushed commit
containing nothing else. `plano_dashboard_dessem.md`, `logo/`, `LICENSE`, `settings.json`, `docs/`,
`plans/`, `src/`, `tests/` and everything under `exemplo/` are untouched.

### Error Handling

This ticket's error handling is **stop and report**, three times over, and every stop is a success
rather than a failure of the ticket: a non-empty `git status --porcelain` (requirement 1), a missing
or incomplete parity report (requirement 2), and a path list that is not the expected thirteen
(requirement 3). If any gate command fails after the deletion, **do not attempt a fix**: report the
failure with the command's output. A test failing because a legacy file disappeared would mean the
reference sweep of the Background was wrong, which is a finding about the sweep, not a licence to
edit a test.

## Dependencies

- **Blocked By**: `ticket-037-polish-cli-usability-and-errors.md`
- **Hard precondition, stronger than a graph edge**: `ticket-035-run-legacy-parity-check.md` must
  have completed **and** produced `plans/dashboard-dessem/epic-05-parity-report.md` with the legacy
  inventory of requirement 2. The epic order is strictly sequential so this holds; never reorder
  these two.
- **Blocks**: none. This is the last ticket of the plan.
- **Dispatch-order constraint, not a graph edge**: must not run concurrently with ticket-036 or
  ticket-037, both of which edit `README.md`.

## Acceptance Criteria

- [ ] Given a clean working tree, when
      `git ls-files Leitura Plotadores main_cmo.py main_custos.py main_ghid.py main_gter.py
      main_tempo.py` is run before the deletion, then it lists exactly the thirteen paths of Current
      State; and when it is run after the deletion, then it lists none, `git ls-files | wc -l` has
      decreased by exactly 13, and `git ls-files exemplo | wc -l` still returns `0`.
- [ ] Given `plans/dashboard-dessem/epic-05-parity-report.md`, when its legacy-inventory section is
      read before the deletion, then it names all seven `Plotadores` modules,
      `Leitura/leitor_arquivos.py`, the five `main_*.py` drivers, the 21 runtime output filenames and
      at least one `file:line` reference per Y-axis title and figure title — so the behaviour of the
      deleted code survives in the working tree as prose.
- [ ] Given the repository after the deletion, when
      `grep -rnI --exclude-dir=__pycache__ "Plotadores\|Leitura/\|main_custos\|main_tempo\|main_ghid\|main_gter\|main_cmo\|leitor_arquivos"
      src/ tests/ docs/ README.md CLAUDE.md pyproject.toml` is run, then every match is prose about
      the deleted code and none is a live dependency on it: the matches fall in exactly two files,
      `tests/test_parity.py` (provenance comments and docstrings) and `README.md` (the Legacy
      scripts subsection plus requirement 4's recovery sentence), with none in `src/`, `docs/`,
      `CLAUDE.md` or `pyproject.toml`, and the per-file count in `tests/test_parity.py` equal to the
      count measured immediately before the deletion; and `plano_dashboard_dessem.md`, `logo/`,
      `LICENSE` and `settings.json` are all still tracked.
- [ ] Given the repository after the deletion, when `.venv/bin/ruff check src tests`,
      `.venv/bin/ruff format --check src tests`, `.venv/bin/mypy src`,
      `.venv/bin/pytest tests/test_parity.py -q` and
      `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing` are run, then all five
      exit 0, the collected count equals the count measured immediately before the deletion, and
      total coverage is at or above 85 percent.
- [ ] Given the commit this ticket creates, when `git show --stat HEAD` is inspected, then it
      contains exactly the thirteen deletions plus `README.md`,
      `plans/dashboard-dessem/.implementation-state.json` and `plans/dashboard-dessem/README.md`,
      its message is a Portuguese conventional commit explaining why, and `git log origin/main -1`
      shows it pushed without any force flag.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Run the pre-flight first and stop there if the tree is not clean. Everything after this step is
   irreversible in the working tree, and a clean tree is what makes `git show HEAD^:<path>` a
   complete recovery.
2. Read the parity report's legacy-inventory section before deleting, and check it against the
   thirteen filenames. This is the one check that cannot be done afterwards.
3. Measure the collected test count with `.venv/bin/pytest --collect-only -q | tail -1` immediately
   before the deletion and write the number down. Requirement 5 compares against that number, not
   against any figure in a document — the count changed once during this epic's refinement alone,
   from 601 to 602, when the epic-04 boundary review added a test.
4. Delete with one `rm` invocation listing the thirteen paths explicitly, then `git add --` with the
   same thirteen. Re-read the command before pressing enter: the whole reason `git rm` is prohibited
   here is that a path-set mistake is unrecoverable, and the same mistake with `rm` at least leaves
   the index intact.
5. Confirm `Leitura/` and `Plotadores/` are gone from `git ls-files` and, if an untracked
   `__pycache__` directory remains on disk inside either, remove that directory too — it is
   gitignored, so this is housekeeping and changes nothing in git. Name it in the report either way.
6. Write the README sentence after the commit exists is impossible — the note names the commit sha.
   Resolve it the way the plan resolves every such loop: commit the deletions and the README with a
   placeholder-free sentence naming the **recovery command shape** rather than a sha, then, if the
   developer wants the sha recorded, add it in a follow-up. Simpler and preferred: write the
   recovery example as `git show <sha>^:Plotadores/Custos.py` with `<sha>` as a literal placeholder
   and one sentence saying the removal commit is the one whose message names the legacy removal,
   findable with `git log --oneline -- Plotadores`. That is true forever and needs no sha.
7. Run the full gate last, including the 10-minute suite, and paste the four outputs into the
   completion report.
8. Stage by explicit path, commit, push with a plain `git push`. Update
   `plans/dashboard-dessem/.implementation-state.json` and `plans/dashboard-dessem/README.md` inside
   the same commit, as every ticket in this plan has done.

### Key Files to Create/Modify

- The thirteen legacy paths of Current State (delete): `Leitura/leitor_arquivos.py`, the seven
  `Plotadores/*.py`, and `main_cmo.py`, `main_custos.py`, `main_ghid.py`, `main_gter.py`,
  `main_tempo.py`
- `README.md` (modify: one sentence in the Legacy scripts subsection ticket-036 wrote)
- `plans/dashboard-dessem/.implementation-state.json` and `plans/dashboard-dessem/README.md`
  (modify: the per-ticket status and score writes every ticket of this plan performs)

### Patterns to Follow

- ticket-001's git discipline, which is the precedent this ticket extends: staging by explicit path,
  one commit for one concern, and `--cached` wherever the index and the working tree must be treated
  separately. ticket-001 used `git rm -r --cached exemplo` precisely because the files had to stay on
  disk; here they must leave the disk, which is why the procedure is `rm` plus `git add --` rather
  than either form of `git rm`.
- `planning-context.md` decision 17 for the commit convention: one conventional commit per ticket,
  message in Portuguese focused on the why, ending with the executing session's attribution line,
  pushed to `origin main`, never force-pushed.
- The plan-wide "stop and report" discipline: four specialist escalations in epic 4 were each
  preceded by a measurement and each turned out to be right. A stop here is the ticket working, not
  the ticket failing.

### Pitfalls to Avoid

- Do not run this ticket before ticket-035. It deletes the parity check's reference implementation,
  and epic-04 learnings section 10 item 3 records the constraint in those words.
- Do not use `git rm`, `git checkout` or `git clean`, and never `git add -A` or `git add .`. The
  procedure is `rm` on thirteen enumerated paths followed by `git add --` on the same thirteen.
- Do not force-push, in any form.
- Do not delete anything outside the thirteen paths. In particular not
  `plano_dashboard_dessem.md`, not `logo/`, not `LICENSE`, not `settings.json`, not `docs/`, and
  nothing whatsoever under `exemplo/`.
- Do not create a `legacy/` directory. The ruling is delete outright, and its whole basis is that
  ticket-035's report already holds the evidence; creating the directory anyway would restore the
  problem the report solved.
- Do not re-investigate `__pycache__`. Measured: nothing tracked, `.gitignore` line 2 covers it.
- Do not compare the post-deletion test count against a number read from a document. Measure it
  immediately before deleting; it changed from 601 to 602 during this epic's refinement alone.
- Do not fix a failing test or a dangling reference found after the deletion. Report it: it would
  falsify the Background's measured claim that nothing references these files, and that is worth
  knowing.
- Do not write a README sentence that embeds a commit sha you cannot know before committing, and do
  not write one that asserts the files are still present.
- Do not touch `src/` or `tests/`. This ticket changes no behaviour.

### Out of Scope

- Any change to `src/`, `tests/`, `settings.json`, `pyproject.toml`, `.gitignore`, `CLAUDE.md`,
  `docs/checklist-manual-dashboard.md` or any plan document other than the two state files.
- Moving `plano_dashboard_dessem.md` (ruled: it stays at the repository root).
- Creating a `legacy/` directory or any archive of the removed code (ruled: delete outright, with
  the parity report as the record).
- The parity report's content (ticket-035) and the README's Legacy scripts subsection itself
  (ticket-036); this ticket adds one sentence to that subsection and nothing more.
- Any `__pycache__` investigation, tracked or untracked, beyond optional housekeeping.
- The epic-05 boundary quality gate, the learnings extraction and the final sign-off, which belong
  to the orchestrator after this ticket.

## Testing Requirements

### Unit Tests

None. This ticket writes no code.

### Integration Tests

None new. The verification is the existing suite, run in full after the deletion, plus
`tests/test_parity.py` run explicitly — ticket-035's Definition of Done proved that module passes
with `Leitura/` and `Plotadores/` moved aside, and this ticket is the real event that claim was
made about.

### Regression

Every test in the repository must pass **unchanged**, and the collected count must be identical
before and after. That is the falsifiable prediction this ticket makes: if the count or the result
changes, the Background's measured claim that nothing references the legacy modules was wrong.

## Definition of Done

- [ ] All five acceptance criteria pass.
- [ ] The pre-flight `git status --porcelain` was empty before any deletion, and its output is quoted
      in the completion report.
- [ ] The parity report's legacy inventory was read and verified complete **before** deleting, and
      the report says so.
- [ ] The thirteen paths were removed with `rm` on an enumerated list and staged with `git add --` on
      the same list; the report quotes both commands verbatim. No `git rm`, `git checkout`,
      `git clean`, `git add -A` or force-push was used.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests`,
      `.venv/bin/mypy src` and `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing`
      all exit 0, with total coverage at or above 85 percent and the collected count equal to the
      pre-deletion measurement, which the report quotes.
- [ ] `.venv/bin/pytest tests/test_parity.py -q` exits 0 with `Plotadores/` gone.
- [ ] The reference sweep returns only prose matches, in exactly the two files requirement 6
      names, with the `tests/test_parity.py` count unchanged from the pre-deletion measurement;
      its full output is quoted in the completion report.
- [ ] One conventional Portuguese commit containing exactly the thirteen deletions plus `README.md`
      and the two plan state files, pushed to `origin main` without a force flag.
- [ ] `plano_dashboard_dessem.md`, `logo/`, `LICENSE`, `settings.json` and every path under
      `exemplo/` are untouched, verified with `git show --stat HEAD`.

## Effort Estimate

**Points**: 1 · **Confidence**: High · **Agent time**: about 20 minutes, of which the 10-minute full
suite is half. Unchanged from the outline's 1 point: the editing work really is thirteen deletions
and one sentence. What refinement changed is that **both of the outline's open questions are now
closed with evidence rather than left to the implementer**. The `__pycache__` question was answered
by measurement (`git ls-files | grep -c __pycache__` returns `0`; `.gitignore` line 2 covers it) and
is dropped. The delete-outright-versus-`legacy/` question was answered by removing its premise:
the objection on the record was that the open cost-presentation decision's only evidence is
`Plotadores/Custos.py`, and ticket-035's parity report now transcribes that evidence — seven modules,
twelve `write_html` call sites, 21 output filenames, every axis and figure title with a `file:line`
reference, and the `(R$)`-versus-`10^3 R$` unit divergence — into a versioned document, which is why
requirement 2 makes that report's existence a hard precondition. Refinement also measured that
nothing in `src/`, `tests/`, `docs/`, `README.md`, `CLAUDE.md` or `pyproject.toml` references the
thirteen files, that all twelve importable legacy modules raise `FileNotFoundError` at import in this
environment, and that they sit outside every quality gate — so the deletion cannot break anything
that currently works. Confidence is High, and the effort is dominated by verification rather than by
editing, which is the right shape for an irreversible change.
