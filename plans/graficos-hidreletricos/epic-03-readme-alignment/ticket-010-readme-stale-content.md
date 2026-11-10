# ticket-010: README stale sections and measured quality-gate table (R28) [OUTLINE]

**Confidence: Low.** This ticket is refined just-in-time after ticket-009. It is the plan's last
ticket.

## Objective

Correct README content that went stale for reasons unrelated to this feature, and re-measure the
quality-gate table on the final tree (ADR-008).

## Anticipated Scope

- `README.md`, the only file.
- **Removed `Avisos` section:** the layout figure, "### Avisos: the eight warning shapes", the
  manifest paragraph and the log paragraph. Warnings now go to the console, the log file and
  `run_manifest.json`.
- **`Execução` versus `Custo`/`Tempo`:** fix the level list and the layout figure. Replace
  "### The two Execução charts" with the seven dedicated bar charts.
- **Quality-gate table:** fill it with values measured from the final gate run: passed and skipped
  counts, test-file count, source-file count and coverage percentage.

## Dependencies

- **Blocked By**: ticket-009-readme-feature-facts.md
- **Blocks**: None

## Notes

- Agent: open-source-documentation-writer.
- Implements R28 and ADR-008.
- Out of scope: feature facts (ticket-009) and any code change.
