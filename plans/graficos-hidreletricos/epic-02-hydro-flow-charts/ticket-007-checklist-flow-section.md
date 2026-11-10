---
filesToBeCreated: []
filesToBeModified:
  - docs/checklist-manual-dashboard.md
filesToBeDeleted: []
agent: open-source-documentation-writer
tier: standard
implements: [R20, R24, R6, R13, R18, ADR-010]
---

# ticket-007: Manual checklist: SIN count and a new section 10 for the hydro flow charts

## Context

### Background

R20 requires new manual-checklist entries. They cover the SIN flow charts and the UHE order in all
four mode combinations: Por deck or Encadeado, each with Absoluto or Diferença. R24 requires the SIN
count to change from five to eight.

ADR-010 (which supersedes ADR-007) sets the one-way door: steps 1-32 keep their numbers and every
test-pinned string. Tests and release records cite them, for example `test_checklist_step_15_*` and
`exemplo_tree.py`'s "step 12". The pinned strings are:
- step 12's build command;
- `04/03/2024 12:00`;
- `MW (diferença)`;
- the seven group labels;
- the section 8 and 9 strings.

Only two edits are allowed in the existing text:
- the SIN count in steps 3 and 7 (five -> eight, measured from the SIN group count);
- one new sentence in the Purpose paragraph naming the 33+ range.

### Current state

`docs/checklist-manual-dashboard.md` has 259 lines, sections `## 1.` to `## 9.` and steps 1-32.
Section 9 is `## 9. Cost and time bar charts` (steps 27-32). It is the last section and has its own
build command.

The text says "five" for the SIN charts at line ~33 ("five initially visible SIN charts") and at
line ~56. Count the SIN charts with
`[s.key for s in enabled_specs() if s.group is ChartGroup.SIN]`, which gives 8 after ticket-004.
Import both names from `dessem_dashboard.charts.registry`. Filter by `group`, because scalar specs
have `level=None`.

### Target state

1. The two "five" occurrences that refer to SIN charts become "eight". They are in step 3's
   expected result ("five initially visible SIN charts", line ~33) and step 7's expected result
   ("the five SIN charts disappear", line ~56). Use the measured SIN group count, not a copied
   number. No other word in steps 1-32 changes, and no step is renumbered.
2. The Purpose paragraph lists each step range ("Steps 1 to 20 cover ... Steps 27 to 32 cover
   ..."). Append one sentence naming the new range, for example "Steps 33 onward cover the hydro
   flow charts of the SIN and `Usinas hidrelétricas` levels (plan graficos-hidreletricos)." Use the
   real last step number once section 10 is written.
3. Append `## 10. Hydro flow charts` after section 9, using section 9's format:
   - a one-sentence Purpose;
   - a build command:

     ```bash
     dessem-dashboard --casos examples/Oficial examples/Modificado --saida <scratch-dir>/dashboard-fluxos.html
     ```

     Check the real flag names in `cli.py` (`--help`). The `--casos` and `--saida` names above
     are unverified.
   - numbered steps 33 and up.
4. The steps cover:
   - (a) The SIN tab shows eight charts in R13 order: Geração Térmica ... Volume Armazenado, then
     Defluência, Turbinamento, Vertimento. Use the real titles from `specs.py`. Each shows one
     trace per scenario in m3/s.
   - (b) On the three SIN flow charts, Por deck with the Deck selector works in Absoluto, then in
     Diferença.
   - (c) The same charts work in Encadeado with Absoluto and with Diferença. The deck selector is
     disabled in that mode, following the wording section 3 uses.
   - (d) The Usinas hidrelétricas tab follows the order Geração, Volume Armazenado, Volume (%),
     Vazão Afluente, Vazão Incremental, Defluência, Turbinamento, Vertimento. Use the real titles.
     The plant filters still apply.
   - (e) For this example pair, Vazão Incremental in Diferença is a flat zero line. That is
     expected, because both cases share inflows. It is not a defect.
   - (f) Add `"QDEF_SIN"` to `charts.disabled` in a temporary copy of the settings, passed with
     `--settings`. Rebuild and confirm that Defluência disappears from SIN and the other two remain.
   - (g) The Submercado tab is unchanged and has no flow chart.
5. Run the build command for real, into a scratch directory outside the repository, before you
   write the expected results. Record the observed values in the ticket report: chart titles,
   counts, and whether the zero line appears. Do not write them as hard-coded data in the
   checklist beyond what the step needs.

## Dependencies

- **Blocked By**: ticket-006-real-data-flow-contract-test.md
- **Blocks**: ticket-008-checklist-section-10-guard-test.md

## Acceptance Criteria

1. **Given** the checklist, **when** it is diffed against `main`, **then**:
   - above section 10, the only changed lines are the two SIN-count sentences (steps 3 and 7) and
     the one added Purpose sentence naming the new step range;
   - steps 1-32 keep their numbers;
   - every test-pinned string listed in Background is byte-identical.
2. **Given** the file, **when** you search for the heading `## 10. Hydro flow charts`, **then** it
   appears exactly once, after `## 9.`, with steps numbered from 33 consecutively.
3. **Given** section 10, **when** it is read, **then** it contains all of these:
   - the four mode words `Por deck`, `Encadeado`, `Absoluto` and `Diferença`;
   - the three SIN flow titles;
   - the eight UHE titles in R13 order;
   - `charts.disabled` with `QDEF_SIN`;
   - the QINC flat-zero note.
4. **Given** `tests/test_renderer_contract.py` and `tests/test_charts_filters.py`, **when** they run,
   **then** every existing checklist guard test still passes.
5. **Given** the manual build, **when** it runs, **then** it exits 0 and writes only to the scratch
   directory. The report records the command and what was observed for steps (a)-(g).

## Files

| File | Change |
| --- | --- |
| `docs/checklist-manual-dashboard.md` | "five" becomes "eight" in steps 3 and 7; one Purpose sentence for the 33+ range; new section 10 appended |

## Technical Details

- Before writing, read sections 3, 4 and 9 for tone, the step format (action line plus an indented
  **Expected:** line), and how selectors such as `#value-toggle` are named.
- Write in English. UI strings appear verbatim in Portuguese, in backticks.
- Hydro-flow wording follows the master plan's amended C-SEM (`00-master-plan.md`, "Domain
  contracts"):
  - never call `Vazão Incremental` "natural" for every plant;
  - never state "Defluência = Turbinamento + Vertimento" as a definition;
  - in step (e), attribute the flat zero to the two cases sharing their inflow input, which is not a
    property of DESSEM.
- Run the existing checklist guard tests:

  ```bash
  .venv/bin/pytest tests/test_renderer_contract.py tests/test_charts_filters.py -q
  ```

- The full gate still applies, even though the change is documentation only: ruff check, ruff
  format --check and mypy src, then pytest in two background chunks with coverage at least 85%.

### Out of scope

- The README, which belongs to tickets 009 and 010.
- The guard test for section 10, which belongs to ticket-008.
- Renumbering steps 1-32.
- Rewording steps 1-32 beyond the SIN count in steps 3 and 7.
- Touching any test-pinned string (ADR-010).
- Synthesis-property checks such as QDEF = QTUR + QVER.

### Door, structure budget, debt

The decision is a one-way door (ADR-010): step ids and test-pinned strings are cited externally.
New steps are therefore appended, and the only edits to the existing text are the two count fixes
and the Purpose sentence. The ticket introduces no new structure and depends on no debt ticket.

## Definition of Done

- [ ] All five acceptance criteria are met, and the evidence for the manual run is in the report.
- [ ] The gate is green and coverage is at least 85%.
- [ ] The manual run wrote nothing to the repository's `output/` or `logs/`. Pass `--saida` into
      a scratch directory, and note that logs go to the repository `logs/` through
      settings-relative resolution. To avoid that, use a temporary settings copy whose
      `paths.log_dir` and `logging.file` point to the scratch directory.
- [ ] Commit message (Portuguese): `docs: adiciona ao checklist os gráficos de vazão`.
