# ticket-007 Add the project `CLAUDE.md` and the README skeleton

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `open-source-documentation-writer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem`.

## Context

### Background

`rules/markdown.md` fixes the README structure for this developer: what it is, requirements,
configuration with every settings key and its default, how to run with real commands, structure, and
logging and auditing. In Rigoroso mode that documentation is written in **English**, while the
commands, flags and configuration keys it documents stay as they are, which means the Portuguese
flag names appear verbatim inside English prose. A project-level `CLAUDE.md` is also part of the
`/new-project` convention: it records the implementation mode and the project-specific rules so a
future session does not have to rediscover them. The repository currently has neither.

### Relation to Epic

`ticket-006` finished the runnable command surface, so this ticket can document real commands rather
than planned ones. It is the last content ticket of the epic; `ticket-008` then verifies the
toolchain and appends the verified command output to the README.

### Current State

The repository root has `pyproject.toml`, `settings.json`, `.gitignore`, `LICENSE`,
`plano_dashboard_dessem.md`, the legacy scripts, `logo/`, the brand PDF, `src/dessem_dashboard/`
with seven modules and `tests/` with four test files. `.claude/` exists but contains only
`settings.local.json`. There is no `README.md` and no project `CLAUDE.md`. The repository root
`README.md` must not describe features that do not exist yet, so sections about charts and filters
are written as a short roadmap pointing at `plans/dashboard-dessem/00-master-plan.md`.

## Specification

### Requirements

1. Create `README.md` at the repository root, in English, with these level-2 headings in this order:
   `## What it is`, `## Requirements`, `## Configuration`, `## How to run`, `## Structure`,
   `## Logging and auditing`, `## Development`, `## Roadmap`.
2. `## Configuration` documents **every** top-level group of `settings.json` and every leaf key with
   its meaning and default, transcribed from Appendix B of `plans/dashboard-dessem/00-master-plan.md`,
   as a table narrow enough to read in a terminal.
3. `## How to run` gives the exact WSL commands for creating the environment, installing, and
   invoking `dessem-dashboard --casos ...`, each in a fenced block tagged `bash`, and states that
   only the manifest and the log are produced until Epic 5 is complete.
4. `## Requirements` states Python `>=3.12`, `uv`, the four runtime dependencies, and that the target
   platform is WSL Ubuntu or a Linux server.
5. `## Structure` shows the `src/dessem_dashboard/` tree with a one-line purpose per module, marking
   the modules that do not exist yet as planned.
6. `## Logging and auditing` explains where the log and the manifest are written, how to change the
   level, and which manifest fields exist.
7. Create `CLAUDE.md` at the repository root recording: implementation mode Rigoroso, the bilingual
   policy (English code and documentation, Portuguese user-facing strings), the settings-driven
   configuration rule, the logging rule, the four quality commands, and a pointer to
   `plans/dashboard-dessem/planning-context.md` and `00-master-plan.md` as required reading.
8. Create `.claude/settings.json` with a `permissions.allow` list covering `Bash(pytest*)`,
   `Bash(ruff*)`, `Bash(mypy*)`, `Bash(uv*)` and `Bash(dessem-dashboard*)`, leaving the existing
   `.claude/settings.local.json` untouched.

### Inputs

`settings.json`, `pyproject.toml`, `src/dessem_dashboard/cli.py` and Appendix B of the master plan.

### Outputs and Behavior

Three new files. No code changes and no behavior changes.

### Error Handling

Not applicable: this ticket produces documentation and one JSON configuration file. The JSON must
parse, which acceptance criterion 4 verifies.

## Dependencies

- **Blocked By**: `ticket-006-add-cli-entry-point-and-pipeline-stub.md`
- **Blocks**: `ticket-008-verify-toolchain-quality-gates.md`

## Acceptance Criteria

- [ ] Given `README.md`, when
      `grep -c '^## ' README.md` is run, then it prints `8`, and `grep -n '^## ' README.md` lists the
      eight headings in the order given in requirement 1.
- [ ] Given `README.md` and `settings.json`, when every leaf key path of `settings.json` is
      extracted and searched in `README.md`, then all of them are present, verified by the command
      in the Testing Requirements section exiting 0.
- [ ] Given `CLAUDE.md`, when it is read, then it contains the exact strings
      `Implementation Mode: Rigoroso`, `settings.json` and `plans/dashboard-dessem/planning-context.md`.
- [ ] Given `.claude/settings.json`, when
      `python3 -c "import json,pathlib;d=json.loads(pathlib.Path('.claude/settings.json').read_text());print(len(d['permissions']['allow']))"`
      is run, then it prints `5` and `.claude/settings.local.json` is unchanged.
- [ ] Given `README.md`, when
      `grep -c '^```$' README.md` is run, then it prints `0`, proving every fenced block declares a
      language tag.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Read `settings.json`, `pyproject.toml` and `src/dessem_dashboard/cli.py` to document the real key
   names, dependency bounds and flag names rather than the planned ones.
2. Write `README.md` following the section order of `rules/markdown.md`, translated to English
   headings. Keep paragraphs short and prefer tables and lists.
3. Transcribe the configuration table from Appendix B, splitting it into one table per settings group
   so no table exceeds about 100 characters per line.
4. Write `CLAUDE.md` as a short bullet list: mode, language policy, configuration rule, logging rule,
   commands, required reading. Do not restate the global rules; only what is project-specific.
5. Write `.claude/settings.json` with the five permission entries.
6. Run the acceptance-criteria commands.

### Key Files to Create/Modify

- `README.md` (create)
- `CLAUDE.md` (create)
- `.claude/settings.json` (create)

### Patterns to Follow

- `rules/markdown.md`: fenced blocks always carry a language tag; explain the reasoning behind
  non-obvious decisions; keep tables terminal-readable.
- Document the *why* of the two view modes and of the single-file output in one sentence each,
  linking to the master plan for the full rationale.
- Use `bash` as the language tag for every command block, since the commands are WSL bash.

### Pitfalls to Avoid

- Do not write the README in Portuguese: Rigoroso mode puts documentation in English, while the
  documented flags (`--casos`, `--saida`, `--referencia`) and settings keys stay verbatim.
- Do not promise charts, filters or the HTML output as working features: at the end of Epic 1 only
  the log and the manifest are produced. Say so explicitly in `## How to run`.
- Do not overwrite `.claude/settings.local.json`, which holds the developer local permissions.
- Do not duplicate the whole master plan in the README; link to
  `plans/dashboard-dessem/00-master-plan.md` instead.
- Keep the mandatory footer string `Gerência de Ferramentas Energéticas - FEN` accurate if it is
  quoted, since it is a hard requirement.

### Out of Scope

- The final user documentation with screenshots and chart descriptions (ticket-036).
- Any change to `settings.json`, `pyproject.toml` or Python code.
- A `CONTRIBUTING.md`, a changelog or license text changes.
- Editing `plano_dashboard_dessem.md`, which is the developer original spec.

## Testing Requirements

### Unit Tests

None: this ticket produces documentation and configuration only.

### Integration Tests

Verify the second acceptance criterion with this command at the repository root, which must exit 0
and print nothing:

```bash
.venv/bin/python - <<'PY'
import json, pathlib, sys

def leaves(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip(".")

readme = pathlib.Path("README.md").read_text(encoding="utf-8")
settings = json.loads(pathlib.Path("settings.json").read_text(encoding="utf-8"))
missing = [key for key in leaves(settings) if key.split(".")[-1] not in readme]
if missing:
    print("missing from README:", missing)
    sys.exit(1)
PY
```

Also confirm `python3 -c "import json,pathlib;json.loads(pathlib.Path('.claude/settings.json').read_text())"`
exits 0.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] The README documents every `settings.json` key with its default.
- [ ] `## How to run` states that only the log and the manifest are produced at this stage.
- [ ] `.claude/settings.local.json` is byte-identical to its previous content.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 25 minutes
