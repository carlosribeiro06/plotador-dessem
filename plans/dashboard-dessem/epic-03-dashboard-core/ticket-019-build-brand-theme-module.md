# ticket-019 Build the brand theme module

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Every visual constant of the dashboard must have exactly one home, or the CSS, the Plotly layout and
the scenario colour assignment drift apart and brand compliance becomes a matter of opinion (master
plan risk "brand compliance judged by eye"). `planning-context.md` fixes the facts: brand green
`#486018` and brand gray `#606060` sampled from the provided logo, the auxiliary palette `#4F8AD8`
blue, `#F76C00` orange, `#D10429` red and `#FBC90B` yellow with **at most three auxiliary colours
combined with the brand colours**, tints of 80/60/40/20 percent allowed, Arial for web, white plot
background, light-gray grid, `hovermode` set to `x unified`, a logo protection area of at least a
0.5 cm equivalent, and no reduction of the logo below 50 percent of its natural size. This ticket
turns those facts into one typed Python module and creates the `dashboard` package that the rest of
Epic 3 fills in.

Four of the five open questions this ticket originally carried were settled by orchestrator rulings
on 2026-09-10 and are recorded as requirements below: the reference scenario always takes brand
green whatever its position in `--casos`; scenarios beyond the fourth use the 60 percent tints of
the first four; and the tint function, the Plotly layout template and the CSS custom properties all
live in Python, which follows from epic decision E3-1 keeping the JavaScript thin.

The fifth question — generated CSS versus hand-written CSS with a test asserting it matches the
Python constants — is resolved here as a third option that keeps a single source of truth without
generating layout rules: `theme.css_root_block()` emits **only** the `:root` custom-property
declaration, and the hand-written `dashboard.css` of ticket-021 reaches those values through
`var(--ons-*)` and is forbidden from containing any colour literal. Layout, spacing and media rules
stay hand-authored where they belong; the brand values exist once, in Python; and the invariant is
enforced by a test that fails the moment a hexadecimal colour appears in the stylesheet.

### Relation to Epic

First ticket of the epic, alongside ticket-020. It creates the `dessem_dashboard.dashboard` package
and the `dessem_dashboard.dashboard.assets` package marker, so ticket-021 only adds asset files, and
it supplies the two values ticket-021 passes into `payload.build_payload`: `scenario_colors(...)`
and `plotly_layout_template(...)`. Every later ticket of Epics 3 and 4 reads its colours, fonts and
layout from here and declares no visual constant of its own.

### Current State

`src/dessem_dashboard/` holds `__init__.py`, `errors.py`, `config.py`, `logging_setup.py`,
`manifest.py`, `cli.py`, `pipeline.py`, `py.typed` and the three subpackages `models/`, `data/` and
`charts/`. **There is no `dashboard/` subpackage at all**, so every path this ticket touches is new.
`pyproject.toml` already declares `[tool.setuptools.package-data]` for
`"dessem_dashboard.dashboard.assets"`, a package that does not yet exist; `mypy` runs `strict` over
`src` and `ruff` selects 20 rule families with `line-length = 100`. The provided logo is
`logo/MarcasONS_Secundarias_verticais_Verde.png`, measured 786 × 622 pixels and 54 484 bytes.
`settings.json` supplies `dashboard.date_format = "%d/%m/%Y %H:%M"`.

## Specification

### Requirements

1. Create `src/dessem_dashboard/dashboard/__init__.py` and
   `src/dessem_dashboard/dashboard/assets/__init__.py`, each holding one English module docstring and
   nothing else, so both packages exist and the `pyproject.toml` package-data key
   `"dessem_dashboard.dashboard.assets"` resolves to a real package that `setuptools` will ship.
   **Do not edit `pyproject.toml`**: the key is already correct and the missing package is the gap.
2. Create `src/dessem_dashboard/dashboard/theme.py` declaring exactly five brand hexadecimal
   literals, each `Final[str]`: `BRAND_GREEN = "#486018"`, `BRAND_GRAY = "#606060"`,
   `AUXILIARY_BLUE = "#4F8AD8"`, `AUXILIARY_ORANGE = "#F76C00"` and `AUXILIARY_RED = "#D10429"`,
   plus `WHITE = "#FFFFFF"` as the sixth and last literal. The auxiliary yellow `#FBC90B` of the
   brand manual is **deliberately not declared**: `planning-context.md` caps the palette at three
   auxiliary colours combined with the brand colours, this dashboard spends them on blue, orange and
   red, and an unused constant is dead code. State that reason in the module docstring, naming the
   colour in words as "the brand manual auxiliary yellow" and **never by its hexadecimal value**, so
   it is not "restored" later and so the six-literal count of the Definition of Done still holds.
3. Expose `tint(color: str, fraction: float) -> str`, blending `color` towards `WHITE` while keeping
   `fraction` of its ink: each channel becomes `round(fraction * channel + (1 - fraction) * 255)`,
   re-rendered as an uppercase `#RRGGBB` string. Raise `ValueError` for a `color` that does not match
   `#RRGGBB` in upper or lower case hexadecimal digits, and for a `fraction` outside the half-open
   interval `(0.0, 1.0]`.
4. Derive every remaining colour instead of writing a new literal:
   `GRID_COLOR: Final[str] = tint(BRAND_GRAY, 0.2)`, the brand manual 20 percent tint, which
   evaluates to `"#DFDFDF"`.
5. Declare the non-colour visual constants: `FONT_FAMILY: Final[str] = "Arial, Helvetica, sans-serif"`
   (the manual mandates Arial for web and open documents; the two fallbacks cover a machine without
   Arial installed), `FONT_SIZE_PX: Final[int] = 12` (legacy parity),
   `CHART_HEIGHT_PX: Final[int] = 450` (legacy parity), `LOGO_MIN_WIDTH_PX: Final[int] = 393`
   (exactly 50 percent of the 786 pixel width of the provided logo, the largest reduction the manual
   permits) and `LOGO_PADDING_PX: Final[int] = 24` (about 0.63 cm at 96 dpi, above the 0.5 cm
   protection area).
6. Declare `SCENARIO_PALETTE: Final[tuple[str, ...]] = (BRAND_GREEN, AUXILIARY_BLUE,
   AUXILIARY_ORANGE, AUXILIARY_RED)` and `TINT_FRACTION: Final[float] = 0.6`.
7. Expose `scenario_colors(scenarios: Sequence[str], *, reference: str) -> dict[str, str]`. Build the
   slot order as `[reference, *(name for name in scenarios if name != reference)]`, so the
   **reference scenario always takes `BRAND_GREEN` whatever its position in `--casos`**
   (orchestrator ruling 2026-09-10: it is the baseline of the Diferença view, and a baseline colour
   that moved with argument order would be surprising). Slot `i` takes `SCENARIO_PALETTE[i % 4]`
   unshaded while `i < 4`, and `tint(SCENARIO_PALETTE[i % 4], TINT_FRACTION ** (i // 4))` from slot 4
   on, so **scenarios beyond the fourth use the 60 percent tints of the first four** exactly as
   `planning-context.md` proposes, and a ninth scenario continues the same rule at 36 percent instead
   of repeating a colour. Raise `ValueError` when `reference` is not in `scenarios`.
8. Expose `plotly_layout_template(*, date_format: str) -> dict[str, object]`, returning the shared,
   chart-independent Plotly layout: `font` built from `FONT_FAMILY`, `FONT_SIZE_PX` and `BRAND_GRAY`;
   `paper_bgcolor` and `plot_bgcolor` set to `WHITE`; `hovermode` set to `"x unified"`; `showlegend`
   true with a horizontal legend below the plot; `autosize` true and `height` set to
   `CHART_HEIGHT_PX`; margins leaving no room for a Plotly title; `xaxis` with `type` `"date"`,
   `tickformat` and `hoverformat` both set to `date_format`, and `gridcolor` set to `GRID_COLOR`;
   `yaxis` with `gridcolor` set to `GRID_COLOR`, `zeroline` true and an empty `title` text. The
   returned mapping **must not contain a top-level `title` key**: the chart heading is HTML per epic
   decision E3-2, and a Plotly title would duplicate it.
9. Expose `css_root_block() -> str`, returning a `:root { ... }` CSS declaration whose custom
   properties are exactly `--ons-green`, `--ons-gray`, `--ons-white`, `--ons-grid`,
   `--ons-font-family`, `--ons-font-size`, `--ons-logo-width` and `--ons-logo-padding`, in that
   order, each carrying the corresponding constant with `px` appended to the three pixel values.
   Custom-property names are identifiers, therefore **English**, per the bilingual policy in
   `CLAUDE.md`.
10. The module performs no I/O, configures no logging handler, and imports nothing beyond the
    standard library. It needs no `logging.getLogger` call: a pure constants-and-functions module has
    no step boundary to audit.

### Inputs

`scenario_colors` takes the scenario labels in `--casos` order, which is `DashboardData.scenarios`,
and the reference label, which is `DashboardData.reference`. `plotly_layout_template` takes
`Settings.dashboard.date_format`. Everything else is a module constant.

### Outputs and Behavior

Plain immutable values — strings, integers and tuples — plus freshly built dictionaries. Each call to
`plotly_layout_template` and `css_root_block` returns a new object, so a caller mutating the layout
for one chart cannot corrupt another chart.

### Error Handling

`ValueError` from `tint` for a malformed colour or an out-of-range fraction, and from
`scenario_colors` for a reference absent from the scenario list. These are English-message
programming errors and deliberately **not** `DashboardError` subclasses: the reference-membership
case is already rejected upstream by `DashboardData.__init__` with a Portuguese `StoreError`, so
reaching it here means a caller bypassed the store and a traceback is the correct outcome. Do not add
an eighth class to `errors.py`.

## Dependencies

- **Blocked By**: `ticket-018-implement-series-consolidation.md`
- **Blocks**: `ticket-021-assemble-single-file-html-shell.md`

## Acceptance Criteria

- [ ] Given the new module, when `tint` is exercised, then `tint("#486018", 0.6)` returns
      `"#91A074"`, `tint("#606060", 0.2)` returns `"#DFDFDF"`, `tint("#FFFFFF", 1.0)` returns
      `"#FFFFFF"`, and both `tint("486018", 0.6)` and `tint("#486018", 0.0)` raise `ValueError`.
- [ ] Given the three scenarios `("caso_a", "caso_b", "caso_c")` and `reference="caso_c"`, when
      `scenario_colors(scenarios, reference="caso_c")` is called, then it returns exactly
      `{"caso_c": "#486018", "caso_a": "#4F8AD8", "caso_b": "#F76C00"}`, proving the reference takes
      brand green from the **third** argument position.
- [ ] Given the five scenarios `("s1", "s2", "s3", "s4", "s5")` and `reference="s1"`, when
      `scenario_colors` is called, then `result["s5"]` equals `"#91A074"`, which is
      `tint(BRAND_GREEN, 0.6)`, and `len(set(result.values()))` equals `5`.
- [ ] Given `plotly_layout_template(date_format="%d/%m/%Y %H:%M")`, when the returned mapping is
      read, then `layout["hovermode"]` equals `"x unified"`, `layout["xaxis"]["tickformat"]` and
      `layout["xaxis"]["hoverformat"]` both equal `"%d/%m/%Y %H:%M"`, `layout["plot_bgcolor"]` equals
      `"#FFFFFF"`, `layout["yaxis"]["gridcolor"]` equals `"#DFDFDF"`, `layout["height"]` equals
      `450`, and `"title"` is not a key of `layout`.
- [ ] Given `css_root_block()`, when its text is inspected, then it starts with `":root {"`, the
      custom-property names found by `re.findall(r"--[a-z-]+", text)` equal the eight documented
      names in the documented order, it contains the substrings `"--ons-green: #486018;"`,
      `"--ons-grid: #DFDFDF;"` and `"--ons-logo-width: 393px;"`, and
      `.venv/bin/pytest tests/test_theme.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Create the two `__init__.py` files first, each with a single English docstring line, then confirm
   `.venv/bin/python -c "import dessem_dashboard.dashboard.assets"` succeeds.
2. Write `theme.py` top-down: module docstring stating that this is the single source of every visual
   constant and why the auxiliary yellow is absent; the six literals; `tint`; the derived
   `GRID_COLOR`; the non-colour constants; `SCENARIO_PALETTE` and `TINT_FRACTION`;
   `scenario_colors`; `plotly_layout_template`; `css_root_block`.
3. Implement `tint` with a compiled `re.Pattern` for `#RRGGBB` and a comprehension over the three
   channel slices, formatting with `f"#{r:02X}{g:02X}{b:02X}"`. Validate the fraction before touching
   the colour, so the message names the wrong argument.
4. Implement `scenario_colors` as one dict comprehension over `enumerate(slot_order)` delegating to a
   small private `_slot_color(index)`; keep the palette indexing and the tint exponent inside that
   single helper so the ruling lives in one place.
5. Build `css_root_block` from an explicit tuple of `(name, value)` pairs rather than from `locals()`
   or `dir()`, so the emitted set is reviewable and the ordered name list in the fifth acceptance
   criterion is a real contract.
6. Write `tests/test_theme.py` covering the five acceptance criteria plus the cases listed under
   Testing Requirements.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/__init__.py` (create)
- `src/dessem_dashboard/dashboard/assets/__init__.py` (create)
- `src/dessem_dashboard/dashboard/theme.py` (create)
- `tests/test_theme.py` (create)

### Patterns to Follow

- `Final` annotations on module constants and `from __future__ import annotations` at the top, as in
  `data/schemas.py`.
- English identifiers, English docstrings, minimal comments (Rigoroso). The only Portuguese this
  module may contain is none at all: it produces no operator-facing text.
- Return concrete `dict` and `tuple` values, never a mutable module-level dictionary shared between
  callers, mirroring how `charts/registry.py` hands out immutable specs.

### Pitfalls to Avoid

- Do not write `#FBC90B` anywhere. Requirement 2 excludes it on purpose and a later
  `code-simplifier` pass would delete it as dead code, producing a pointless diff.
- Do not hard-code `"#DFDFDF"`: it must be `tint(BRAND_GRAY, 0.2)`, so the grid provably stays a
  brand-manual tint. The literal and the derived value agree today; only the derivation survives a
  future correction to the brand gray.
- Do not put the scenario colours in the CSS custom properties. They depend on the run scenario
  labels and reach the browser through the payload built by ticket-020; the `:root` block is
  run-independent.
- Do not add a Plotly `title` to the layout, and do not set `xaxis.type` to `"category"`. Master plan
  decision 14 requires a true date axis, because a categorical axis gives an 8-hour stage the same
  width as a 30-minute stage and visually falsifies the horizon.
- Do not accept a `fraction` of `0.0` as a "white" shortcut: requirement 3 rejects it, because a
  fully white series line is invisible on the white plot background.
- `round()` uses banker rounding. The three tint values asserted in the acceptance criteria were
  computed with it (`round(223.2) == 223`, `round(159.6) == 160`); do not substitute `math.floor` or
  `int()`.

### Out of Scope

- `dashboard.css` itself, and the enforcement test that it contains no colour literal: both belong to
  ticket-021, which creates the stylesheet.
- The JSON payload, including where the scenario colours and the layout template sit inside it:
  ticket-020 owns the payload key names.
- The HTML template, the base64 logo embedding and any consumer of `LOGO_MIN_WIDTH_PX`
  (ticket-021).
- Per-chart layout parts: the Y-axis unit title (ticket-025) and the Diferença suffix (decided in
  ticket-024, implemented in ticket-025).
- Bar-chart colours for `CUSTOS` and `TEMPO` (Epic 4, tickets 030 and 031).

## Testing Requirements

### Unit Tests

`tests/test_theme.py`:

- `tint` on the three asserted values, plus the lower-case input `"#486018"` written with lower-case
  hexadecimal digits returning the same upper-case output;
- `tint` raising `ValueError` for `"486018"`, `"#48601"`, `"#GGGGGG"`, `0.0` and `1.5`;
- `GRID_COLOR` equals `tint(BRAND_GRAY, 0.2)`, asserted as that identity rather than against a
  literal;
- `scenario_colors` for one, two, three, four and five scenarios, with the reference in first, middle
  and last argument position, asserting green lands on the reference every time;
- `scenario_colors` returning pairwise distinct values for eight scenarios, and raising `ValueError`
  when the reference is absent;
- `plotly_layout_template` field by field, including the absence of `title` and the fact that two
  successive calls return objects that are not the same instance, so mutating one cannot affect the
  other;
- `css_root_block` name list, order and the three asserted substrings.

### Integration Tests

None. This module has no external input; the visual result is verified by the manual checklist
created in ticket-022 and by the assertions ticket-021 makes on the generated HTML.

## Definition of Done

- [ ] The four files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pyproject.toml` is unmodified, verified with `git diff --stat pyproject.toml` printing nothing,
      and `.venv/bin/python -c "import dessem_dashboard.dashboard.assets"` exits 0.
- [ ] `theme.py` contains exactly six hexadecimal colour literals, verified with
      `grep -o "#[0-9A-Fa-f]\{6\}" src/dessem_dashboard/dashboard/theme.py | wc -l` printing `6`.
      Use `grep -o` piped to `wc -l`, not `grep -c`, which counts matching **lines** and would read
      `6` even if two literals shared one line.
- [ ] No file outside the four listed above is modified, in particular not `errors.py`, which keeps
      its seven classes.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
