---
filesToBeCreated: []
filesToBeModified:
  - tests/test_renderer_contract.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R20, ADR-010]
---

# ticket-008: Static literal-pin guard test for checklist section 10

## Context

### Background

Ticket-007 appends `## 10. Hydro flow charts` to `docs/checklist-manual-dashboard.md`. Epic-04's
Live Defects table recorded that an unguarded checklist section can be deleted by a simplifier
without any test failing. Section 9 then received
`test_checklist_section_9_covers_cost_and_time_bar_charts`, and section 8 has
`test_checklist_replaces_the_placeholder_with_plant_filter_steps` in `tests/test_charts_filters.py`.

ADR-010, which supersedes ADR-007, requires a guard for section 10 "like sections 8 and 9". Those
guards pin literal strings only, and `tests/test_renderer_contract.py` imports nothing from
`dessem_dashboard.charts.registry`. This guard does the same:

- it pins the section-10 strings as literals;
- it does **not** read titles from `enabled_specs()`, because that would turn it into a
  checklist-versus-catalogue drift test. ADR-008 rejected docs-drift tests as over-engineering, and
  design critique round 1 (DES-03) confirmed that rejection.

The R13 order is pinned in the catalogue by `tests/test_chart_specs.py` (ticket-003, ticket-004).
This test only checks that the checklist text states it.

### Current state

`tests/test_renderer_contract.py` has `_read_checklist()` and the section-9 guard at line ~532. The
guard:

1. reads the text;
2. asserts the heading is present;
3. slices from the heading to the next `\n## ` or the end of the file;
4. asserts literal content strings inside that slice, for example `"Custo Presente"`,
   `"03/03/2024 - PRESENTE"` and `"the Y axis reads `min`"`.

Its docstring explains three things: why the section is guarded, why the test does not assert that
nothing follows the section, and the mutation proof it records.

The exact chart titles in `src/dessem_dashboard/charts/specs.py`, measured on `main`, are:

| Group | Key -> title |
| --- | --- |
| SIN flows | `QDEF_SIN` -> `Defluência`, `QTUR_SIN` -> `Turbinamento`, `QVER_SIN` -> `Vertimento` |
| UHE (R13 order) | `GHID_UHE` -> `Geração`, `VARMF_UHE` -> `Volume Armazenado (hm3)`, `VARPF_UHE` -> `Volume Armazenado (%)`, `QAFL_UHE` -> `Vazão Afluente`, `QINC_UHE` -> `Vazão Incremental`, `QDEF_UHE` -> `Defluência`, `QTUR_UHE` -> `Turbinamento`, `QVER_UHE` -> `Vertimento` |

Some titles occur twice. `Defluência`, `Turbinamento` and `Vertimento` appear in both the SIN step
and the UHE step. Bare `Geração` and `Volume Armazenado` are also substrings of SIN titles such as
`Geração Térmica`. The checklist quotes UI strings in backticks (ticket-007, Technical Details), so
pin each title **with its backticks**, for example ``"`Geração`"``. Search for the UHE titles only
from the UHE-order step onwards.

### Target state

A new test, `test_checklist_section_10_covers_hydro_flow_charts`, follows the section-9 shape. It
asserts these literals inside the section-10 slice:

- the heading `## 10. Hydro flow charts`;
- step `33.`, as `"\n33. "`;
- the four mode words `Por deck`, `Encadeado`, `Absoluto` and `Diferença`;
- `charts.disabled` and `QDEF_SIN`;
- the three backticked SIN flow titles, located **before** the UHE-order step;
- the eight backticked UHE titles, in R13 order, located **from** the UHE-order step onwards. Each
  title is searched with `section.index(title, previous_position)`, so the order is enforced and a
  SIN occurrence cannot satisfy a UHE check.

The UHE-order step is the section-10 step that lists the `Usinas hidrelétricas` charts. Locate it by
its literal step number, read from the checklist that ticket-007 wrote (for example `"\n36. "`), and
pin that number as a literal. If you anchored on the first `Usinas hidrelétricas` occurrence instead,
the section's purpose line could mention the tab first and move the anchor.

## Dependencies

- **Blocked By**: ticket-007-checklist-flow-section.md
- **Blocks**: ticket-009-readme-feature-facts.md

## Acceptance Criteria

1. **Given** the checklist from ticket-007, **when** the new test runs, **then** it passes, and
   `grep -n "enabled_specs\|charts.registry" tests/test_renderer_contract.py` prints nothing.
2. **Given** a copy of the checklist with section 10 deleted, **when** the test reads that copy,
   **then** it fails on the heading assertion.
   - Prove this by mutating in place, observing the failure, and restoring the file
     byte-identically (check with `git diff --exit-code docs/`).
   - Record the observed exception in the docstring, as the section-9 test does.
3. **Given** a copy with two UHE titles swapped out of R13 order, for example `Vazão Afluente` and
   `Defluência` in the UHE step, **when** the test runs, **then** the order assertion fails. Prove
   this the same way.
4. **Given** the full gate, **when** it runs, **then** all four commands exit 0 and coverage is at
   least 85%.

## Files

| File | Change |
| --- | --- |
| `tests/test_renderer_contract.py` | One new test function |

## Technical Details

```python
def test_checklist_section_10_covers_hydro_flow_charts() -> None:
    """<why, scope, literal-pin stance (ADR-010, no catalogue read), mutation proof -- mirror the
    section-9 docstring, concisely>"""
    text = _read_checklist()
    heading = "## 10. Hydro flow charts"
    assert heading in text
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    section = text[start:] if end == -1 else text[start:end]

    assert "\n33. " in section
    for literal in ("Por deck", "Encadeado", "Absoluto", "Diferença", "charts.disabled", "QDEF_SIN"):
        assert literal in section

    uhe_step = section.index("\n36. ")  # literal number of the UHE-order step; read it from ticket-007's text
    for sin_title in ("`Defluência`", "`Turbinamento`", "`Vertimento`"):
        assert sin_title in section[:uhe_step]

    position = uhe_step
    for uhe_title in (
        "`Geração`",
        "`Volume Armazenado (hm3)`",
        "`Volume Armazenado (%)`",
        "`Vazão Afluente`",
        "`Vazão Incremental`",
        "`Defluência`",
        "`Turbinamento`",
        "`Vertimento`",
    ):
        assert uhe_title in section[position:], f"{uhe_title} missing or out of R13 order"
        position = section.index(uhe_title, position) + len(uhe_title)
```

Adjust the literals to the text ticket-007 actually wrote:

- the UHE-order step number;
- whether a title is backticked. If ticket-007 did not backtick a title, pin it exactly as written
  and record why in the docstring.

Do not add any import from `dessem_dashboard.charts`.

### Out of scope

- Editing the checklist (ticket-007).
- Guard tests for other sections.
- Moving `_read_checklist`.
- Any catalogue-derived check (ADR-008, DES-03).

### Door, structure budget, debt

The decision is a two-way door. The ticket adds one test function and no helper. It depends on no
debt ticket. Because the titles are literals, this file is not a catalogue pin site. A later
retitle of a UHE chart changes the checklist and this guard together, like any documentation
change.

## Definition of Done

- [ ] All four acceptance criteria are met, and both mutation proofs are recorded in the report.
- [ ] `git diff --exit-code docs/` passes, so the checklist is restored after the mutations.
- [ ] The gate is green and coverage is at least 85%.
- [ ] Commit message (Portuguese): `test: protege a seção 10 do checklist`.
