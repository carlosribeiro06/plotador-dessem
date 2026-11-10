# Council brief questions — operator answers (2026-11-09)

Rendered by `/plan` P2 after the `design-council` brief stage. The four seats
(`dessem-specialist`, `python-task-automation-developer`, `test-strategist`,
`open-source-documentation-writer`) all returned a brief; no seat was dropped. Every seat chose
`simplestViable` with `reversibility: two-way`. Their `questionsForUser` were batched into one
operator gate; the answers below are binding for SYNTHESIS.

| # | Seat | Question (summary) | Operator answer |
| --- | --- | --- | --- |
| A1 | dessem-specialist (K1), test-strategist | Should the real-data suite also carry synthesis-property checks (SIN = ΣUHE, QDEF ≥ QTUR+QVER, QAFL ≥ QINC, flows ≥ 0)? | **No.** The real-data test asserts the dashboard contract only (section order, 1 entity + `m3/s` per SIN flow chart, subtitle = `METADADOS_OPERACAO.nome_longo_variavel` read from the file, payload values = file `valor` rounded to `output.decimals` on the deck axis and on the first `chaining.stages_per_deck` chained stages, zero warnings; every size measured from the files). The inequality forms stay recorded in the dessem brief for a later decision. |
| A2 | test-strategist | Assert `QDEF_SIN == QTUR_SIN + QVER_SIN` on the payload? | **No.** Per the dessem-specialist's contract C3: DESSEM defluência includes a diversion term (MM 22.3.0 §9.6); the equality is a synthesizer/deck property, not an identity. Never assert it, nor `QINC Diferença == 0`. |
| A3 | python-task-automation-developer | Shape of the R27 fix | **Option A.** Thread a required `fictitious_codes` keyword into `registries.load_registries` (drop the hard-coded `(11, 99)` default from the signature); `consolidate._load_registries` passes `settings.submarkets.fictitious_codes` on both call sites; regression test included. Option B (moving classification into `visible_submarket_codes`, removing `Submarket.fictitious`) is rejected as beyond R27's confirmed wording. |
| A4 | test-strategist (K2) | Fixture `METADADOS` fidelity gap (long name == title; rows for `CUSTO_*`/`TEMPO_*`) | **Recorded as technical debt, not fixed in this plan** (default confirmed by silence at the gate; no new requirement). |
| A5 | open-source-documentation-writer | `cli.py` still points operators to the removed `Avisos` section (Portuguese log message), and the `_MAX_LOGGED_WARNINGS` comment carries the stale 23/92 counts; `tests/test_cli.py:589` pins the `Avisos` wording | **Fold into the R25 cleanup ticket of the feature epic**: message points only to `run_manifest.json`, comment/docstring updated (counts become 26/104 or are dropped), test assertion updated. Small code + test change, owned by the Python developer. |
| A6 | open-source-documentation-writer | README `Avisos: the eight warning shapes` — delete or re-home? | **Re-home under `## Logging and auditing`**, rewriting its intro (the eight shapes still reach console, log and `run_manifest.json`; only the dashboard section is gone) and re-checking shape 7 after R27. |

Earlier operator decisions (clarification loop) are recorded in `../intake.md` under
"Clarification answers" and are not repeated here.
