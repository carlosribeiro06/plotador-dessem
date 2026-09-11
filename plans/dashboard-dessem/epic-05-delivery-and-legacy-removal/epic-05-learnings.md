# Epic 5 learnings — Delivery and legacy removal

> Written at the epic-05 boundary by the orchestrator. Epic 5 is the last epic, so these learnings
> feed the plan completion protocol rather than a later refinement. Every number here was measured
> during the epic; where a number came from a document rather than a run, the document is named.
>
> Section 6 is deliberately about the orchestrator's own errors. Four of the five defect classes
> this plan kept finding are classes of **unmeasured claim**, and the orchestrator produced five of
> them in epic 4 alone. Recording them is the only mechanism that has actually reduced them.

## 1. The epic's shape: five tickets that verified, one that changed behaviour

Epic 5 was specified as delivery — wire the pipeline, test it on real data, prove parity, document
it, polish the CLI, delete the legacy. What it turned out to be is **one behavioural fix and five
acts of verification**, and the single behavioural fix was found by verification rather than by
implementation:

| Ticket | What it was specified as | What it actually produced |
| --- | --- | --- |
| 033 | Wire the end-to-end pipeline | The real chain replacing the stub; **the first run over real data in the plan's history** |
| 034 | Add an example-data integration test | Skip-guarded real-data tests; a guardian **rejection** over a skip message that named neither the env var nor the default path |
| 035 | Run the legacy parity check | A 289-line report and 868 lines of independent-recomputation tests; **four legacy defects marked NOT REPRODUCED** |
| 036 | Write user documentation | A README rewritten from scratch in English; the 12-file chart-count blast radius measured, not estimated |
| 037 | Polish CLI usability and errors | **The only shipped-code defect of the epic**: the log went to stdout, so the documented `saida=$(...)` contract was false |
| 038 | Remove the legacy scripts | Thirteen deletions gated behind three stop-and-report checks |

The lesson is not that verification found a defect. It is **where** it found it: ticket-036 wrote
the README sentence promising that a successful run prints exactly the output path, and ticket-037
was the first ticket to run the shipped binary in a subprocess with the streams separated. The
promise and its first measurement were one ticket apart. A promise written in ticket N and first
measured in ticket N+1 is the plan's most productive defect-finding pattern, and it is also an
indictment: had 036 measured its own sentence, the defect would have been found a ticket earlier.

## 2. The defect that survived because one test module disagreed with production

`tests/test_cli.py`'s `_settings_dict` hardcodes `"use_rich": False`. It is **the only module of
eighteen that does** — measured after the fix, not assumed. `test_cli.py` is also the only module
that drives `cli.main` end to end. So the single module exercising the full entry point was the
single module that detuned the logging configuration, and the shipped configuration's code path was
never executed by any test.

Under the shipped `settings.json`, a real subprocess run produced **47 lines of log on stdout and
zero on stderr**, with the output path last. After the fix: **stdout exactly one line, exactly the
path; stderr 52 lines; exit 0** on a degraded run.

The mechanism is one keyword argument. `RichHandler()` with no `console=` builds a default
`Console()`, which writes to stdout. The plain-`Formatter` fallback (`logging.StreamHandler()`)
already went to stderr. So **the defect existed only in the configuration every real run uses**,
and only when `rich` was installed — which is to say, only in production.

Three transferable rules:

1. **A test fixture that differs from the shipped settings file is a hole in the shape of the
   difference.** Not a style issue. The remedy that shipped is a second test building its own local
   copy with `use_rich: True`, because changing the shared `_settings_dict` would have rewritten
   the expectations of every test in the module.
2. **When a docstring claims a fixture matches the repository's values, check it.** Spec defect 20
   was the same fault in the same file: `_settings_dict`'s docstring claimed to mirror repository
   values while hardcoding `time.stage_groups = {"PL": ["PL"]}` against a shipped three-group
   default. Residue was found in **eleven** modules. The fix was to correct **the docstring, not the
   value** — changing `stage_groups` would move the TEMPO bar count and invalidate
   `test_output_size.py`'s measured byte range.
3. **Assert the stream, not the handler type.** A test asserting `use_rich=True` selects a
   `RichHandler` already existed. Nothing asserted *where that handler writes*. That is defect
   class (c), a correspondence with no owner: the type is chosen in one place and the stream matters
   in another, and no test owned the pairing.

## 3. Parity by independent recomputation, because the reference could not run

The legacy tool **cannot be executed in this environment**. `Leitura/leitor_arquivos.py:9`
hard-codes `C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo` and iterates it at
module level on line 13, so importing it raises `FileNotFoundError` — and all twelve other legacy
modules carry `from Leitura.leitor_arquivos import *`, so every one of them fails at import.

This turned a comparison problem into a transcription problem, and the shape of the answer is worth
keeping:

- **Transcribe each legacy constant once, with a `file:line` provenance comment**, then recompute
  the quantity independently in pandas and compare. `tests/test_parity.py` is 868 lines and 15
  tests built this way.
- **Prove the independence rather than claiming it.** The module was run with `Leitura/` and
  `Plotadores/` moved aside; it passed. That single experiment is what makes the fifteen provenance
  comments provably comments rather than references — and it is what licensed ticket-038 to delete
  the reference implementation at all.
- **Pin the absolutes.** `_REFERENCE_CUSTOS_PRESENTE = 58667.5674`,
  `_REFERENCE_CUSTOS_FUTURO = 228420390.34615`,
  `_REFERENCE_CUSTOS_TOTAL_AT_TWO_DECIMALS = 228479057.92`.
- **Four legacy behaviours were marked NOT REPRODUCED**, deliberately. Parity is not bug-for-bug
  compatibility, and saying which divergences are intentional is the part of a parity report that
  has value after the legacy is gone.

The report's section (d) presents both presentation collapses — the legacy emits three cost figures
and four time figures where the dashboard ships one each — with evidence and options, and **chooses
neither**. That is the correct output for a decision that belongs to the developer, and it is why
ticket-038 could delete the scripts: the evidence moved into the working tree as prose.

## 4. The ruling that made an irreversible deletion safe

The recorded objection to deleting outright was concrete: the open cost-presentation decision's
"only evidence is `Plotadores/Custos.py`", so deleting would leave it recoverable from git history
but **not discoverable by someone reading the working tree**.

ticket-035 did not answer the objection; it **removed the objection's premise** by transcribing the
evidence into a versioned document — seven modules, twelve `write_html` call sites, 21 runtime
output filenames, every Y-axis and figure title with a `file:line` reference, the verbatim scalar
formulas, the four defects, and the `(R$)`-versus-`10^3 R$` unit divergence. Only then did
"delete outright" become the cheaper option, and ticket-038's requirement 2 made that document's
existence a **hard precondition verified before anything is removed**.

Transferable: when an irreversible step is blocked by an evidence objection, the productive move is
usually to relocate the evidence, not to argue about the objection's weight or to compromise on a
`legacy/` directory that adds a second place to look.

## 5. Spec defects found in epic 5, and the one new shape

Epic 5 contributed defects 22 through 25. Three repeat known shapes; one is new.

| # | Ticket | Shape | What it was |
| --- | --- | --- | --- |
| 22 | 033 | **New: a criterion with no assigned owner** | Acceptance criterion 2 had **no assigned test** in the ticket's own Testing Requirements. |
| 23 | 034 | Claim about the suite, unmeasured | DoD said "reports four skips" while Testing Requirements designed one of the tests to always pass. |
| 24 | 036 | Claim about a measurement method | AC4 said "re-measured by grep" while the Approach and DoD mandate scratch-copy-and-run and state grep undercounts, 7 versus 12. |
| 25 | 038 | Claim about the repository, stale | Background asserted the legacy-reference sweep "returns no match" — falsified **by ticket-035 and ticket-036 inside the same epic**, after 038 was refined. |

**Defect 22 is the new shape and the one worth carrying forward.** Readiness scoring gave ticket-033
a 1.00 and **could not have caught it**: scoring checks that acceptance criteria are *verifiable*,
not that each one has been *assigned a verifier*. Those are different properties, and only the
second is a plan invariant. The gate added for it is: **every acceptance criterion must have some
named verification somewhere in the ticket.** Note the wording — the orchestrator's first version
of this gate required the criterion to be "referenced by number" and produced **two false positives**
when applied to tickets 034–038. A gate that fires on formatting rather than on substance is worse
than no gate, because it trains the reader to dismiss it.

**Defect 25 is the shape a progressive plan is structurally exposed to.** Epic 5 was refined
just-in-time, so its tickets were written against a repository state that its own earlier tickets
then changed. The Background bullet was true when written and false when read. The remedy that
worked is mechanical: **at dispatch, re-measure every claim the ticket makes about the repository**,
because the measurement is cheap and the failure mode is expensive — a literal-minded implementer
could have satisfied the original requirement 6 by deleting the parity check's fifteen provenance
comments, destroying the audit trail to make a grep quiet.

## 6. Orchestrator errors in this epic, and the one that matters most

Recorded for audit, in the order they were made.

1. **`status: completed` written while a guardian was still running** (ticket-034), paired with
   `workflow_step: guardian_pending` as if the two fields hedged each other. They do not: `status`
   is what the Stop hook and the progress count read, so the plan asserted 34/38 for an unverified
   ticket. **Rule: the state file and the plan README move together, and only after verification.**
   The ticket-034 guardian flagged it, and scored 0.95 rather than 1.00 so the rejection stays
   visible in the plan's own record.
2. **A state/README divergence of the same family at ticket-037**: the state write succeeded, then
   its own README regex assertion failed (`expected 1 ticket-037 row, matched 0`) because the row
   title is "…and error **messages**", not "…and errors". Caught by the assertion, fixed in the
   same turn. The assertion earned its keep: a script that writes two files should verify both, and
   this one did.
3. **A stale duration repeated into six dispatches.** "About 5 to 5.5 minutes" was written into six
   specialist briefs and ticket-032 claimed "about 220 s"; the measured suite was **564 s, 618 s
   and up to 674 s**. Corrected with both measurements cited. A duration is a measurement with a
   date, and this plan's duration tripled while the sentence stayed the same.
4. **The wrong mechanism asserted to a guardian.** The orchestrator told the ticket-037 guardian
   that pytest's logging capture intercepts the handler, making the stdout defect untestable. The
   guardian **disproved it by experiment**: `capsys` captures the pollution fine under
   `use_rich: True`. The real cause was narrower and worse — `test_cli.py`'s hardcoded
   `use_rich: False`. A guardian that runs an experiment beats an orchestrator that reasons about a
   mechanism, and the correct response is to verify the correction independently, which was done
   (one module of eighteen).
5. **An inverted precision note in ticket-035**: the orchestrator wrote that the dump's
   `N unique -> [...]` line is truncated and the sample rows carry full precision. The opposite is
   true. The ticket-035 specialist caught it **by measuring the dump**.

The meta-lesson, which the epic-04 boundary stated and epic 5 confirmed four more times:
**measuring that a string is absent is not measuring that a fact is unverifiable**, and reasoning
about a mechanism is not measuring it. Every one of these five was corrected by somebody running a
command.

## 7. Facts about this repository worth keeping

- **The suite takes about ten minutes.** Measured 412–674 s across runs this plan; the most recent
  pair was `pytest -q --no-cov` at 314.61 s and `pytest --cov` at 478.35 s. 637 tests after
  ticket-037, 99% total coverage, `cli.py` at 100%, `logging_setup.py` at 95% (the two missed lines
  are the unreachable `except ImportError: pass`).
- **Run coverage and the plain suite as separate steps.** A combined full-suite-with-coverage run
  was killed twice by the harness for low system memory — a Windows-side precaution, not a Linux
  OOM (the editor stack holds 5.7 of 15 GiB; 6.8 GiB free inside WSL).
- **There is no `fail_under` anywhere.** The coverage floor is a convention the plan enforces by
  reading the number, and ticket-036's README says so honestly. Adding `fail_under` would make that
  README sentence false and must be done in the same change.
- **Real-data figures, first run of the plan:** zero warnings on the documented pair,
  `bytes_html = 8,307,555`, `valores = 618,372`. Extrapolated to 3 scenarios × 30 decks the
  controlled share is **~90 MiB** — labelled an estimate, and enough that `output.size_warning_mb`
  will genuinely fire on a realistic study.
- **`exemplo/` is untracked** (`git ls-files exemplo` → 0) and holds 240 irreplaceable local Parquet
  files. The only quotable source of real-data figures is the committed
  `plans/dashboard-dessem/reference/parquet-schemas.txt`.
- **Two orphaned worktree directories** sit under `.claude/worktrees/`, each a full copy of the
  repository including the legacy files. `git worktree list` registers only the main tree and
  `.git/info/exclude:9` hides them, so they cannot be staged — but an unscoped `grep` hits them and
  reads as a failed deletion. Scope every sweep.
- **`grep -rn` without `-I`** reports binary matches in `tests/__pycache__/*.pyc`. Use
  `-I --exclude-dir=__pycache__` on any reference sweep.

## 8. Open items handed to the developer

These are recorded in `.implementation-state.json` under epic-05's
`open_decisions_for_developer` and are **decisions, not defects** — each has evidence and options
and deliberately no chosen answer.

1. **The two presentation collapses.** The legacy emits three cost figures and four time figures
   where the dashboard ships one each. The cost of splitting was **measured at 12 files**, not the 7
   a grep suggests.
2. **The `10^3 R$` cost-unit correction.** `FALLBACK_UNITS["CUSTOS"]` went from `"R$"` to
   `"10^3 R$"` on three verified anchors, with the arithmetic in a comment at the constant. It is
   reversible in one line if the developer's domain reading disagrees.
3. **The cost scale.** `PRESENTE ≈ 5.87e4` against `FUTURO ≈ 2.28e8`, both `10^3 R$` — about four
   orders of magnitude in one bar chart. A log axis is ruled out because it cannot render a signed
   Diferença.
4. **Plant labels carry the name without the code**, and `output.decimals` is global.
5. **Whether to add `fail_under`** — see section 7; it cannot be added without editing the README
   sentence in the same change.
6. **The human browser walk** of `docs/checklist-manual-dashboard.md` (9 sections, 32 steps) remains
   outstanding **by design** under E3-1. It is the only behavioural gate in the plan that no agent
   can close, and the epic-04 boundary strengthened it: the note telling operators that empty chart
   areas were correct was deleted, and step 30's invented "tens to a few hundred" minutes band was
   replaced by the measurable relation `TOTAL == MILP + PL + Leitura`.

## 9. The boundary fan-out, and what a zero-edit simplifier pass is worth

### 9.1 `code-simplifier`: three files, zero edits, twelve recorded rejections

The epic changed three source files — `pipeline.py`, `cli.py`, `logging_setup.py` — and the
simplifier changed **nothing**. That is the correct outcome for files two tickets and two guardians
had just gone over, and the pass still earned its cost, because **the twelve candidates it
considered and rejected are the reusable output**. A future pass that re-proposes any of them is
repeating work already done and answered.

The rejections worth keeping, each with the reason it is not a simplification:

- **Deriving the CLI's `_LOG_LEVELS` from `logging_setup._VALID_LEVEL_NAMES`**, to remove a
  duplicated list of five level names. `_VALID_LEVEL_NAMES` is a `frozenset`, so feeding it to
  argparse `choices` is either non-deterministic in `--help` or, if sorted, **reorders the
  user-facing list from severity order to alphabetical** — a visible change to a user-facing string,
  which Rigoroso mode puts out of bounds for a cleanliness pass. Duplication across a public
  boundary is sometimes the cheaper contract.
- **Dropping the `rich_handler: logging.Handler` annotation** as inferable. `mypy` runs
  `strict = true` with no per-module overrides and `rich` is an optional `try`-guarded import, so
  the annotation plausibly holds `warn_return_any` quiet where `rich` resolves to `Any`. The
  simplifier has **no Bash tool and therefore cannot run `mypy`**, and it declined to trade a
  one-word gain for a possibly failed gate. Knowing the limits of your own verification is part of
  the judgement.
- **Hoisting the duplicated `data.warnings()` call** in `pipeline.run`. It returns a fresh tuple
  from an in-memory list, so the duplicate is free, and the two uses differ: `len(...)` for the log
  field, `list(...)` for `RunResult`. Extracting a local adds a line and removes nothing.
- **Trimming `_log_warnings`' six-line docstring** as excessive for a private function. Five of its
  six lines are *why* — `add_warning` only appends to a list, so without this call an operator
  watching the console sees nothing — plus the documented cap-overflow behaviour. `D` (pydocstyle)
  is not among the selected ruff rules, so nothing forced it: it was written deliberately.
- **Extracting helpers out of `cli.main`.** A CLI entry point reading as a linear script is the
  right shape, and `params` is built *before* `start = time.perf_counter()` precisely so the
  measured `elapsed_s` covers only `pipeline.run`. Extraction would blur that.
- **Unifying the two "default when `None`" styles** in `cli.main` (a ternary for `reference`, an
  `if` block for `output_file`). The `output_file` default spans two attribute lookups and a path
  join, so the ternary form would wrap across three lines and read worse. A consistency preference,
  not a simplification — and `or` is not a valid shortcut here.
- **Narrowing `_resolve_labels`' return type** to the keys the caller actually uses. That is a
  signature change, out of bounds for this pass, and `label -> directory` is the domain concept even
  where the values are currently write-only.

### 9.2 The one finding the simplifier reported instead of acting on

`cli.main` calls `output_file.parent.mkdir(parents=True, exist_ok=True)` while `write_dashboard`
documents that it creates the parent directory itself, so the call looks redundant. It is not, and
the simplifier correctly classified removing it as **not behaviour-neutral**:

1. The directory exists even when discovery or consolidation raises, so the run manifest has
   somewhere to land on a failed run.
2. It **fails fast on an unwritable `--saida`**, before minutes of Parquet reading.

Keep both. This is the shape of apparent redundancy that is really a cheap early check, and
reporting it was the right move: a simplifier that cannot run the suite should never make a change
whose safety depends on running the suite.

## 10. What the boundary review found that no per-ticket gate could

`code-reviewer` on the committed epic diff returned **NEEDS_ATTENTION**: 0 critical, 3 important,
7 minor, from 14 findings considered. It re-ran the gate itself first — 637 passed, 99%, 508.89 s —
and confirmed that every correctness claim the epic made holds under measurement: the end-to-end
wiring, the parity recomputation, the stdout contract and the legacy removal. What it found was one
real defect and a set of documentation and assertion tightenings, all ten of which were applied at
the boundary.

### 10.1 The defect: the same shape as ticket-037's, one sink over

`_log_warnings` caps the logged warnings at `_MAX_LOGGED_WARNINGS = 20`, and that logger feeds
**both** the console handler and the `RotatingFileHandler`. So warnings 21..n never reached the
**log file** either — while the truncation line written *into that file* said they were omitted
`no console`, implying the file had kept them. Measured by driving `_log_warnings` with 25 messages:
20 in the log file, and the file itself blaming the console for the missing five.

This is **defect class (c) — a correspondence with no owner** — and it is precisely the shape of
ticket-037's stdout defect, one sink further on. Both halves were individually correct: the cap
works, and the message is well-formed. Nothing owned the pairing of *what the message claims* with
*what the file handler actually keeps*. The existing test asserted on `caplog` records only; its
sibling test does read `logs/dashboard.log`, but only in the under-cap case, where the discrepancy
cannot appear.

**Ruling: fix the message, not the logging architecture.** The complete list genuinely survives in
`run_manifest.json` and the dashboard's Avisos section — both named in the message itself — so no
audit trail is lost; the only false thing was one clause. The message now names both sinks. The
alternative (cap the console through a `logging.Filter` and let the file take every warning) was
**deliberately not implemented** and goes to the developer as an open decision: re-architecting
handlers at the close of a plan, for something one string makes true, is the larger risk.

The missing assertion was added at the point where the correspondence lives: the test now reads
`logs/dashboard.log` and proves it holds exactly twenty individual warnings plus the truncation
line.

### 10.2 The finding line coverage structurally cannot see

`cli.py` passes `initial_mode=args.modo_inicial` to `pipeline.run`, and **no test drove that flag
through `main`**. Delete the keyword argument and all 637 tests still pass with `cli.py` still at
**100% line coverage** — because line coverage cannot see an *omitted keyword argument*. The shipped
tool would then write `data-initial-mode="encadeado"` while `run_manifest.json` recorded
`modo_inicial: "deck"`: an audited artefact disagreeing with its own manifest.

That is worth stating plainly, because this plan leaned on coverage as a gate throughout: **100%
line coverage of a call site says nothing about the arguments at that call site.** The fix pins the
flag → manifest → document triple in one test, and it was proved to fail by removing the keyword
argument before restoring it.

### 10.3 Two documents falsified by the epic's own later commits

- The README's **quality-gate table** still read `631 passed ... 1543 statements` while ticket-037's
  own commit message, three hunks away in the same file, said 637. The commit edited `README.md`
  and left the table alone.
- The README's **"15 `log_step` lines per run"** cannot be true of every run: three of the line
  groups scale with scenarios and decks, so a two-scenario two-deck run writes **25**. Re-measured
  independently at the boundary and reworded as a formula with a worked number.

Both are the same shape as spec defect 25, which the same epic produced: **a measured number
written into a document, and a later change in the same epic that moved it.** The transferable rule
is not "check the README at the end" but rather: a document that quotes a measurement should say
what produced it, so a reader can re-run it instead of trusting it.

### 10.4 Assertions that could not fail, and one that could not fail *usefully*

- `assert warnings is not None` on a field declared `list[str] = field(default_factory=list)`.
  Unconditional. Deleted.
- `assert sum(tempo_values) == sum(_REFERENCE_TEMPO_SECONDS)` on the line after
  `assert tempo_values == _REFERENCE_TEMPO_SECONDS`. Equal tuples have equal sums, so no
  implementation change can fail one and pass the other — yet the docstring advertised the nine
  values "and their sum" as two pinned facts. Deleted, and the docstring corrected to claim one.
- `assert "5" in truncation_message` — **mutation-insensitive rather than vacuous**, which is worse
  because it reads like a real check. Changing `omitted = len(messages) - _MAX_LOGGED_WARNINGS` to
  `omitted = len(messages)` makes the audit log say `25 aviso(s) ... omitido(s)` when five were
  omitted, and the substring check still passes. Replaced with a delimited comparison and proved to
  fail under exactly that mutation.

### 10.5 Two fixture docstrings, and why the docstring is what gets fixed

`tests/test_pipeline.py`'s `_settings_dict` claimed to match "the repository's own values" while
shipping `time.stage_groups = {"PL": ["PL"]}` against the shipped three-group default — **spec
defect 20's shape, recurring in a module written after that defect was recorded**, because the new
module copied `test_renderer_contract.py`'s pattern without copying its correction.
`tests/test_cli.py`'s twin documented its `logo_file` divergence but stayed **silent about
`use_rich: False`**, the single detuned key whose silence hid the stdout defect through eight
guardians.

Both were fixed in the docstring, never in the value, for the reason epic 4 recorded: changing
`stage_groups` would move the TEMPO bar count and invalidate `test_output_size.py`'s measured byte
range, and `use_rich: False` is required by ticket-037 while a separate test covers the shipped
`True`. **A fixture that diverges from the shipped settings is fine; a fixture that diverges
silently is the hole.**

### 10.6 The guard whose failure mode is silence

`tests/exemplo_tree.py`'s `_has_sintese_deck` claimed to mirror `discovery._decks_of` *exactly* but
adds a requirement that `EST.parquet` exist, and hardcodes the `sintese` directory name while the
integration module reads it from the shipped `settings.json`. The divergence direction is the
dangerous one: a **stricter** guard makes `qualifying_scenarios()` return too few paths, and then
every real-data test reports SKIPPED **while the suite stays green**. Discovery itself would have
raised loudly; the guard converts a loud failure into a quiet one. Corrected in documentation, with
the direction named.

### 10.7 A false alarm designed out before it could cost anything

Group B's TEMPO recomputation mirrors `Plotadores/Tempo.py`'s `.values[0]` for `Leitura` and `MILP`
and sums the PL group. The committed dump shows nine rows over five etapa names in one execution, so
an etapa already repeats on the reference deck — Group B passes only because the repeats land on the
summed names. A future deck logging two `MILP` rows would have the pipeline sum them (correct) while
the helper took the first, producing a "TEMPO diverges" failure pointing at a parity regression that
does not exist. Expensive, because ticket-035 requirement 10 forbids editing source to make such a
failure pass.

The fix keeps the legacy mirror and adds an explicit one-row precondition at each single-row read,
with a message naming the legacy semantics and pointing at the Group C test that owns the proof that
the shipped pipeline sums repeated rows. **A future failure now explains itself instead of
masquerading as a regression.**

### 10.8 The reviewer's false positives, which are worth as much as its findings

Five, each recorded with what made it look like a defect:

- **"The absolute pins are at unreproducible precision."** They are not: the dump's values are
  shortest-repr float64 strings that parse back to the identical double, and `round(x, 2)` returns
  the double nearest the correctly-rounded decimal, which is what the literal parses to.
- **"Group B never actually runs, so parity is unproven."** Disproved by measurement:
  `pytest tests/test_parity.py -q -rs` reports 15 passed with **no skip lines**, and the full suite
  reports zero skips — the real-data tests, the pinned Appendix-A volumes and the reference-deck
  pins all executed.
- **"`assert not all(_matches_known_warning_shape(...))` is vacuous."** Unfalsifiable by the
  product, and deliberately so: it guards the `all(...)` above it from degenerating into "accepts
  anything".
- **Byte reproducibility** was filtered out as a latent risk rather than a finding, because the
  artefact was **measured** reproducible: two CLI subprocesses under `PYTHONHASHSEED=1` and `777`
  produced byte-identical 4,531,704-byte documents. The in-process comparisons in
  `test_builder.py` and `test_output_size.py` genuinely cannot detect hash-seed ordering; a
  subprocess pair is the cheapest guard if one is ever wanted.
- **Mode compliance** was checked in both directions and found clean: identifiers, comments,
  docstrings, skip reasons and assertion messages English; the only Portuguese user-facing — the
  `--help` epilog, log and warning text, and the `ConfigError` stderr message.

### 10.9 The boundary's own numbers

Ten fixes applied, one source line changed (the message string), eight files touched, and the three
mutation-proofed fixes each shown failing before being restored. Gate after the boundary:
`ruff` clean, `mypy` clean on 26 source files, **638 passed** — up by exactly the one test added —
at **99%** coverage, 441.41 s. The orchestrator re-ran lint, types and the four affected modules
independently (46 passed, zero skips) before committing.
