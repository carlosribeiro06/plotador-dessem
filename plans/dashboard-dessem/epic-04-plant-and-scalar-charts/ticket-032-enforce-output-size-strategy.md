# ticket-032 Enforce the output size strategy

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: last of the epic, strictly after ticket-029 and ticket-031.** The document it
> measures must already contain everything Epic 4 adds — the plant filter markup of ticket-028, the
> `data-kind` attribute of ticket-030 and the aggregated scalars of tickets 030 and 031 — or the
> measured range it pins is stale on the day it lands. It also modifies `dashboard/builder.py`,
> which ticket-028 and ticket-030 modify, so it cannot run in parallel with either.
> **Refined together with ticket-027**, as epic decision E4-3 requires: ticket-027 omits the
> all-`null` arrays and entities, and this ticket measures what that saves and warns when the
> document still grows past the threshold.

## Context

### Background

The master plan's first listed risk is that the embedded JSON grows beyond a usable HTML size with
many decks and scenarios, and it names this ticket as the owner of enforcement. The mitigations are
already in place: columnar arrays keyed by (chart, entity, scenario, deck); one shared time axis per
deck plus one chained axis instead of a timestamp per point; values rounded to `output.decimals`;
absolute series only, with the differences computed in the browser; and, from ticket-027, no array
and no entity made only of `null`. What is missing is the **measurement**: the final size logged, a
warning past `output.size_warning_mb`, and the volumes made available for the run manifest.

The figures that motivate it are measured, not projected. The Epic 3 document is about **4.5 MB** on
the two-scenario fixture, of which 4,293,280 characters are the inlined `plotly.min.js` bundle and
72,648 the base64 logo — so the part this plan actually controls is roughly **213 KB**. At
production scale the picture inverts: the master plan's own estimate is about 8 M embedded values for
30 decks × 3 scenarios, which puts the payload alone near **56 MB** — already past the
`output.size_warning_mb` default of 50 before a single plant chart is added. The warning firing on a
large study is therefore the expected outcome, not a defect, and that is exactly why it must say
something an operator can act on.

Epic decision **E4-3** closed the outline's escalation question before refinement: the payload stays
**fully embedded**. The deliverable is one self-contained HTML file that opens offline with no server
and no sibling files, so a lazy fetch is not a trade that exists; a split output would break the same
requirement; and omitting plant series in Encadeado mode would silently change what the dashboard
shows to save bytes. Size is managed by rounding, by ticket-027's omissions and by this measurement.
Lazy **rendering** is a separate matter and already the design: ticket-023 renders only the active
group, so 165 plant traces are never built until that level is opened. **Do not reopen the
single-file goal.**

The three original key decisions and the two open questions resolve as follows.

- **Exceeding the threshold is a warning and nothing more.** Master plan decision 18's degradation
  rule governs: the run continues and produces the artefact. A 56 MB single file still opens in a
  modern browser, so refusing to write it would deny the operator a usable dashboard to enforce a
  number that is a rule of thumb; and a hard-limit opt-in would be a new settings key, i.e.
  unrequested scope, which is the same argument E4-4 used to keep submarket filtering out.
- **Six integer volumes, not a free-form dict.** `cenarios`, `decks`, `graficos`, `valores`,
  `bytes_html` and `bytes_plotly`. The last two are the pair that makes the payload share visible:
  `bytes_html - bytes_plotly` is the only part of the document the plan can influence, and reporting
  the total alone would hide a payload blow-up behind a 4.3 MB constant. `manifest.write_run_manifest`
  takes `Mapping[str, int]`, and `pipeline.RunResult.data_volumes` is already typed
  `dict[str, int]` with `cenarios` as its stub's only key, so these names fit the contract that
  exists.
- **The size is measured on the written file, and the write stays as it is.** `output_volumes` reads
  `output_file.stat().st_size`, which is the artefact the operator actually ships, and
  `write_dashboard` keeps measuring the in-memory document for its log line — the two agree because
  the write is a plain UTF-8 `write_text`. An atomic write through a temporary file and a rename is a
  different concern (partial-write recovery), unrequested, and would change behaviour that
  `tests/test_builder.py` pins; it stays out.
- **`output.decimals` stays global.** A per-chart rounding would have to travel in the payload,
  because the browser reads a single `formats.decimals` to round the differences it computes, so it
  is a payload-contract change rather than a settings addition. Recorded as deferred, not decided
  against: if `CMO_SBM` values around 0.05 prove to need more precision than `EARMF_SIN` values around
  190 000, that is a developer decision with a payload cost, and ticket-034's run on real data is
  where the evidence will appear.
- **The manifest wiring belongs to ticket-033, not here.** `pipeline.run` is still the Epic 1 stub
  whose body ticket-033 replaces, and that ticket's own objective is to "return the volumes and
  warnings that the CLI records in the run manifest". This ticket therefore delivers the
  measurement and a manifest-ready mapping; wiring it into `RunResult` here would mean writing
  ticket-033's body. The outline's anticipated scope named `pipeline.py`; that is corrected.

### Relation to Epic

The closing ticket of the epic and the gate to Epic 5. It turns the size strategy from a documented
intention into a measured, logged, warned and manifest-ready fact, and it is the first place in the
plan where the cost of the whole embedded payload is asserted as a number rather than assumed.

### Current State

`builder.build_html(data, *, settings, initial_mode)` performs exactly one
`Template.substitute` call, inlining `plotly.offline.get_plotlyjs()`, the CSS, the JSON payload and
the renderer script, and logs one INFO line through `log_step`:
`Payload embutido no documento HTML do dashboard  graficos=23  valores=N  (T s)`.

`builder.write_dashboard(data, *, settings, output_file, initial_mode) -> Path` builds the document,
creates the parent directory, writes it as UTF-8, returns `output_file` **unchanged**, and logs
`Dashboard HTML escrito em disco  caminho=…  bytes=N  (T s)`, where `N` is
`len(document.encode("utf-8"))`. Two tests pin that behaviour:
`test_write_dashboard_tmp_path_returns_path_matching_build_html_output` asserts the returned value
equals `output_file` and that the written text equals `build_html`'s output, and
`test_build_html_and_write_dashboard_log_info_lines_with_volume_fields` asserts the log messages
contain `graficos=23`, `valores=<value_count>`, the output path and
`bytes=<output_file.stat().st_size>`. The return type and the `bytes=` field must therefore survive
this ticket.

`tests/test_builder.py` also asserts `4_300_000 <= len(document) <= 5_242_880`. That lower bound can
never fail — the plotly bundle and the logo alone are 4,365,928 characters — so the upper bound is
the only live half of it, and this ticket adds the assertion that actually watches the payload.

`manifest.write_run_manifest(..., data_volumes: Mapping[str, int] | None = None)` writes
`"data_volumes": dict(data_volumes) if data_volumes is not None else {}`.
`pipeline.run` is the Epic 1 stub: it logs its arguments and returns
`RunResult(output_file=output_file, data_volumes={"cenarios": len(scenario_dirs)})`, with a comment
naming ticket-033 as the ticket that replaces the body.

`settings.output.size_warning_mb` is a `float`, validated positive by `config`, and is `50` in the
repository `settings.json`. `settings.output.decimals` is `2`.

`data.value_count()` is the store's own audit figure: the sum of the series array lengths plus the
number of scalar entries, counting the `None` slots that ticket-027's rules then drop from the
payload. It is the number `write_dashboard` already logs as `valores`, and it stays that number —
the two questions "how much did the store hold" and "how many bytes did the document cost" have two
different answers and both belong in the manifest.

Measured on the `scenario_tree` fixture at the start of this ticket: the document is about 4.51 MB,
the inlined bundle 4,293,280 characters, the base64 logo 72,648, and the part the plan controls —
document minus bundle — about 220 KB, of which roughly 135 KB is the payload's 16 856 embedded
values and the rest the logo, the CSS, the renderer and the shell.

## Specification

### Requirements

1. In `dashboard/builder.py`, add `plotly_bundle_bytes() -> int`, returning
   `len(plotly.offline.get_plotlyjs().encode("utf-8"))` and memoised with `functools.cache` so the
   4.3 MB read happens at most once per process. Do not hard-code the figure: it is a property of the
   installed `plotly` version and the epic-03 learnings already recorded that a future upgrade must
   change it without a code edit.
2. Add `output_volumes(data, *, settings, output_file) -> dict[str, int]` returning exactly six keys
   in this order: `cenarios` (`len(data.scenarios)`), `decks` (`len(data.deck_dates)`), `graficos`
   (the number of enabled specs for these settings), `valores` (`data.value_count()`), `bytes_html`
   (`output_file.stat().st_size`) and `bytes_plotly` (`plotly_bundle_bytes()`). Every value is an
   `int`, so the mapping is directly usable as `write_run_manifest`'s `data_volumes` and as
   `RunResult.data_volumes`. The function reads no parquet and builds no document; it stats one file.
3. Extend `write_dashboard`'s existing `log_step` call with the size in mebibytes, formatted to one
   decimal, **without** removing or renaming the `caminho=` or `bytes=` fields that
   `tests/test_builder.py` asserts. One INFO line, not two.
4. In `write_dashboard`, after the write, emit exactly one Portuguese `logger.warning` when the
   document size exceeds `settings.output.size_warning_mb`, naming the measured size with one
   decimal, the threshold and the dotted settings key `output.size_warning_mb`, and suggesting the
   two actions the operator actually has: comparing fewer decks or fewer scenarios. Emit no warning
   at or below the threshold. Use `logger.warning`, never `data.add_warning`: the document is already
   complete when its size is known, so the Avisos section cannot carry the message, and mutating the
   store at that point would break the non-mutation invariant `tests/test_payload.py` relies on.
5. Exceeding the threshold changes nothing else: the file is written, the path is returned, and no
   exception is raised. Add no settings key, no `--limite` flag, no hard cap and no truncation.
6. Honour E4-3 exactly: the payload stays fully embedded, `build_html` keeps its single
   `Template.substitute` call, `write_dashboard` keeps its single `write_text` call, and no sibling
   file, temporary file, fetch or split output is introduced. Do not reopen the single-file goal and
   do not escalate the outline's question about 30 decks × 3 scenarios — E4-3 answered it.
7. Create `tests/test_output_size.py` asserting: the six volume keys and their values; the
   **controlled share** `bytes_html - bytes_plotly` within a measured range; the warning firing with
   a low threshold and staying silent at the repository default; and the byte saving that
   ticket-027's omission rules produce, measured on a store that actually contains an all-`null`
   entity. Record each measured figure in a comment beside its assertion, as
   `tests/test_builder.py` does for the document range.
8. Change no other file. Not `pipeline.py` — ticket-033 replaces its body and owns the manifest
   wiring — not `cli.py`, not `manifest.py`, not `payload.py`, not `theme.py`, not
   `dashboard/scalars.py`, not any packaged asset, and not `docs/checklist-manual-dashboard.md`.

### Inputs

At run time, the built document, `settings.output.size_warning_mb`, the written file and the
populated `DashboardData`. At test time, the `scenario_tree` fixture, the repository `settings.json`
copied into `tmp_path`, one variant with `output.size_warning_mb` set to `1`, and two stores that
differ only in one entity's arrays.

### Outputs and Behavior

Every run logs one INFO line naming the output path, the byte count and the size in MiB, and a run
whose document exceeds the configured threshold adds one Portuguese WARNING naming the size, the
threshold and the settings key. `output_volumes` returns the six integers the run manifest records,
so an audit of an official run can reconstruct how large the artefact was and how much of it was the
Plotly bundle. Nothing else changes: the same bytes are written to the same path and the same `Path`
is returned.

### Error Handling

No new exception and no new failure mode. A size above the threshold is a warning by requirement 5.
`output_file.stat()` is called only after `write_dashboard` has written the file, so the
`FileNotFoundError` case is a programming error in the caller rather than an operator condition, and
it must propagate rather than be swallowed — the same rule `_read_asset` follows for a missing
packaged asset. `plotly_bundle_bytes()` failing would mean a broken `plotly` installation, which
`build_html` would already have failed on.

## Dependencies

- **Blocked By**: `ticket-029-render-thermal-plant-charts.md`,
  `ticket-031-render-computational-time-bar-charts.md`
- **Blocks**: `ticket-033-wire-end-to-end-pipeline.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture written to `tmp_path` with the repository `settings.json`,
      when `output_volumes` is called on the written file, then its keys are exactly `cenarios`,
      `decks`, `graficos`, `valores`, `bytes_html`, `bytes_plotly`; every value is an `int`;
      `cenarios` is 2, `decks` is 2, `graficos` is 23 and `valores` equals `data.value_count()`;
      `bytes_html` equals `output_file.stat().st_size`; `bytes_plotly` equals
      `len(plotly.offline.get_plotlyjs().encode("utf-8"))`; and `bytes_html > bytes_plotly`.
- [ ] Given the same build, when the controlled share `bytes_html - bytes_plotly` is computed, then
      it lies between 150 000 and 400 000 bytes — measured at about 220 000, of which about 72 600 is
      the base64 logo and about 135 000 the payload's embedded values — so a payload that doubled or
      silently halved fails this assertion while the 4.3 MB constant cannot mask it.
- [ ] Given the fixture built with `output.size_warning_mb` set to `1`, when `write_dashboard` runs,
      then exactly one WARNING record of the `dessem_dashboard.dashboard.builder` logger is emitted,
      its message names `output.size_warning_mb`, the measured size to one decimal and the threshold,
      the returned value still equals `output_file`, and the written text still equals `build_html`'s
      output byte for byte.
- [ ] Given the fixture built with the repository `output.size_warning_mb` of `50`, when
      `write_dashboard` runs, then no WARNING record is emitted by that logger while the INFO line
      naming `caminho=`, `bytes=` and the MiB figure is still present — the pair that makes the
      threshold check non-vacuous, since the fixture document is about 4.5 MB and a bare
      "under 50 MB" assertion could never fail.
- [ ] Given two documents built from stores that differ only in one `GHID_UHE` entity — all-`None`
      arrays in the first, real values of the same lengths in the second — when their sizes are
      compared, then the first is at least 1 500 bytes smaller (2 scenarios × 196 positions × at
      least 4 characters ≈ 1 568 bytes of arrays plus their keys), the first document contains
      neither that entity's `<option>` nor its `series` key while the second contains both; and
      `.venv/bin/pytest tests/test_output_size.py tests/test_builder.py tests/test_manifest.py
      tests/test_charts_hydro.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Add `plotly_bundle_bytes` and `output_volumes` next to `write_dashboard`, both public and both
   docstringed in English, naming in the docstring who consumes them (ticket-033's `pipeline.run`
   feeding `manifest.write_run_manifest`).
2. Compute `graficos` with `len(enabled_specs(disabled=settings.charts.disabled))`, the same call
   `build_html` makes, rather than re-counting the document's sections: the two must agree, and one
   source of truth is how they stay that way.
3. Put the threshold comparison in `write_dashboard` immediately after the `log_step` call, working
   from the same byte count, so there is exactly one place the size is computed.
4. Convert with `1024 * 1024`, not `1e6`, and say MB in the Portuguese message as the settings key
   does — `size_warning_mb` is the operator's vocabulary, and mixing MiB arithmetic with a MB label
   is a documented rounding of the same order as the threshold itself. Format with one decimal.
5. Build the two comparison stores of criterion 5 by consolidating the fixture once, then calling
   `set_entities("GHID_UHE", existing + (extra,))` and `add_series` for the extra entity on both
   scenarios across the two deck axes and the chained axis — all-`None` tuples for the first store,
   tuples of a constant float of the same lengths for the second. `add_series` validates the length
   against the axis, so use 50, 50 and 96. `tests/test_builder.py`'s
   `test_build_html_entity_label_with_ampersand_and_less_than_escapes_in_option_text` is the
   precedent for hand-building a store and calling `build_html` on it.
6. Write the low-threshold variant by copying `settings.json` into `tmp_path` and editing the one
   key, never by mutating a loaded `Settings`: every settings dataclass is frozen.
7. Assert the absence of a WARNING as a filtered count over `caplog.records` for that logger name,
   not as `len(caplog.records) == 0`: other loggers legitimately emit during a build, and the
   filtered-count rule is the one Epic 2 learnings section 7 recorded after an unfiltered count
   nearly shipped.
8. Prove each assertion can fail: set the threshold to `0.001` and confirm criterion 4 fails; invert
   the comparison operator and confirm criterion 3 fails; fill the all-`None` arrays and confirm
   criterion 5's size difference collapses below the floor. Restore each. The last mutation is the
   one that matters, because it is the only evidence that ticket-027's omission is what produces the
   saving.
9. Run the whole suite once at the end. It takes about 10 minutes — measured at 564 s and 618 s in two epic-boundary runs, not the 220 s an earlier draft claimed — and this is the last ticket of the
   epic, so the epic-boundary gate — `ruff check`, `ruff format --check`, `mypy src`,
   `pytest --cov` — runs against the complete Epic 4 surface.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/builder.py` (modify: `plotly_bundle_bytes`, `output_volumes`, the
  extended log line and the threshold warning)
- `tests/test_output_size.py` (create)

### Patterns to Follow

- `log_step`'s keyword-field style for the INFO line, keeping the existing field names.
- `_warn_omitted_charts`' Portuguese `logger.warning` style, naming the dotted settings key, and
  `_logo_data_uri`'s habit of naming both the key and the resolved value.
- `functools.cache` on a pure, argument-less reader, the same discipline `_read_asset` follows by
  never caching a mutable result.
- The settings-copy-in-`tmp_path` pattern for a variant, and the hand-built-store pattern of
  `tests/test_builder.py` for a document with a controlled payload.
- The measured-range assertion style of the epic-03 learnings: a range with the measured value
  recorded beside it, never a budget the artefact cannot reach.

### Pitfalls to Avoid

- Do not change `write_dashboard`'s return type. Two assertions in `tests/test_builder.py` depend on
  it returning `output_file`, and ticket-033 can call `output_volumes` separately — that is why it
  takes `output_file` rather than being folded into the writer's result.
- Do not remove or rename the `bytes=` or `caminho=` log fields.
  `test_build_html_and_write_dashboard_log_info_lines_with_volume_fields` asserts both, and the
  second field is how an operator finds the artefact in a log.
- Do not assert "under 50 MB" on the fixture. The document is about 4.5 MB, so such an assertion can
  never fail — one of the three can-never-fail commands the Epic 3 refinement caught in its own
  drafts, and the reason criterion 4 is paired with criterion 3.
- Do not assert the total document size instead of the controlled share. The 4.3 MB Plotly constant
  is 95 percent of the document and would mask a doubling of the payload.
- Do not hard-code the Plotly bundle size. It is a property of the installed version; the epic-03
  learnings already recorded that a future upgrade must fail loudly in one place rather than drift
  silently.
- Do not write the size warning into the Avisos section or through `data.add_warning`. The document
  exists before its size is known, and mutating the store during or after payload building breaks an
  invariant `tests/test_payload.py` asserts.
- Do not raise on an oversized document, and do not add a settings key for a hard limit. Decision 18
  makes degradation the rule, and a 56 MB file still opens.
- Do not introduce an atomic write, a temporary file or a second `write_text` call. It is unrequested,
  and `test_write_dashboard_missing_parent_directory_creates_it` pins the current behaviour.
- Do not touch `pipeline.py`. Its body is ticket-033's, and editing it here would put two tickets in
  the same function with one of them unable to test it end to end.
- Do not measure the saving against the default fixture alone. It contains no all-`None` entity —
  ticket-027's rules have nothing to drop there — so a saving assertion over the plain fixture would
  be unsatisfiable, which is why criterion 5 builds the two stores explicitly.
- Do not use an unfiltered `caplog` count. A build legitimately logs from `payload`, `consolidate`
  and `builder`, so the absence assertion must filter by logger name.

### Out of Scope

- The manifest wiring, the `RunResult` fields and the CLI reporting (ticket-033), and any `--dry-run`
  flag reporting volumes without writing.
- Any lazy, fetched, split or partially embedded payload; any per-chart `output.decimals`; any hard
  size limit or opt-in error; any compression, minification or base64 change of the logo.
- Any change to what is embedded: the chart catalogue, the rounding, the entity omission rules of
  ticket-027 and the scalar aggregations of tickets 030 and 031 are all already decided and shipped.
- Any change to `pipeline.py`, `cli.py`, `manifest.py`, `payload.py`, `theme.py`,
  `dashboard/scalars.py`, the packaged assets or the manual checklist.
- Re-measuring or re-pinning the document range `tests/test_builder.py` already asserts.

## Testing Requirements

### Unit Tests

`tests/test_output_size.py`:

- the five acceptance criteria;
- `output_volumes` with `charts.disabled = ["VARPF_UHE"]`: `graficos` is 22 and `valores` falls,
  proving both figures follow the settings rather than being constants;
- the returned mapping is JSON-serialisable and round-trips through `write_run_manifest` into a
  `run_manifest.json` whose `data_volumes` equals it, proving requirement 2's manifest-ready claim
  against the real writer rather than by inspection;
- `plotly_bundle_bytes()` returns the same value on two calls and equals the direct
  `len(get_plotlyjs().encode("utf-8"))`, so the memoisation is exercised rather than assumed;
- the warning message contains no ISO date and no path-less phrasing: it names the size, the
  threshold and `output.size_warning_mb`, and the assertion is on those three substrings;
- the four non-vacuity mutations of Suggested Approach step 8, each confirmed to fail before
  restoration.

### Integration Tests

None automated here. The size of the document built from the **real** example tree, where the
projected 56 MB at 30 decks × 3 scenarios becomes observable, is ticket-034's run; this ticket gives
that run the number to report. The manual checklist gains no step: a byte count is not a visual
property.

## Definition of Done

- [ ] The two files exist — one modified, one created — and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent, and the full suite —
      about 10 minutes — is green, since this is the epic-boundary run.
- [ ] `write_dashboard` still returns `output_file`, still writes the same bytes, and still logs
      `caminho=` and `bytes=`; the MiB figure is an added field on the same INFO line.
- [ ] The threshold produces exactly one Portuguese WARNING above it and none at or below it, proven
      by the criterion 3 and criterion 4 pair.
- [ ] `output_volumes` returns the six documented integer keys and round-trips through
      `write_run_manifest`.
- [ ] No file outside `src/dessem_dashboard/dashboard/builder.py` and `tests/test_output_size.py` was
      touched; `pipeline.py` still carries its ticket-033 stub comment.
- [ ] The payload is still fully embedded: `build_html` performs one `Template.substitute` call,
      `write_dashboard` one `write_text` call, and the document still contains no `http://` or
      `https://` outside the inlined Plotly bundle.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 30 minutes. The outline's 2 points hold,
with the scope corrected on two counts: `pipeline.py` is not touched, because ticket-033 owns the
manifest wiring, and the measurement is asserted as a **range over the controlled share** rather than
against the threshold, because the fixture document is 4.5 MB and the threshold is 50 MB, so any
assertion against the threshold alone could never fail. The weight is in the two stores that make the
omission saving measurable and in the warning's fires/stays-silent pair. Confidence is High: every
figure is measured on the fixture and nothing here depends on a browser.
