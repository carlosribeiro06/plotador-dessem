# Epic 03: Dashboard Core

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **outline** — every ticket in this epic carries the `[OUTLINE]` marker and must be
> refined with the learnings of Epics 1 and 2 before dispatch.

## Goal

Turn the `DashboardData` produced by Epic 2 into a single self-contained HTML file that opens
offline with the ONS visual identity and renders the SIN, submarket and interchange charts for every
scenario, with the view-mode toggle, the deck selector, the level navigation and the
Absoluto/Diferença toggle all working.

## Scope

In scope: the brand theme module, the compact JSON payload, the HTML shell with inlined
`plotly.min.js`, inlined CSS and JavaScript and the base64 logo, the JavaScript renderer core, the
view-mode and deck controls, the difference toggle, and the SIN, submarket and interchange chart
rendering.

Out of scope: plant-level charts and their name and code filters, the `CUSTOS` and `TEMPO` bar
charts, and the output size enforcement, which are Epic 4; pipeline wiring, the run against real
data, the parity check and the legacy removal, which are Epic 5.

## Tickets

| Ticket | Title | Points | Detail |
| ------ | ----- | ------ | ------ |
| ticket-019 | Build the brand theme module | 2 | outline |
| ticket-020 | Export the compact JSON payload | 3 | outline |
| ticket-021 | Assemble the single-file HTML shell | 3 | outline |
| ticket-022 | Implement the JavaScript chart renderer core | 3 | outline |
| ticket-023 | Implement the view mode and deck selector | 3 | outline |
| ticket-024 | Implement the absolute and difference toggle | 2 | outline |
| ticket-025 | Render the SIN level charts | 2 | outline |
| ticket-026 | Render the submarket and interchange charts | 3 | outline |

## Dependency Order

```text
ticket-019 ─┐
ticket-020 ─┴─> ticket-021 -> ticket-022 ─┬─> ticket-023 ─┬─> ticket-025 -> ticket-026
                                          └─> ticket-024 ─┘
```

## Refinement Inputs Required

Before these tickets can be refined into detailed tickets, the following must be available:

- `epic-01-learnings.md`: the `Settings` field names, the interpreter used, the error hierarchy.
- `epic-02-learnings.md`: the `DashboardData` accessor names, the `EntityRef` and `TimeAxis` shapes,
  the entity identifier format, the warning wording, the `ChartSpec` field names.
- ~~A decision on whether chart titles come from `ChartSpec.title` or from `Registries.title_for`,
  which ticket-015 made available but did not settle.~~ **RESOLVED 2026-09-10 by the developer** —
  see decision E3-2 below.

## Resolved Epic Decisions

These were settled by the developer on 2026-09-10, before any Epic 3 ticket was refined or
dispatched. They are binding for tickets 019 to 026 and for Epic 4, which inherits the same
renderer and the same title convention.

### E3-1 · Renderer testing: Python-only assertions plus a documented manual checklist

No JavaScript is executed by the test suite and **no new toolchain is added**. Measured input:
`node` and `npm` are not installed in this WSL environment, so a jsdom smoke test would have meant
provisioning a second package manager alongside `uv` for a deliverable that is one offline HTML
file.

Automated, in pytest:

- the exported JSON payload: key set, per-array lengths matching their axis length, rounding to
  `output.decimals`, absence of the `NaN` token;
- the generated HTML: `plotly.min.js` inlined, the logo embedded as base64, **no external
  reference of any kind** (the file must open offline), one container per enabled chart, and the
  total size within the configured budget.

Manual, in a checklist committed under `docs/`, walked once per release: opening the file offline,
the Por deck and Encadeado modes, the Absoluto and Diferença toggle against the reference, the
level navigation, and the plant name and code filters.

**Accepted trade-off, stated explicitly:** the difference computation runs in the browser per
master plan decision 8, so it has no automated test under this choice. Mitigations that are binding
on refinement: keep the JavaScript thin and free of data shaping, do every transformation that can
happen in Python in Python, and make the manual checklist name the exact difference case to verify.
Revisit only if the browser-side logic grows beyond the toggle.

### E3-2 · Chart titles: curated `ChartSpec.title` as the heading, registry long name as a subtitle

The heading is always `ChartSpec.title` from the 42-entry catalogue. `Registries.title_for` supplies
a subtitle or hover text where it differs from the heading, and contributes nothing when it returns
`None`.

Measured rationale, from the real `METADADOS_OPERACAO.parquet` of `exemplo/caso_oficial`:

| chart key | `ChartSpec.title` (heading) | `nome_longo_variavel` (subtitle) |
| --------- | --------------------------- | -------------------------------- |
| `CMO_SBM` | CMO | Custo Marginal de Operação |
| `EARMF_SIN` | EARMF | Energia Armazenada Absoluta Final |
| `VARMF_UHE` | Volume Armazenado (hm3) | Volume Armazenado Absoluto Final |
| `GHID_UHE` | Geração | Geração Hidráulica |
| `GHID_SIN` | Geração Hidrelétrica | Geração Hidráulica |

The registry name is the better text exactly where the curated title is an opaque acronym, which is
why it is kept rather than discarded. But letting it win outright would replace
`Volume Armazenado (hm3)` with `Volume Armazenado Absoluto Final` and so collapse the hm3-versus-%
distinction that master plan open question 2 was resolved by adding, and likewise the
afluente-versus-incremental distinction of open question 3. The heading therefore stays curated and
the registry text is additive. This keeps `title_for` load-bearing rather than dead code, so
ticket-015 requirement 5's `None` contract remains meaningful.

## Open Questions for the Epic

- ~~How the renderer is tested without a browser.~~ **RESOLVED 2026-09-10** — see decision E3-1.
- Whether the deck selector and the level navigation share one URL-hash state so a particular view
  can be linked, which the spec does not require. **Orchestrator ruling 2026-09-10: out of scope.**
  The spec does not ask for linkable views, so adding hash routing would be unrequested scope in an
  epic that already owns the shell, the renderer core and four interactive controls. Refinement must
  not introduce it. Reopen only on an explicit request from the developer.
