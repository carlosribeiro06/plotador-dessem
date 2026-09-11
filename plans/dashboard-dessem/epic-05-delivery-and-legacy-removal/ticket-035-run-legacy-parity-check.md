# ticket-035 Run the legacy parity check

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-034 and strictly before ticket-036. It must never be
> reordered after ticket-038**, which deletes `Plotadores/` — this ticket's reference implementation.
> **Data handling.** As in ticket-034, `exemplo/` may be **run over** but never transcribed, so the
> real-data verification is expressed as *assertions comparing two computations of the same data*,
> which never emit a value. **One source of real figures is authorised and is used here**:
> `plans/dashboard-dessem/reference/parquet-schemas.txt`, a committed 933-line dump of the reference
> deck `exemplo/2024-03-03/caso_oficial/sintese` — which `planning-context.md` decision 15 verified
> byte-identical by blob hash to `exemplo/caso_oficial/2024-03-03/sintese`. Figures quoted from that
> file, with the file cited, are measured. Spec defect 17 was a magnitude quoted from data its author
> could not read at all; quoting the committed dump is the fix the epic-04 boundary review applied.

## Context

### Background

Master plan decision 12 and goal 6 make the legacy scripts deletable only "after a parity check",
to protect against silent behaviour regressions. Appendix A.7 lists what must be preserved: the
`GHID_SIN` and `GTER_SIN` line charts; `GHID_SBM`, `GTER_SBM` and `CMO_SBM` for submarkets 1 to 4;
`CUSTOS` bars with presente, futuro and total; `TEMPO` bars with MILP, the PL group, Leitura and
total **in minutes**; the look (white plot background, light-gray grid, Arial 12,
`hovermode="x unified"`, x tick format `%d/%m/%Y %H:%M`); the first-48-stage chaining; and one known
intentional divergence, the datetime axis of decision 14 replacing `type='category'`.

**The method question the outline left open is settled by measurement: the legacy scripts cannot be
executed in this environment, so the check is an independent recomputation plus a documented
presentation comparison, and the legacy source is read as a specification rather than run.** Three
independent reasons, each verified:

1. `Leitura/leitor_arquivos.py:9` hard-codes
   `Path("C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo")` and iterates it at
   **module level**, line 13. Measured:
   `.venv/bin/python -c "import Leitura.leitor_arquivos"` raises
   `FileNotFoundError: [Errno 2] No such file or directory: 'C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo'`.
   All twelve legacy modules — the seven `Plotadores/*.py` and the five `main_*.py` — carry
   `from Leitura.leitor_arquivos import *` exactly once each (measured with `grep -c`), so **every
   one of them fails at import**.
2. The scripts require the **date-first** layout `exemplo/<data>/<caso>/sintese`, and the tree is
   scenario-first since `planning-context.md` decision 15 rebuilt it as
   `exemplo/<caso>/<data>/sintese`. Under the current layout `leitor_arquivos` would build
   `casos = {"caso_oficial": ["2024-03-03", "2024-03-04"], "caso_gurobi": [...]}` — scenario names
   as dates and deck dates as case names — and `Plotadores/Custos.py:29`
   (`df_cp['Datas'] = pd.to_datetime(df_cp['Datas'])`) would then be asked to parse
   `"caso_oficial"` as a timestamp.
3. Two of the five drivers are only accidentally correct, so editing them to run is not a mechanical
   fix. `main_custos.py:17` unpacks `df_cp, df_cd = gera_df_custos(...)` and line 19 calls
   `df_plot_custos(df_cp, df_cf)` — `df_cf` resolves only because
   `from Plotadores.Custos import *` also imported the module-level `defaultdict` that
   `gera_df_custos` mutates. `main_tempo.py:17` binds `df_tempo_milp, df_tempo_pl, df_tempo_leitura`
   and line 19 passes `df_pls`, the star-imported global, instead of `df_tempo_pl`.

Making them run would mean editing legacy code, which decision 12 exists to avoid, and would
produce a *modified* reference — the worst of both worlds. Recomputing the legacy formulas
independently, with the same pandas expressions read from the legacy source, gives the same
numerical guarantee with no edit and no hidden state.

**The tension this ticket inherits, and must not resolve by arithmetic alone.** Recorded in
ticket-030's Context and in `.implementation-state.json`'s epic-04 dispatch notes:
`Plotadores/Custos.py` emits **three** separate figures with the Y-axis titles `Custo Presente (R$)`
(line 34), `Custo Futuro (R$)` (line 52) and `Custo Total de Operação (R$)` (line 77), each on its
own axis. The new dashboard ships **one** grouped bar chart, deliberately — the catalogue has one
`_scalar("CUSTOS", "Custo Presente, Futuro e Total")` entry and `planning-context.md` says "bars per
deck" — and on a shared linear axis one series may be invisible where the legacy gave it its own
axis. **The parity check must not be read as passing merely because the totals agree.**

Refinement found the **same shape a second time, and it is not yet recorded anywhere**:
`Plotadores/Tempo.py` emits **four** separate figures, `title="Tempo MILP"` (line 33),
`"Tempo PL"` (line 51), `"Tempo Leitura de Dados e Impressão"` (line 69) and `"Tempo Total"`
(line 94), each with `yaxis_title='Tempo em Minutos'`. The new dashboard ships one
`Tempo Computacional` grouped bar chart with the four series `MILP`, `PL`, `Leitura` and `TOTAL` on
one axis. So the presentation collapse is 3→1 for costs **and** 4→1 for times, and both belong in
the report.

### Relation to Epic

The gate ticket-038 waits for, and the reason the epic's order is fixed. It produces the two
artefacts the rest of the epic depends on: an automated parity test that survives the deletion, and
a report that **transcribes the legacy behaviour into a document**, which is what makes deleting
`Plotadores/` outright safe rather than lossy (ticket-038's Definition of Done checks for that
transcription before it deletes anything).

### Current State

The legacy inventory, measured from the source as it stands. Twelve `fig.write_html(...,
include_plotlyjs="cdn")` call sites across seven modules produce **21 output HTML files** per run,
because the three submarket plotters loop `submercados = [1, 2, 3, 4]`:

| Legacy module | Figures per run | Y-axis title(s) | Output filename(s) |
| --- | --- | --- | --- |
| `Plotadores/Ghid_SIN.py` | 1 | `Geração Hidráulica (MW)` | `grafico_ghid_sin.html` |
| `Plotadores/Gter_SIN.py` | 1 | `Geração Térmica (MW)` | `grafico_gter_sin.html` |
| `Plotadores/Ghid_sbm.py` | 4 | `Geração Hidráulica (MW)` | `grafico_ghid_sbm{1..4}.html` |
| `Plotadores/Gter_sbm.py` | 4 | `Geração Térmica (MW)` | `grafico_gter_sbm{1..4}.html` |
| `Plotadores/CMO_sbm.py` | 4 | `Custo Marginal de Operação (R$/MWh)` | `grafico_cmo_sbm{1..4}.html` |
| `Plotadores/Custos.py` | 3 | `Custo Presente (R$)`, `Custo Futuro (R$)`, `Custo Total de Operação (R$)` | `grafico_custo_{presente,futuro,total}.html` |
| `Plotadores/Tempo.py` | 4 | `Tempo em Minutos` (all four), with figure titles `Tempo MILP`, `Tempo PL`, `Tempo Leitura de Dados e Impressão`, `Tempo Total` | `grafico_{MILP,PL,Leitura,total}.html` |

Every line chart filters `df.loc[df["estagio"] <= 48]` and every one sets
`fig.update_xaxes(..., type='category', tickformat="%d/%m/%Y %H:%M")`. Every layout sets
`hovermode="x unified"`, `xaxis_title='Data'`, `font=dict(family='Arial', size=12)`,
`plot_bgcolor='white'`, `autosize=False`, `width=1400`, `height=450`, and every axis sets
`showgrid=True, gridcolor="lightgray", gridwidth=1`.

The legacy scalar formulas, verbatim:

```python
# Plotadores/Custos.py, lines 20-21
df_cp[caso.name].append(df_custos.loc[df_custos["parcela"] == "PRESENTE", "valor_esperado"].values[0])
df_cf[caso.name].append(df_custos.loc[df_custos["parcela"] == "FUTURO", "valor_esperado"].values[0])
# line 69: df_total = df_cp_resultante + df_cf_resultante

# Plotadores/Tempo.py, lines 22-24
df_leitura[caso.name].append(df_tempo.loc[df_tempo["etapa"] == "Leitura de Dados e Impressão", "tempo"].values[0]/60)
df_milp[caso.name].append(df_tempo.loc[df_tempo["etapa"] == "MILP", "tempo"].values[0]/60)
df_pls[caso.name].append(df_tempo.loc[(df_tempo["etapa"] == "PL") | (df_tempo["etapa"] == "PL.Int.Fix") | (df_tempo["etapa"] == "PL.CalcCMO"), "tempo"].sum()/60)
# line 90: df_total = df_milp_resultante + df_pl_resultante + df_leitura_resultante
```

The new side, as shipped. `enabled_specs()` returns 23 specs (measured), of which the eight the
legacy covered carry the curated titles `Geração Hidrelétrica` (`GHID_SIN`, MW),
`Geração Térmica` (`GTER_SIN`, MW), `Geração Hidráulica` (`GHID_SBM`, MW),
`Geração Térmica` (`GTER_SBM`, MW), `CMO` (`CMO_SBM`, R$/MWh),
`Custo Presente, Futuro e Total` (`CUSTOS`, **`10^3 R$`**) and `Tempo Computacional`
(`TEMPO`, min) — measured by calling `enabled_specs()` after the epic-04 boundary review, which
changed the cost unit from `R$` (boundary finding 1).
`dashboard.scalars.aggregate_costs` sums the parcels named by `costs.total_parcels`, default
`["PRESENTE", "FUTURO"]`, over **already rounded** values and rounds once more.
`aggregate_times` sums each `time.stage_groups` member present in the raw mapping, divides by
`time.unit_divisor` (60.0) and rounds once — and `consolidate._load_scalars` has already **summed**
the rows sharing one `etapa`, whereas the legacy takes `.values[0]` for `Leitura` and `MILP`.
`theme.plotly_layout_template` sets `xaxis.type = "date"` with `tickformat` and `hoverformat` from
`dashboard.date_format`, and `dashboard.js`'s `buildLayout` replaces that with
`xaxis.type = "category"` plus `barmode = "group"` for the two `SCALAR_BY_DECK` charts.

**The unit divergence, and it is the most consequential parity finding of the epic.** Every legacy
cost axis is labelled `(R$)` — `Custo Presente (R$)` at `Plotadores/Custos.py:34`,
`Custo Futuro (R$)` at line 52, `Custo Total de Operação (R$)` at line 77 — and it plots
`CUSTOS.valor_esperado` unscaled. The epic-04 boundary review established from
`reference/parquet-schemas.txt` that those values are in **`10^3 R$`**, not plain `R$`:
`CUSTOS.PRESENTE` = `58667.5674` tracks `COP_SIN`'s reference-deck sum
(`406.6581 R$/h × 144 h = 58558.77`, ratio 1.0019), and `CUSTOS.FUTURO` = `228420390.34615` tracks
`CFU_SIN` = `228917.0446721` at `10^6 R$` at ratio 0.9978 when read as `10^3 R$` versus 1000× too
small when read as plain `R$`; and `METADADOS_OPERACAO.unidade`'s own value set contains
`10^3 R$` and `10^6 R$` but never plain `R$`. So **the legacy axis label was wrong by a factor of
1000, and the new dashboard corrects it.** The parity report must record this as a divergence the
new tool introduces deliberately, in the "not reproduced" list rather than the "preserved" list, and
it is the strongest available argument that a parity check comparing only numbers would have missed
the thing that mattered.

Four **defects in the legacy implementation** were found while reading it, and they matter here
because parity must not mean reproducing them:

- `Plotadores/Ghid_SIN.py:26-28` sets `df_plot[caso] = aux["valor"].values` (concatenation order)
  while `df_datas["Datas"] = np.unique(aux["data_inicio"])` (**sorted** order). The two are paired
  positionally by `px.line`, so if the decks were concatenated out of date order the y values are
  silently mispaired with the x values. The concatenation order is
  `caminho_pasta.iterdir()` order — filesystem order, not date order — because
  `Leitura/leitor_arquivos.py` and every `main_*.py` iterate without sorting.
- `df_datas` is filled only on the first scenario (`if len(df_datas) == 0`), so a second scenario
  with a different timeline would be plotted against the first one's timestamps.
- `type='category'` makes the accompanying `tickformat="%d/%m/%Y %H:%M"` inert: a categorical axis
  renders the category strings themselves, which for `numpy.datetime64` values are full ISO
  timestamps. Appendix A.7's "x tick format `%d/%m/%Y %H:%M`" describes the legacy *source*, not
  what the legacy *rendered*.
- The `(R$)` axis labels understate the unit by a factor of 1000, as established above.

`tests/exemplo_tree.py` exists after ticket-034 and exposes `exemplo_root()`,
`qualifying_scenarios(root)` and `documented_pair(root)`; `tests/fixtures_sintese.py`'s
`make_sintese_dir(target, *, first_stage_start, n_stages=6, half_hour_stages=4,
long_stage_hours=2.0, hydro_codes=(1,2,3), reservoir_codes=(1,2), thermal_codes=(1,2),
submarket_codes=(1,2,11,99), pair_codes=((1,2),(2,1)), omit=(), seed=42)` can build both a
four-submarket tree and a tree with `TEMPO` omitted so a custom one can be written beside it.
`tests/conftest.py`'s `scenario_tree` uses the generator defaults for `submarket_codes`, so **only
codes 1 and 2 are visible on that fixture** — asserting "submarkets 1 to 4" on it would be vacuous.

## Specification

### Requirements

1. Create `tests/test_parity.py` with three groups of tests and no source change anywhere. The
   module must **not** read, import or reference any file under `Leitura/` or `Plotadores/`: every
   legacy fact it depends on is transcribed into the requirement text and into the parity report,
   because ticket-038 deletes those directories and a test reading them would fail the moment it
   does. That is the cross-ticket collision shape this plan has hit twice.
2. **Group A, synthetic parity, always runs.** On a fixture tree built with
   `submarket_codes=(1, 2, 3, 4, 11, 99)` so the legacy's `submercados = [1, 2, 3, 4]` list is
   actually covered, recompute each Appendix A.7 quantity from the Parquet with pandas, using the
   legacy expression, and assert it equals the value the payload carries:
   - `GHID_SIN` and `GTER_SIN`: `payload["charts"][key]["series"][""][scenario]["encadeado"]` equals
     the per-deck `valor` arrays for `estagio <= chaining.stages_per_deck`, concatenated in
     **deck-date order**, each value rounded to `output.decimals`;
   - `GHID_SBM`, `GTER_SBM` and `CMO_SBM`: the same, per submarket, for each of the codes 1, 2, 3
     and 4, with the entity id being `str(codigo_submercado)`;
   - `CUSTOS`: `scalars["PRESENTE"]`, `scalars["FUTURO"]` and `scalars["TOTAL"]` equal the file's
     `valor_esperado` for each parcela and their sum;
   - `TEMPO`: `scalars["MILP"]`, `scalars["Leitura"]`, `scalars["PL"]` and `scalars["TOTAL"]` equal
     the legacy expressions divided by `time.unit_divisor`, with `PL` summing the three etapa names.
   Use `pytest.approx` with an absolute tolerance of `10 ** -settings.output.decimals` wherever a
   sum or a division is involved and exact equality where a value is read straight from the file.
3. **Group B, real-data parity, skipped without the tree.** Repeat every comparison of requirement 2
   against the tree `tests/exemplo_tree.py` resolves, over the two documented scenarios. This is the
   real-data verification, and it is expressed **only as assertions**: no value is printed, logged
   or written to a file, so nothing from `exemplo/` is transcribed. Skip with the same reason shape
   ticket-034 established when fewer than two scenarios qualify. Where the real submarket set
   differs from 1 to 4, iterate `visible_submarket_codes(registries, include_fictitious=False)`
   rather than a hard-coded list, and additionally assert that the iterated set is non-empty so the
   loop cannot pass over nothing.

   Add **two absolute assertions for the reference deck**, guarded by `documented_pair` and by the
   deck key `03/03/2024`, with the figures taken from the committed
   `reference/parquet-schemas.txt` dump and the file cited in a comment. They are the only place in
   the epic where a real number is pinned, and they are legitimate because the dump is versioned and
   decision 15 verified the deck is the same one:
   - `CUSTOS`: `PRESENTE == 58667.5674` and `FUTURO == 228420390.34615` exactly, so the legacy total
     `PRESENTE + FUTURO` is `228479057.91355` and the payload's `TOTAL` at `output.decimals = 2` is
     `228479057.91`;
   - `TEMPO`: the file's nine rows carry nine distinct `tempo` values —
     `48.0, 438.0, 469.0, 564.0, 714.0, 786.0, 1056.0, 1086.0, 6726.0` — summing to `11887.0`
     seconds; the three default `stage_groups` cover every etapa the file holds, so the payload's
     `TOTAL` is `round(11887.0 / 60.0, 2) = 198.12` minutes.
   Prove both can fail by asserting the same values against `unit_divisor = 1.0` and against a
   single-parcel `costs.total_parcels`, and confirming each mutation breaks them.

   > **Take the figures from the dump's SAMPLE ROWS, never from its unique-value lists** — added
   > 2026-09-11 after the orchestrator walked into this while auditing the ticket. The dump prints
   > a `valor_esperado: N unique -> [...]` line before the sample rows, and those uniques are
   > truncated to seven significant figures: `5.866757e+04` and `2.284204e+08`. Summing those gives
   > `228479067.57`, which is wrong in the eighth digit and would fail the
   > `== 228479057.91` assertion by about 10 R$. The sample rows carry full precision
   > (`58667.5674`, `228420390.34615`) and are the only usable source for an absolute pin. The
   > uniques appear *earlier* in the file than the sample rows, so they are what a reader greps
   > first — which is exactly why this note exists.
4. **Group C, the deliberate divergences, always runs.** Assert each documented divergence is real,
   on the new side only:
   - the repeated-`etapa` divergence: build a synthesis directory with
     `make_sintese_dir(..., omit=("TEMPO",))`, write a `TEMPO.parquet` beside it carrying the
     columns `("etapa", "tempo", "execucao")` with **two** `MILP` rows of different non-zero values,
     and assert the payload's `MILP` equals `(row_a + row_b) / 60` rounded, while the legacy
     expression `.values[0] / 60` equals only `row_a / 60`, and the two differ. The new behaviour is
     the correct one — a discarded row is silently lost runtime — and this is the assertion that
     records it;
   - the axis-type divergence: `payload["theme"]["layout"]["xaxis"]["type"] == "date"` with
     `tickformat == settings.dashboard.date_format`, and the two `SCALAR_BY_DECK` charts' category
     labels in the document read `<deck key> - <series name>`;
   - the file-count divergence: exactly one output HTML, containing 23 chart sections and no
     `https://cdn.plot.ly` reference outside the inlined bundle, against the legacy's 21 files each
     loading Plotly from a CDN.
5. Create `plans/dashboard-dessem/epic-05-parity-report.md` with seven sections, in English per
   Rigoroso mode: (a) method, including the three measured reasons the legacy is not executed;
   (b) the legacy inventory table of this ticket's Current State, with `file:line` references for
   every axis title, figure title, filter and output filename — **this is the transcription that
   makes ticket-038's deletion safe, and ticket-038's Definition of Done checks for it**; (c) the
   value-parity result, one row per Appendix A.7 quantity, with the verdict and the tolerance used,
   citing the Group A and Group B test names as the evidence rather than quoting any number from
   real data; (d) the presentation-parity table, one row per chart family, stating the legacy figure
   count, the new chart count and the verdict; (e) the deliberate divergences, with the decision or
   the spec clause that authorises each; (f) the four legacy defects found while reading, marked
   **not reproduced**; and (g) the **unit divergence**, given its own section because it is the one
   finding that changes what a number on the screen means: the legacy labelled the cost axes `(R$)`
   while the values are `10^3 R$`, and the dashboard labels them `10^3 R$`, with the
   `reference/parquet-schemas.txt` evidence quoted and cited.
6. In section (d), record the two presentation collapses as **open decisions for the developer**,
   each with its options and its evidence: `CUSTOS` 3 figures → 1 grouped chart, and `TEMPO`
   4 figures → 1 grouped chart. For each, state the two options — accept the single grouped chart,
   or add separate `ChartSpec` entries in a follow-up ticket — and name the evidence: checklist step
   29's "read and record" of the two cost magnitudes, and checklist step 30's four time bars. Do
   **not** choose. The cost case is already on the developer's open-decision list in
   `.implementation-state.json`; the time case is new and must be added to the report and reported
   to the orchestrator.
7. Answer the outline's second open question in section (e) and record the answer: the categorical
   axis is **not** offered as an option. Master plan decision 14 records the rationale — with stage
   durations of 0.5, 2, 6 and 8 hours a categorical axis gives an 8-hour stage the same width as a
   30-minute one, which visually falsifies the horizon — the legacy's own `tickformat` was inert
   under `type='category'` anyway, and a second axis mode would be a new settings key, which the
   epic's scope excludes. Reopen only on an explicit developer request.
8. Touch no file under `src/`, no existing test module, and no file under `Leitura/` or
   `Plotadores/`. If a Group A or Group B assertion fails, that is a **parity failure**: stop, report
   it with the chart key, the scenario, the deck and the two computed values side by side (a
   fixture value may be quoted; a real-data value must be reported as a relative difference only),
   and do not change a source module to make it pass.

### Inputs

From the repository: the legacy source text, read once during refinement and transcribed here and
into the report — the test never reads it. From `tests/fixtures_sintese.py`: a four-submarket tree
and a `TEMPO`-omitted tree. From `tests/exemplo_tree.py`: the real tree, when present. From
`settings.json`: `chaining.stages_per_deck` (48), `costs.total_parcels`, `time.stage_groups`,
`time.unit_divisor` (60.0), `output.decimals` (2), `submarkets.include_fictitious` (false) and
`dashboard.date_format`. Every legacy constant the tests compare against is written into the test
as a named module constant with a comment giving its `Plotadores/*.py` line, so the provenance
survives the deletion.

### Outputs and Behavior

One new test module whose Group A and Group C tests run on every machine and whose Group B tests
skip without the data, and one report document. No source behaviour changes and no artefact is left
in the repository tree: every document the tests build goes to `tmp_path`.

### Error Handling

No new exception type. A parity mismatch surfaces as an `AssertionError` from the test, which is the
intended failure channel: the check exists to fail loudly. A missing real tree is a skip, never an
error. A `SchemaError` from the hand-written `TEMPO.parquet` of requirement 4 means the frame does
not match `SCALAR_COLUMNS["TEMPO"]` and must be fixed in the test, not worked around by relaxing
`readers.read_times`.

## Dependencies

- **Blocked By**: `ticket-034-add-example-data-integration-test.md` (it creates
  `tests/exemplo_tree.py`, which requirement 3 imports, and it is the run whose manual walk feeds
  the report's sections (c) and (d))
- **Blocks**: `ticket-036-write-user-documentation.md`
- **Hard ordering constraint**: `ticket-038-remove-legacy-scripts.md` must run **after** this
  ticket, because it deletes `Plotadores/`, the source this ticket transcribes. The epic order is
  already sequential; do not reorder it under any circumstances.

## Acceptance Criteria

- [ ] Given a fixture tree built with `submarket_codes=(1, 2, 3, 4, 11, 99)`, when Group A runs,
      then for each of `GHID_SIN`, `GTER_SIN`, `GHID_SBM`, `GTER_SBM` and `CMO_SBM` the payload's
      chained array equals the independently recomputed `estagio <= 48` concatenation in deck-date
      order within `0.01`, the comparison covers submarket codes 1, 2, 3 and 4 for each of the three
      submarket charts, and every comparison visited at least one array of non-zero length.
- [ ] Given the same fixture, when Group A's scalar tests run, then `CUSTOS`'s `PRESENTE` and
      `FUTURO` equal the file's `valor_esperado` exactly, `TOTAL` equals their sum within `0.01`,
      and `TEMPO`'s `MILP`, `Leitura`, `PL` and `TOTAL` equal the four legacy expressions divided by
      `60.0` within `0.01`.
- [ ] Given a synthesis directory whose hand-written `TEMPO.parquet` carries two `MILP` rows with
      distinct non-zero values, when the payload is built, then `scalars["MILP"]` equals their sum
      divided by `60.0` and rounded to two decimals, it does **not** equal the first row divided by
      `60.0`, and the two differ by more than `0.01` — proving the divergence from the legacy's
      `.values[0]` is real and is a deliberate improvement rather than an accident.
- [ ] Given the real tree, when Group B runs, then every comparison of acceptance criteria 1 and 2
      passes over the two documented scenarios and the submarket set is non-empty; and given an
      empty `DESSEM_DASHBOARD_EXEMPLO` root, Group B reports `SKIPPED` with a reason naming the
      variable and the default path while Groups A and C still pass.
- [ ] Given `plans/dashboard-dessem/epic-05-parity-report.md`, when it is read, then it contains all
      seven required sections; the legacy inventory names all seven `Plotadores` modules, all twelve
      `write_html` call sites, the 21 runtime output filenames and every Y-axis and figure title with
      a `file:line` reference; the presentation table records `CUSTOS` as 3 → 1 and `TEMPO` as
      4 → 1, each with two stated options and no chosen answer; section (g) records the `(R$)`
      versus `10^3 R$` unit divergence with its `reference/parquet-schemas.txt` evidence; and
      `.venv/bin/pytest tests/test_parity.py -q && .venv/bin/ruff check src tests` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Read `Plotadores/*.py` and `main_*.py` once, at the start, and transcribe every constant you will
   need into module-level constants in `tests/test_parity.py` with a comment naming the source line.
   After that, do not read them again: the test must be independent of files ticket-038 deletes.
2. Write Group A first and drive it from the fixture, because it is decidable, fast and runs
   everywhere. Build the tree with `build_scenario_tree`-style calls to `make_sintese_dir`, passing
   `submarket_codes=(1, 2, 3, 4, 11, 99)`; note that `tests/conftest.py`'s `scenario_tree` fixture
   uses the generator default `(1, 2, 11, 99)`, so you cannot reuse it for the submarket comparisons
   — an assertion over codes 3 and 4 on that fixture would pass over an empty loop.
3. Recompute with pandas exactly as the legacy does, including the `estagio <= 48` filter and the
   concatenation, but concatenate in **deck-date order read from `EST.parquet`** rather than in
   `iterdir()` order. Record in the report that this is a correction, not a reproduction: the legacy
   order is filesystem-dependent and its y values are paired positionally against a sorted x array.
4. Round the recomputed values with the same `round(value, decimals)` the payload uses, then compare
   with `pytest.approx(..., abs=10 ** -decimals)`. Do not compare unrounded values to rounded ones
   and call the difference a tolerance.
5. For Group C's repeated-`etapa` case, write the `TEMPO.parquet` with
   `pd.DataFrame({"etapa": [...], "tempo": [...], "execucao": [...]})` matching
   `schemas.SCALAR_COLUMNS["TEMPO"]`, and give the two `MILP` rows values whose sum differs from the
   first by far more than the tolerance, so the assertion cannot be satisfied by rounding. Keep the
   other etapa rows so the `PL` and `Leitura` groups still emit and `TOTAL` is still computable.
6. Write Group B as a thin parametrisation over the same comparison helpers Group A uses, so the two
   groups cannot drift apart. Import `exemplo_root`, `qualifying_scenarios` and `documented_pair`
   from `tests/exemplo_tree.py`; do not duplicate the resolution logic and do not import a private
   helper from `tests/test_integration_exemplo.py`.
7. Write the report last, after the tests pass, so section (c) cites test names that exist. Fill
   sections (a), (b), (e) and (f) from this ticket's Current State — they are source facts and need
   no data. Leave section (c)'s verdict column filled from the test results and **no value column
   for real data**; the evidence is "assertion X passed at tolerance Y", which is a verdict rather
   than a transcription.
8. For section (d), write each collapse as a three-part entry: what the legacy did (with line
   references), what the dashboard does, and the two options with their costs — accepting the single
   chart costs one series' visibility on a shared linear axis; splitting costs three or four new
   `ChartSpec` entries in `charts/specs.py`, three or four new `FALLBACK_UNITS` entries, and the six
   pinned `23` chart-count literals in the suite (`tests/test_builder.py:36`,
   `tests/test_charts_costs.py:570`, `tests/test_charts_sin.py:483`,
   `tests/test_output_size.py:45`, `tests/test_payload.py:33`, `tests/test_registries.py:32`, plus
   `tests/test_chart_specs.py`'s `_ENABLED_KEYS_IN_ORDER` tuple and its three `42` literals).
   Re-measure that list with a grep before writing it; do not copy it from here.
9. Prove the new assertions can fail: change the recomputation's stage filter from
   `<= 48` to `<= 24` and confirm criterion 1 fails; drop `TOTAL` from the `CUSTOS` comparison and
   confirm criterion 2 fails; set the second `MILP` row to `0.0` and confirm criterion 3's
   "they differ" assertion fails; point `DESSEM_DASHBOARD_EXEMPLO` at an empty directory and confirm
   Group B skips rather than errors. Restore each.
10. Hand the orchestrator two things in the completion report: the parity verdict per Appendix A.7
    quantity, and the two open presentation decisions with the evidence, flagged as needing a
    developer ruling before ticket-038 commits the deletion.

### Key Files to Create/Modify

- `tests/test_parity.py` (create: Groups A, B and C, plus the shared comparison helpers)
- `plans/dashboard-dessem/epic-05-parity-report.md` (create: the six sections)

### Patterns to Follow

- `tests/test_charts_costs.py`'s "recompute from `CUSTOS.parquet` with pandas, proving the value
  reached the payload from the file rather than from a coincidence of the aggregation" — this ticket
  generalises that single test to every Appendix A.7 quantity.
- `tests/test_output_size.py`'s settings builder and `_REPO_LOGO`, and `tests/dashboard_document.py`'s
  public slicing helpers for the document assertions of requirement 4.
- `tests/exemplo_tree.py`'s resolution and skip contract from ticket-034, reused rather than
  reimplemented.
- The plan-wide non-vacuity discipline: every loop-driven comparison asserts that the loop visited
  something, and every equality is paired with a mutation that breaks it.
- `docs/checklist-manual-dashboard.md`'s `**Expected result:**` convention if the report gains any
  operator step; otherwise keep the report a plain document with tables.

### Pitfalls to Avoid

- Do not run, import, edit or copy any legacy module. All twelve fail at import in this environment,
  measured, and editing them to run would produce a modified reference.
- Do not let `tests/test_parity.py` read `Plotadores/` or `Leitura/`. ticket-038 deletes both, and a
  test that reads a file a later ticket removes is exactly the collision shape this plan recorded
  twice.
- Do not reuse `tests/conftest.py`'s `scenario_tree` for the submarket comparisons. Its
  `submarket_codes` default is `(1, 2, 11, 99)`, so a loop over codes 1 to 4 would silently cover
  two of the four. Epic-02 learnings section 7 records the identical trap for `INT_SBP` and code 11.
- Do not read parity as "the totals agree". Two presentation collapses, 3 → 1 for costs and
  4 → 1 for times, change what the operator sees even when every number matches — and the unit
  divergence changes what the matching numbers **mean**, since the legacy called `10^3 R$` values
  `R$`.
- Do not quote a value read from `exemplo/` anywhere — not in the report, not in a test, not in the
  completion message. A mismatch is reported as a relative difference. Figures from
  `reference/parquet-schemas.txt` are the one exception and must always cite that file.
- Do not reproduce the legacy's defects for the sake of parity. The `.values[0]` truncation of a
  repeated `etapa`, the sorted-x-versus-concat-order pairing and the first-scenario-only timeline are
  bugs; the report marks them **not reproduced** and requirement 4 asserts the first one is fixed.
- Do not treat Appendix A.7's "x tick format `%d/%m/%Y %H:%M`" as legacy *rendered* behaviour. Under
  `type='category'` the tickformat is inert; the legacy rendered ISO category strings.
- Do not compare an unrounded recomputation against a rounded payload value and absorb the gap into
  the tolerance. Round both, then compare at `10 ** -decimals`.
- Do not offer a categorical-axis option. Decision 14 settles it, and a second axis mode is a new
  settings key the epic's scope excludes.
- Do not change a source module to make a parity assertion pass. A mismatch is the finding this
  ticket exists to produce.

### Out of Scope

- Any change under `src/`, to `settings.json`, to `charts/specs.py` or to any existing test module.
- Adding, splitting or removing any `ChartSpec` — including the three-cost-chart and four-time-chart
  splits the report puts on the developer's desk. Those are a follow-up ticket if the developer wants
  them.
- Deleting or moving anything under `Leitura/` or `Plotadores/` (ticket-038).
- The README's parity section and the checklist's stale title and intro (ticket-036).
- Any new settings key, including a categorical-axis toggle or a per-chart axis type.
- Parity for the sixteen charts the legacy never produced — `GUNS_*`, `EARMF_SIN`, `VARMF_*`,
  `MER_SBM`, `INT_SBP`, the eight `UHE` charts and `GTER_UTE`. They have no reference behaviour and
  Appendix A.7 does not list them.

## Testing Requirements

### Unit Tests

None beyond the parity module itself; this ticket adds no production code.

### Integration Tests

`tests/test_parity.py`:

- Group A — acceptance criteria 1 and 2, on the four-submarket fixture, always running;
- Group B — acceptance criterion 4, the same comparisons over the real tree, skip-guarded;
- Group C — acceptance criterion 3 plus the axis-type and single-file divergence assertions, always
  running;
- the four non-vacuity mutations of Suggested Approach step 9, each observed to fail before
  restoration.

### Regression

Every existing test module passes **unchanged**. This ticket writes no source and amends no
assertion, which is the falsifiable prediction it makes about itself: if an existing test has to
change, that is a finding and must be reported rather than absorbed.

## Definition of Done

- [ ] All five acceptance criteria pass, and the four non-vacuity mutations were each observed to
      fail and then restored.
- [ ] `tests/test_parity.py` contains no reference to `Plotadores`, `Leitura` or `main_`, verified
      with `grep -n "Plotadores\|Leitura\|main_" tests/test_parity.py` returning no match outside a
      provenance comment, and the module passes with `Leitura/` and `Plotadores/` temporarily moved
      aside — the proof that ticket-038 cannot break it.
- [ ] The parity report exists with all six sections, and its legacy inventory carries a `file:line`
      reference for every axis title, figure title, stage filter and output filename, so the
      behaviour of the seven plotter modules survives their deletion as a document.
- [ ] The two presentation collapses are recorded as open developer decisions with options and
      evidence, and are reported to the orchestrator for a ruling before ticket-038 runs.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
      `.venv/bin/mypy src` exit 0; `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing`
      passes with total coverage at or above **85 percent**.
- [ ] The completion report states the parity verdict for every Appendix A.7 quantity, the tolerance
      used, the collected test count from `pytest --collect-only -q`, and an explicit statement that
      no value from `exemplo/` was transcribed.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 50 minutes. Unchanged from the
outline's 3 points, but the content changed more than any other ticket in the epic. The outline left
the comparison method open and listed running the legacy scripts as one of three candidates;
refinement closed it by measurement — all twelve legacy modules raise `FileNotFoundError` at import,
the tree layout they expect no longer exists, and two of the five drivers only work through
star-imported globals — so the ticket is now an independent recomputation with a transcription,
which is both cheaper and stronger than editing legacy code to run. Refinement also found that the
cost-chart presentation tension has an unrecorded twin in `TEMPO` (4 figures → 1) and three genuine
defects in the legacy implementation that parity must not reproduce. Confidence is Medium rather than
High because the ticket's value depends on a developer ruling it cannot make — whether one grouped
chart per family is acceptable where the legacy gave each series its own axis — and because the real
tree's Group B run cannot be inspected value by value under this plan's data rules; it can only
assert.
