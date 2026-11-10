# Design brief — `dessem-specialist`

- **Domain:** DESSEM (daily scheduling: decks, I/O files, methodology, validation)
- **Meets all stated requirements:** True
- **Chosen anchor:** `simplestViable`
- **Reversibility:** `two-way`
- **Rationale:** This domain creates no format, schema, key or API: README wording and test assertions are cheap to change, so the simpler dashboard-contract option wins and synthesis-property checks can be added later if a synthesizer regression ever appears.
- **Confidence:** 80

Rendered by `/plan` P2 from the `design-council` workflow's returned data (schema: `~/.claude/skills/plan/references/design-brief.md`).

## simplestViable

**Description.** Pass the synthesized SIN and UHE flow values through unchanged and pin down only what they mean and what can be tested. (1) README semantics, one short paragraph per flow. QDEF_SIN, QTUR_SIN and QVER_SIN are the synthesized per-stage sums over every plant in the synthesis, in m3/s. This is an aggregate indicator, not a physical system outflow, because cascade water is counted again at every plant it passes. Measured on both example scenarios: SIN = sum of UHE within 3e-11. Vazao Incremental is the natural incremental inflow, which is model input (dadvaz; 22-saidas-deck-b section 2, 'Qincr = dadvaz'), so its Diferenca is zero whenever the scenarios share hydrology. Vazao Afluente adds the upstream outflows, so it depends on upstream decisions and can differ even with the same hydrology. Defluencia is the synthesized 'Vazao Defluente', and the README does not promise Defluencia = Turbinamento + Vertimento, because DESSEM's defluencia also has a diversion term (MM 22.3.0 section 9.6). (2) The real-data test asserts the dashboard contract only, with every size measured from the files instead of hard-coding 169 plants, 80 stages or 48 stages: SIN shows 8 sections and UHE 8, both in R13 order; each SIN flow chart has 1 entity and unit m3/s, and its subtitle equals METADADOS_OPERACAO.nome_longo_variavel read from the file; payload values equal the file `valor` rounded to output.decimals, on the deck axis and on the first chaining.stages_per_deck stages; there are zero warnings. (3) The manual checklist records that Vazao Incremental in Diferenca is a flat zero on the Oficial/Modificado pair, and that this is expected.

**Forgoes.** Nothing would catch a synthesizer regression: SIN no longer equal to the sum of UHE, QDEF redefined to include diversion, or negative turbined or spilled flow. The suite trusts the synthesis files as ground truth and checks only that the dashboard renders them faithfully.

## mostDurable

**Description.** The simplest option, plus a separate, clearly labelled module of real-data synthesis-property tests, kept apart from the dashboard-contract test and skipped when the data is absent. It would assert only relations that stay physically valid when diversion is active. (a) X_SIN = sum over plants of X_UHE per stage, for X in {QDEF, QTUR, QVER}, within a relative tolerance. (b) QDEF_UHE >= QTUR_UHE + QVER_UHE - tol, an inequality rather than an equality, because MM 22.3.0 section 9.6 defines defluencia as turbinamento + vertimento + desvio. (c) QAFL_UHE >= QINC_UHE - tol, because total inflow = incremental + upstream outflows. (d) QTUR, QVER and QDEF >= -tol. It would not assert QINC >= 0, because no available source states it. Measured on both scenarios: (a) max abs 3e-11, (b) equality within 4e-12, (c) min(QAFL - QINC) = 0.0, (d) min = 0.0. It would also log VERSAO.parquet next to the result.

**Costs.** One more test module, with tolerances to choose and justify. It couples the dashboard suite to the synthesizer's behaviour: a change in the synthesizer, or a deck with active diversion, could fail the dashboard suite while the dashboard itself is correct. The R20 requirement does not ask for it, so it borders on over-engineering. It also needs a council or operator decision, because it tests the producer rather than the consumer.

## gaps

- No real deck with PDO_HIDR is on this machine. ~/modelos/dessem/references/decks and ~/projects/dessem do not exist, so validate_outputs.py could not run. I could not check whether the synthesized QDEF_UHE contains the PDO_HIDR Qdesv term. On the example pair, QDEF = QTUR + QVER exactly (0.0) even for Jordao (73) and Moxoto (173), the diversion plants that MM 22.3.0 section 9.6 cites. Either diversion was zero in this run, or the synthesizer defines QDEF as QTUR + QVER. The sources cannot decide between the two, so neither the README nor the tests may state the identity as a DESSEM definition.
- The example pair's VERSAO.parquet reads DESSEM 22.4.1. Per the skill (60-versoes, user info 2026-10-01), 22.4.1 is not yet official at ONS, so all real-data evidence comes from a non-official model version. Nothing shows that the synthesized-file semantics differ across 22.0.2, 22.3.2 and 22.4.1, but this is unverified.
- The tool that writes sintese/ is identified only by inference: the file names follow the sintetizador-dessem pattern (90-fontes-e-versoes, item 3). Its definitions of QAFL and QDEF are not in the available sources, so the README describes the files as 'as synthesized' rather than as derived from specific PDO columns.

## oneWayDoors

_none_

## twoWayDoors

- Location of the real-data test: extending tests/test_integration_exemplo.py or adding a new module gated by exemplo_tree.qualifying_scenarios. The DESSEM content of the assertions is the same either way.
- Whether to add the synthesis-property module (the most durable option) later. The inequality forms (b) to (d) are recorded so that a later decision does not adopt the brittle equalities.
- Exact README wording of the semantics paragraph and of the manual-checklist note on the zero QINC Diferenca.

## contracts

- C1, README semantics (English): each SIN flow chart shows the synthesized SIN file (QDEF_SIN, QTUR_SIN, QVER_SIN), which is the per-stage sum over all plants of the matching *_UHE flow, in m3/s. It is an aggregate indicator: water flowing down a cascade is counted at every plant it passes. Defluencia is the synthesized 'Vazao Defluente'; do not write 'Defluencia = Turbinamento + Vertimento' as a definition, because DESSEM's defluencia includes diversion (MM 22.3.0 section 9.6). Vazao Incremental is model input (natural incremental inflow, dadvaz). Vazao Afluente = incremental + upstream outflows, so it is decision-dependent.
- C2, dashboard-contract assertions for the real-data test (test-strategist / python-task-automation-developer). SIN section order: GTER, GHID, GUNS, EARMF, VARMF, QDEF, QTUR, QVER. UHE order: GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER. Each SIN flow chart has 1 entity and unit m3/s, and its subtitle equals METADADOS_OPERACAO.nome_longo_variavel for that key, read from the file: on the example pair 'Vazao Defluente', 'Vazao Turbinada' and 'Vazao Vertida', with accents. Payload values equal the file `valor` rounded to output.decimals, on each deck axis and on the first chaining.stages_per_deck stages of the chained axis. Zero warnings. Every size (plant count, stage count, chained window) is measured from the files.
- C3, assertions that must NOT be written as dashboard invariants. QINC Diferenca == 0 holds only because the pair shares hydrology (0 of 13,520 rows differ): assert instead that the payload carries both scenarios' arrays equal to their files. QDEF == QTUR + QVER as an equality is a synthesizer or deck property, not a DESSEM identity. QINC >= 0 is not covered by the available sources.
- C4, completeness under R26: after this plan, every flow file the synthesis ships (QAFL_UHE, QINC_UHE, and QDEF, QTUR, QVER at UHE and SIN) has an enabled chart. The synthesis ships no SBM flow file, no SIN QAFL or QINC, and no diversion, pumping or evaporation file, so no-file-no-chart leaves no shipped hydro flow unrepresented.
- C5, R27 isolation: fixing fictitious_codes changes no hydro flow chart. On the example pair every UHE belongs to submarket codes 1 to 4 (117 SE, 33 S, 9 NE, 10 N), and SIN flows are read from the SIN files, not from UHE rows filtered by submarket.
- C6, time semantics: the flows are per-stage rates in m3/s. The example stages are 48 of 0.5 h followed by 32 of 2 to 17 h, and the patamar per stage is consistent between the SIN and UHE files. Step plotting over the datetime axis and stage-wise Diferenca are correct as they stand. The dashboard does no time aggregation, so no duration weighting is needed; a future volume would need m3/s x h x 0.0036 = hm3 (22-saidas-deck-b section 2), which is out of scope.

## questionsForUser

- Council item K1: should the real-data suite also carry the synthesis-property checks, which test the synthesizer rather than the dashboard? If yes, use only the inequality forms in the durable option (SIN = sum of UHE; QDEF >= QTUR + QVER; QAFL >= QINC; non-negative QTUR, QVER and QDEF), never QDEF == QTUR + QVER or QINC Diferenca == 0. My recommendation is no, for now.
