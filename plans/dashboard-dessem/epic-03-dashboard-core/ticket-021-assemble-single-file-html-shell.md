# ticket-021 Assemble the single-file HTML shell

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Produce the single self-contained HTML document: header with the ONS logo and the dashboard title,
navigation and control areas, chart container, mandatory footer, and inlined `plotly.min.js`, CSS,
JavaScript and payload, so the file opens with no server and no network access.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/builder.py`,
  `src/dessem_dashboard/dashboard/assets/dashboard.html`,
  `src/dessem_dashboard/dashboard/assets/dashboard.css`, `tests/test_builder.py`.
- **Key decisions needed**:
  - whether the HTML is a Python format string, a `string.Template`, or a package-data template file
    with placeholder substitution;
  - how the `plotly.offline.get_plotlyjs()` output is inlined, and whether its size of roughly 3 MB
    is acceptable or a reduced bundle should be considered;
  - the logo protection area in CSS that satisfies the brand manual requirement of at least a
    0.5 cm equivalent margin, and the maximum reduction of 50 percent.
- **Open questions**:
  - Does the footer carry only `Gerência de Ferramentas Energéticas - FEN`, or also the run
    timestamp and the git sha for auditability?
  - Is the payload embedded in a `<script type="application/json">` block or as a JavaScript
    assignment? The former avoids escaping problems with the accented Portuguese labels.
  - How is the logo embedded as base64, and what happens when `paths.logo_file` is missing: fatal
    error or a text-only header with a warning?

## Dependencies

- **Blocked By**: `ticket-019-build-brand-theme-module.md`,
  `ticket-020-export-compact-json-payload.md`
- **Blocks**: `ticket-022-implement-js-chart-renderer-core.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
