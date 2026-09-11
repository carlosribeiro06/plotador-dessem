# Epic 5 Legacy Parity Report

> Implementation mode: Rigoroso. Produced by ticket-035; the automated evidence behind every
> verdict below lives in `tests/test_parity.py`. Written in English per the mode policy; every
> Portuguese interface string named below is quoted verbatim from the source it names.

## (a) Method

**The legacy scripts are never executed. Parity is established by an independent recomputation of
the legacy pandas expressions, transcribed from the source and checked against `dessem_dashboard`'s
payload.** Three reasons, each re-measured during this ticket:

1. `Leitura/leitor_arquivos.py:9` hard-codes
   `Path("C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo")` and iterates it at
   **module level**, line 13. Measured again in this environment:

   ```
   $ .venv/bin/python -c "import Leitura.leitor_arquivos"
   FileNotFoundError: [Errno 2] No such file or directory:
     'C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo'
   ```

   All seven `Plotadores/*.py` modules and all five `main_*.py` drivers carry
   `from Leitura.leitor_arquivos import *` **exactly once each** (`grep -c` re-measured: 12 files,
   1 match each), so every one of the twelve fails at import.
2. The scripts require the **date-first** layout `exemplo/<data>/<caso>/sintese`; the tree has been
   scenario-first, `exemplo/<caso>/<data>/sintese`, since `planning-context.md` decision 15. Under
   the current layout `leitor_arquivos` would build `casos = {"caso_oficial": ["2024-03-03",
   "2024-03-04"], "caso_gurobi": [...]}` — scenario names read as dates — and
   `Plotadores/Custos.py:29` would then ask `pd.to_datetime` to parse `"caso_oficial"`.
3. Two of the five drivers only work by accident, through star-imported globals, so "fix the path
   and run" is not a mechanical edit:
   - `main_custos.py:17` unpacks `df_cp, df_cd = gera_df_custos(...)` and line 19 calls
     `df_plot_custos(df_cp, df_cf)`. `df_cf` resolves only because
     `from Plotadores.Custos import *` (line 5) also imported the module-level `defaultdict`
     `gera_df_custos` mutates; `df_cd` is bound and never used.
   - `main_tempo.py:17` binds `df_tempo_milp, df_tempo_pl, df_tempo_leitura` and line 19 calls
     `df_plot_tempo(df_tempo_milp, df_pls, df_tempo_leitura)` — `df_pls`, not the local
     `df_tempo_pl`, is the star-imported module-level global from `Plotadores.Tempo`.

Editing the legacy scripts to run would produce a **modified** reference, which is worse than none
(decision E5-1). So every figure below is recomputed independently, in `tests/test_parity.py`, from
the same synthesis files the legacy scripts would have read, using the legacy pandas expressions
transcribed once into module constants (each citing its `Plotadores/*.py` source line) — never by
importing, running, or otherwise reading `Leitura/` or `Plotadores/`.

## (b) Legacy inventory

Twelve `fig.write_html(..., include_plotlyjs="cdn")` call sites across seven `Plotadores/*.py`
modules produce **21 runtime output files** (measured: `grep -rn write_html Plotadores/*.py` finds
exactly 12 sites; the three submarket plotters each loop `submercados = [1, 2, 3, 4]`, quadrupling
their one call site to four files). Thirteen legacy files are tracked in git
(`git ls-files Leitura Plotadores main_*.py`): `Leitura/leitor_arquivos.py`, the seven
`Plotadores/*.py` modules, and the five `main_*.py` drivers.

| Module | Figures | Y-axis / figure title(s) | Stage filter | Output filename(s) |
| --- | --- | --- | --- | --- |
| `Plotadores/Ghid_SIN.py` | 1 | `Geração Hidráulica (MW)` (:35) | `estagio <= 48` (:18) | `grafico_ghid_sin.html` (:44, write_html :46) |
| `Plotadores/Gter_SIN.py` | 1 | `Geração Térmica (MW)` (:35) | `estagio <= 48` (:18) | `grafico_gter_sin.html` (:44, write_html :46) |
| `Plotadores/Ghid_sbm.py` | 4 | `Geração Hidráulica (MW)` (:37) | `estagio <= 48` (:19) | `grafico_ghid_sbm{1..4}.html` (:46, write_html :48); `submercados = [1, 2, 3, 4]` (:13) |
| `Plotadores/Gter_sbm.py` | 4 | `Geração Térmica (MW)` (:37) | `estagio <= 48` (:19) | `grafico_gter_sbm{1..4}.html` (:46, write_html :48); `submercados = [1, 2, 3, 4]` (:13) |
| `Plotadores/CMO_sbm.py` | 4 | `Custo Marginal de Operação (R$/MWh)` (:37) | `estagio <= 48` (:19) | `grafico_cmo_sbm{1..4}.html` (:46, write_html :48); `submercados = [1, 2, 3, 4]` (:13) |
| `Plotadores/Custos.py` | 3 | `Custo Presente (R$)` (:34), `Custo Futuro (R$)` (:52), `Custo Total de Operação (R$)` (:77) | none (scalar per deck) | `grafico_custo_presente.html` (:43, write_html :45), `grafico_custo_futuro.html` (:62, write_html :64), `grafico_custo_total.html` (:87, write_html :89) |
| `Plotadores/Tempo.py` | 4 | all four `Tempo em Minutos` (:37, :55, :73, :98); figure titles `Tempo MILP` (:33), `Tempo PL` (:51), `Tempo Leitura de Dados e Impressão` (:69), `Tempo Total` (:94) | none (scalar per deck) | `grafico_MILP.html` (:46, write_html :48), `grafico_PL.html` (:64, write_html :66), `grafico_Leitura.html` (:82, write_html :84), `grafico_total.html` (:107, write_html :109) |

Every line chart (`Ghid_SIN`, `Gter_SIN`, `Ghid_sbm`, `Gter_sbm`, `CMO_sbm`) additionally sets
`type='category'` and `tickformat="%d/%m/%Y %H:%M"` on the X axis (each module's `update_xaxes`
call, immediately after its `write_html` line's preceding block); every bar chart (`Custos.py`,
`Tempo.py`) sets `type='date'` with no `tickformat`. Every one of the seven modules sets
`hovermode="x unified"`, `xaxis_title='Data'`, `font=dict(family='Arial', size=12)`,
`plot_bgcolor='white'`, `autosize=False`, `width=1400`, `height=450`, and every axis sets
`showgrid=True, gridcolor="lightgray", gridwidth=1`.

The legacy scalar formulas, verbatim (also transcribed into `tests/test_parity.py`'s module
constants):

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

The five `main_*.py` drivers, verbatim in structure:

| Driver | Imports | Loop body | Plot call |
| --- | --- | --- | --- |
| `main_ghid.py` | `Plotadores.Ghid_sbm`, `Plotadores.Ghid_SIN` | :14-20 | `df_plot_ghid_sbm(df_ghid_sbm)` (:23), `df_plot_ghid_sin(df_ghid_sin)` (:24) |
| `main_gter.py` | `Plotadores.Tempo`, `Plotadores.Gter_sbm`, `Plotadores.Gter_SIN` | :15-21 | `df_plot_gter_sbm(df_gter_sbm)` (:23), `df_plot_gter_sin(df_gter_sin)` (:24) |
| `main_cmo.py` | `Plotadores.Tempo`, `Plotadores.CMO_sbm` | :14-19 | `df_plot_cmo_sbm(df_cmo)` (:21) |
| `main_custos.py` | `Plotadores.Custos` | :12-17 | `df_plot_custos(df_cp, df_cf)` (:19) — `df_cf` is the star-imported global, not the locally bound `df_cd` |
| `main_tempo.py` | `Plotadores.Tempo` | :12-17 | `df_plot_tempo(df_tempo_milp, df_pls, df_tempo_leitura)` (:19) — `df_pls` is the star-imported global, not the locally bound `df_tempo_pl` |

`Leitura/leitor_arquivos.py:9` (`caminho_pasta = Path("C:/Users/carlo/...")`) and `:13`
(`for pasta in caminho_pasta.iterdir():`) are the module-level hard-coded path and the
module-level iteration that make every import above fail in this environment.

## (c) Value-parity result

Every quantity below **passes**. The evidence is the named test in `tests/test_parity.py`, never a
quoted real-data number; a real-data value is never printed, logged or written to a file by any
test in this module (Requirement 3).

| Appendix A.7 quantity | Tolerance | Verdict | Evidence (Group A, synthetic) | Evidence (Group B, real data) |
| --- | --- | --- | --- | --- |
| `GHID_SIN`, `GTER_SIN` chained | exact (rounded to `output.decimals`) | PASS | `test_group_a_sin_chained_matches_legacy_filter_and_deck_date_order` | `test_group_b_series_and_scalar_parity_matches_legacy_expressions` |
| `GHID_SBM`, `GTER_SBM`, `CMO_SBM` chained, codes 1-4 | exact (rounded to `output.decimals`) | PASS | `test_group_a_submarket_chained_matches_legacy_for_codes_1_to_4` | `test_group_b_series_and_scalar_parity_matches_legacy_expressions` (codes from `visible_submarket_codes`, per requirement 3) |
| `CUSTOS.PRESENTE`, `CUSTOS.FUTURO` | exact | PASS | `test_group_a_custos_scalars_match_legacy_direct_reads_and_sum` | `test_group_b_series_and_scalar_parity_matches_legacy_expressions`; absolute pin: `test_group_b_reference_deck_custos_pins_match_committed_dump` |
| `CUSTOS.TOTAL` | `abs=10**-decimals` (0.01) | PASS | `test_group_a_custos_scalars_match_legacy_direct_reads_and_sum` | same two tests as above |
| `TEMPO.MILP`, `TEMPO.Leitura`, `TEMPO.PL`, `TEMPO.TOTAL` | `abs=10**-decimals` (0.01) | PASS | `test_group_a_tempo_scalars_match_legacy_expressions_divided_by_unit_divisor` | `test_group_b_series_and_scalar_parity_matches_legacy_expressions`; absolute pin: `test_group_b_reference_deck_tempo_pins_match_committed_dump` |

**Two corrections to this ticket's own text, found while implementing it, both measured rather than
asserted, neither changing the verdict above:**

1. **The precision-trap note's structural attribution is backwards.** Measured directly against
   `plans/dashboard-dessem/reference/parquet-schemas.txt` lines 86-94: the full-precision strings
   `'228420390.34615'` and `'58667.5674'` are in the column's own `valor_esperado: 4 unique -> [...]`
   line (89); it is the printed **sample-rows table** three lines below (91-94) that shows the
   truncated scientific notation `5.866757e+04` / `2.284204e+08`. The ticket's note has the two
   structures swapped. The *values* the note and this report use (`58667.5674`,
   `228420390.34615`) are correct either way — verified by the note's own arithmetic
   (`58667.5674 + 228420390.34615 = 228479057.91355`, versus the truncated
   `58667.57 + 228420400 = 228479067.57`) — only which printed block carries them is wrong.
2. **Requirement 3's `CUSTOS.TOTAL` pin (`228479057.91`) does not match what the shipped pipeline
   produces for the reference deck (`228479057.92`), because of a double rounding the requirement's
   arithmetic missed.** `dashboard.payload._build_scalars` rounds `PRESENTE` and `FUTURO` to
   `output.decimals` **individually** before `dashboard.scalars.aggregate_costs` ever sees them
   (`round(58667.5674, 2) = 58667.57`; `round(228420390.34615, 2) = 228420390.35` — this one rounds
   *up*, since its third decimal digit is 6); `aggregate_costs` then sums those two already-rounded
   figures and rounds once more: `round(58667.57 + 228420390.35, 2) = 228479057.92`. The
   requirement's `228479057.91` is `round(58667.5674 + 228420390.34615, 2)` — rounding the raw sum
   directly, which is not the rule `aggregate_costs` implements (its own docstring: `"summed =
   round(sum(values), decimals)"` over already-rounded per-parcel values). `228479057.92` is
   measured by actually running `build_dashboard_data` + `build_payload` over the real reference
   deck; `tests/test_parity.py` uses it, and `test_group_b_reference_deck_custos_total_pin_is_not_vacuous_under_single_parcel_total`
   proves the pin is not vacuous. **This is a one-cent arithmetic slip in the ticket's own
   requirement 3, not a parity defect** — `TEMPO.TOTAL`'s pin (`198.12`) needed no correction, since
   its three group values round-then-sum-then-round to the same figure either way.

A third, smaller correction: Suggested Approach step 5's `make_sintese_dir(..., omit=("TEMPO",))`
does not run as written — `make_sintese_dir`'s own `omit` parameter names full file names
(`"TEMPO.parquet"`), not chart keys, and raises `ValueError` on `"TEMPO"`. `tests/test_parity.py`
uses `omit=("TEMPO.parquet",)`.

## (d) Presentation parity

| Chart family | Legacy figures | New chart(s) | Verdict |
| --- | --- | --- | --- |
| `GHID_SIN` / `GTER_SIN` | 1 each | 1 line chart each | Parity (axis type intentionally differs — see (e)) |
| `GHID_SBM` / `GTER_SBM` / `CMO_SBM` | 4 each (one static file per submarket) | 1 chart each, with a submarket selector | Improved: one series is shown at a time either way, so the selector loses no visibility the legacy had |
| `CUSTOS` | 3 (`Custo Presente`, `Custo Futuro`, `Custo Total de Operação`, each on its own Y axis) | 1 grouped bar chart, one shared linear axis | **Open decision — see below** |
| `TEMPO` | 4 (`Tempo MILP`, `Tempo PL`, `Tempo Leitura de Dados e Impressão`, `Tempo Total`, each `Tempo em Minutos`) | 1 grouped bar chart, one shared linear axis | **Open decision — see below** |

**Do not read this table as "parity passes because the totals agree" (Pitfalls).** The `CUSTOS` and
`TEMPO` rows are presentation *collapses*: the legacy tool gave each series its own Y axis, so a
`PRESENTE`-sized bar and a `FUTURO`-sized bar (about four orders of magnitude apart on the reference
deck, per `reference/parquet-schemas.txt`) were always independently visible; on one shared linear
axis in the new dashboard, the smaller series may be visually flattened.

### Open decision 1 — `CUSTOS`: 3 figures → 1 grouped chart

- **What the legacy did:** `Plotadores/Custos.py` emits three separate figures with the Y-axis
  titles `Custo Presente (R$)` (:34), `Custo Futuro (R$)` (:52) and `Custo Total de Operação (R$)`
  (:77), each on its own axis, each in its own HTML file.
- **What the dashboard does:** one `_scalar("CUSTOS", "Custo Presente, Futuro e Total")` chart, a
  grouped bar chart with three series (`PRESENTE`, `FUTURO`, `TOTAL`) sharing one linear Y axis.
- **Options:**
  - **A — Accept the single grouped chart** as shipped. Cost: `PRESENTE` may be visually flattened
    next to `FUTURO` and `TOTAL` on a shared linear axis (checklist step 29's "read and record" of
    the two cost magnitudes is the evidence the operator needs to judge this for themselves).
  - **B — Add separate `ChartSpec` entries** (one per parcela, or per parcela-vs-total) in a
    follow-up ticket, restoring three independent axes. Cost: three new `ChartSpec` entries in
    `charts/specs.py`, three new `FALLBACK_UNITS` entries, and the seven pinned chart-count
    literals below have to move from 23 to 25 (or more).
- **Not chosen by this ticket.** Already on the developer's open-decision list in
  `.implementation-state.json`.

### Open decision 2 — `TEMPO`: 4 figures → 1 grouped chart (new, not previously recorded)

- **What the legacy did:** `Plotadores/Tempo.py` emits four separate figures — `title="Tempo
  MILP"` (:33), `"Tempo PL"` (:51), `"Tempo Leitura de Dados e Impressão"` (:69) and `"Tempo
  Total"` (:94) — each with `yaxis_title='Tempo em Minutos'`, each in its own HTML file.
- **What the dashboard does:** one `_scalar("TEMPO", "Tempo Computacional")` chart, a grouped bar
  chart with four series (`MILP`, `PL`, `Leitura`, `TOTAL`) sharing one linear Y axis.
- **Options:** the same shape as `CUSTOS` above — **A**, accept the single grouped chart (evidence:
  checklist step 30's four time bars); or **B**, add three or four separate `ChartSpec` entries in
  a follow-up ticket.
- **Not chosen by this ticket.** This is the twin the epic-04 boundary review found unrecorded;
  it is reported to the orchestrator alongside decision 1, for the same developer ruling.

**Re-measured chart-count literal list** (Suggested Approach step 8 asks for a fresh grep, not a
copy from the ticket): `tests/test_builder.py:36`, `tests/test_charts_costs.py:570`,
`tests/test_charts_sin.py:483`, `tests/test_output_size.py:45`, `tests/test_payload.py:33`,
`tests/test_registries.py:32`, `tests/test_chart_specs.py`'s `_ENABLED_KEYS_IN_ORDER` tuple and its
three `42` literals (lines 56, 129, 137) — **plus a seventh location this ticket adds**,
`tests/test_parity.py`'s own `_ENABLED_CHART_COUNT = 23` (used by the file-count-divergence test in
section (e)'s single-file check). Splitting either chart family would need all seven updated.

## (e) Deliberate divergences

Divergences the new dashboard introduces on purpose, each with the decision or spec clause that
authorises it:

1. **Date-typed X axis, not the legacy's categorical axis.** `theme.plotly_layout_template` sets
   `xaxis.type = "date"`; master plan decision 14 (restated as epic decision E5-9) is the
   authority: with stage durations of 0.5, 2, 6 and 8 hours, a categorical axis gives an 8-hour
   stage the same width as a 30-minute one, which visually falsifies the horizon. The legacy's own
   `tickformat="%d/%m/%Y %H:%M"` was inert under its `type='category'` anyway (see (f)). **The
   categorical axis is not offered as an option and is not reopened by this ticket** — a second
   axis mode would be a new settings key, which the epic's scope excludes (requirement 7); reopen
   only on an explicit developer request.
2. **One inlined HTML file, not 21 CDN-loading files.** `dashboard.builder.write_dashboard` writes
   exactly one file; `plotly.offline.get_plotlyjs()` is embedded verbatim rather than loaded from
   `https://cdn.plot.ly`. Authorised by master plan decision 6 (no pre-rendered figures, one
   embedded data store) and epic decision E4-3 (the single self-contained HTML file that opens
   offline). Verified in `test_group_c_new_dashboard_diverges_from_legacy_axis_type_and_output_file_count`.
3. **Submarket line charts (`GHID_SBM`, `GTER_SBM`, `CMO_SBM`) ship one chart with a selector, not
   four static files.** Authorised by `planning-context.md` decision 9 (BI-style selectors) and
   the registry-driven catalogue design (master plan decision 7).
4. **Curated chart titles, not the legacy's Y-axis titles.** `GHID_SIN`'s curated title is
   `"Geração Hidrelétrica"`, while the legacy's Y-axis title for the same data is `"Geração
   Hidráulica (MW)"` — `GHID_SBM`'s curated title, `"Geração Hidráulica"`, does match the legacy
   wording. Authorised by epic decision E3-2 (`payload._build_chart_entry`'s docstring: "title is
   always the curated `spec.title`").
5. **The unit divergence — see (g), given its own section.**

## (f) Legacy defects found while reading — marked NOT REPRODUCED

Four defects in the legacy implementation, found while transcribing it for this ticket. Parity
deliberately does not reproduce any of them:

1. **`.values[0]` silently discards a repeated `etapa` row.** `Plotadores/Tempo.py:22-24` reads
   `.values[0]` for `Leitura` and `MILP`; if either etapa were logged more than once in a run,
   every occurrence after the first would be silently dropped from the plotted runtime. The same
   defect class the epic-02 boundary fixed in consolidation (`finding 1`, where it destroyed 67.8%
   of the `PL` time before the fix). **Proven fixed, not just avoided**, by
   `test_group_c_repeated_etapa_milp_is_summed_not_first_row_only`: a hand-written `TEMPO.parquet`
   with two `MILP` rows of distinct non-zero values shows `dashboard.data.consolidate._load_scalars`'
   groupby-sum reaching the payload, differing from the legacy `.values[0]` result by more than the
   rounding tolerance.
2. **`y` in filesystem-iteration order, paired against a `np.unique`-sorted `x`.**
   `Plotadores/Ghid_SIN.py:26-28` (and the identical pattern in `Gter_SIN.py`, `Ghid_sbm.py`,
   `Gter_sbm.py`, `CMO_sbm.py`) builds `df_plot[caso] = aux["valor"].values` in the order decks were
   concatenated — filesystem (`caminho_pasta.iterdir()`) order, since none of `Leitura/
   leitor_arquivos.py` or any `main_*.py` sorts — while `df_datas["Datas"] = np.unique(aux
   ["data_inicio"])` is always sorted. If decks are read out of date order, the y values are
   silently mispaired against the x axis. **Corrected, not reproduced**: `tests/test_parity.py`'s
   own Group A fixture deliberately names its deck directories so that alphabetical order disagrees
   with date order (`"deck_z"` for 2024-03-03, `"deck_a"` for 2024-03-04), and every chained-series
   comparison concatenates in deck-date order — read independently from each deck's own
   `EST.parquet`, never from a folder name — and still matches the payload.
3. **`df_datas` is filled only from the first scenario.** `Plotadores/Ghid_SIN.py:27`'s
   `if len(df_datas) == 0:` guard means a second scenario with a different timeline is silently
   plotted against the first scenario's timestamps. The new dashboard builds one `TimeAxis` per
   deck date from the deck timelines and warns (`consolidate._check_timeline_coverage`) when a
   scenario's own timeline disagrees with the one selected for that date, rather than silently
   overwriting it.
4. **The `(R$)` cost-axis labels understate the unit by 1000x — see (g).**

## (g) The unit divergence

**The most consequential parity finding of the epic.** Every legacy cost axis is labelled `(R$)` —
`Custo Presente (R$)` at `Plotadores/Custos.py:34`, `Custo Futuro (R$)` at line 52, `Custo Total de
Operação (R$)` at line 77 — plotting `CUSTOS.valor_esperado` unscaled. The values are in **`10^3
R$`**, not plain `R$`, established from the committed `plans/dashboard-dessem/reference/
parquet-schemas.txt` dump (epic decision E5-3, epic-04 boundary review finding 1):

| Anchor | Reported | `CUSTOS` read as `10^3 R$` | Ratio |
| --- | --- | --- | --- |
| `COP_SIN` (`10^3 R$`), `406.6581 R$/h × 144 h` | 58,558.8 | `PRESENTE` = 58,667.5674 | **1.0019** |
| `CFU_SIN` (`10^6 R$`) = `228,917.0446721` | 2.2892e11 R$ | `FUTURO` = 228,420,390.34615 | **0.9978** |

Read as plain `R$`, `FUTURO` is ratio **0.000998** against `CFU_SIN` — 1000x too small.
`METADADOS_OPERACAO.unidade`'s own value set contains `10^3 R$` and `10^6 R$` but never plain `R$`,
and physically, 58,667 R$ of present operating cost for the whole SIN over 144 hours is absurd by
four orders of magnitude.

**The legacy axis label was wrong by a factor of 1000; the new dashboard corrects it.**
`data/schemas.py`'s `FALLBACK_UNITS["CUSTOS"]` is `"10^3 R$"`, consumed by
`Registries.unit_for("CUSTOS")` and rendered as the chart's Y-axis title. This is recorded as a
divergence the new tool introduces **deliberately**, not as something parity should have
reproduced — a parity check comparing only the raw numbers (which match, up to the double-rounding
of (c)) would have missed the one finding that changes what the number on the screen *means*.
