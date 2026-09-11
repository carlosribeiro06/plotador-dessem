# Manual Release Checklist — Dashboard

## Purpose

Epic decision E3-1 forbids executing any JavaScript in the automated test suite (`node` and `npm`
are not installed in this WSL environment), so `src/dessem_dashboard/dashboard/assets/dashboard.js`
carries only static, Python-side assertions (`tests/test_renderer_contract.py`). This checklist is
the behavioural gate that stands in for a browser test. Walk it once per release, against the
dashboard HTML file built for that release, and record a pass or fail for every numbered step —
none of them should require interpretation.

Steps 1 to 20 cover the whole of Epic 3 (tickets 019–026): the offline shell, the renderer core,
the view-mode and deck controls, the Absoluto/Diferença toggle, and the SIN, submarket and
interchange charts. Steps 21 to 26 cover Epic 4's plant name and code filters (ticket-028). Steps
27 to 32 cover Epic 4's cost and time bar charts (tickets 030–031).

Interface strings are quoted exactly as they render, in Portuguese, because that is the language of
every dashboard UI string (`CLAUDE.md`); the prose around them is English, per the Rigoroso mode
policy.

## 1. Offline load and console check

This step comes first because it is the only JavaScript syntax gate `dashboard.js` has: epic
decision E3-1 means no test parses this file, so a syntax error would otherwise ship unnoticed.

1. Disable network access on the machine (airplane mode, or disconnect Wi-Fi/Ethernet) before
   opening the file, so a silent network dependency cannot hide behind a working connection.
2. Open the built `dashboard_dessem.html` file directly from disk (`file://...`), by double-clicking
   it or via the browser's "Open File" dialog — not through a local web server.
3. Open the browser's developer console (F12 or equivalent) and reload the page once with the
   console already open.

   **Expected result:** the page renders the ONS header, the level navigation, the controls and the
   five initially visible SIN charts; the console reports no error of any kind. Any error here is a
   defect in `dashboard.js` and must be fixed before release, since no other gate would catch it.

## 2. ONS visual identity

4. Confirm the header shows the ONS logo image (not a broken-image icon) to the left of the title.
5. Confirm the footer text reads exactly `Gerência de Ferramentas Energéticas - FEN`.

   **Expected result:** the logo renders at readable size; the footer text matches the quoted string
   verbatim, with no missing accents or truncation.

## 3. Level navigation

6. Confirm the level navigation bar (`#level-nav`) shows exactly six buttons, in this order:
   `SIN`, `Submercado`, `Intercâmbio`, `Usinas hidrelétricas`, `Usinas termelétricas`, `Execução`.

   **Expected result:** six buttons, in that order, each with the exact Portuguese label quoted
   above.

7. Click `Submercado`.

   **Expected result:** the five SIN charts disappear, the six `Submercado` charts appear in their
   place, and the `Submercado` button becomes the pressed one while `SIN` stops being pressed. Click
   back to `SIN` and confirm the reverse. Level switching is a re-render, not a page reload, so the
   browser must not navigate.

   **Note on the three plant-level and scalar headings:** clicking `Usinas hidrelétricas`,
   `Usinas termelétricas` or `Execução` must switch — the nav button becomes pressed and the
   previous level's charts disappear — and each of those three levels now renders its own charts
   (Epic 4, tickets 027–031; verified by steps 21 to 32 below). An empty plot area under any of
   those three headings is a **defect**, exactly like a nav button that does not respond.

## 4. Por deck and Encadeado modes

8. Confirm the mode toggle (`#mode-toggle`) shows two buttons labelled `Por deck` and `Encadeado`.
9. Switch to `Por deck` mode. Confirm the deck selector (the `Deck` dropdown, `#deck-selector`)
   becomes usable and lets you pick one of the individual deck dates.
10. While in `Por deck` mode, pick a deck and inspect a chart's time axis: confirm that a 6-hour
    stage renders six times wider along the horizontal axis than a 30-minute stage of the same
    deck, since master plan decision 14 keeps a true date axis rather than one evenly-spaced tick
    per stage.
11. Switch to `Encadeado` mode. Confirm the deck selector is disabled while this mode is active,
    since the chained axis does not read from a single deck.

    **Expected result:** both mode buttons render with the quoted labels; the deck selector's
    enabled state matches the active mode; stage width on the time axis is visibly proportional to
    stage duration, not uniform.

## 5. Absoluto and Diferença toggle

This is the one computation E3-1 accepts as untested by the automated suite, because master plan
decision 8 puts the difference arithmetic in the browser. Verify it against this concrete case.

12. Build the dashboard for the bundled two-scenario example (do not run this command as part of an
    automated check; it is the manual reproduction case for this release):

    ```bash
    dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi
    ```

    Because `--referencia` defaults to the first `--casos` directory's basename, the reference
    scenario for this build is `caso_oficial`.
13. Select the chart `GHID_SIN` and switch to `Encadeado` mode.
14. Hover the point at timestamp `04/03/2024 12:00` (point 73 of 96 on the chained axis, since
    chaining takes the first 48 half-hour stages of each deck: the chained axis runs
    03/03/2024 00:00–23:30 followed by 04/03/2024 00:00–23:30) and write down the `caso_oficial` and
    `caso_gurobi` values shown in the hover tooltip.
15. Switch the value toggle (`#value-toggle`) from `Absoluto` to `Diferença`.

    **Expected result:** the `caso_oficial` trace is a flat line at zero across the whole axis,
    since it is its own reference; the `caso_gurobi` trace's value at `04/03/2024 12:00` equals
    `caso_gurobi - caso_oficial` (the two absolute values recorded in step 14), rounded to the
    number of decimals configured in `output.decimals` in `settings.json`. The chart's Y-axis
    title must also switch: it reads `MW (diferença)` while Diferença is the active toggle, and
    reverts to the bare `MW` the moment Absoluto is reselected.

## 6. Submarket and interchange-pair selectors

16. Navigate to a chart with a submarket entity selector (for example `CMO_SBM`, labelled
    `Submercado`) and confirm its `<select>` offers one option per submarket, each showing the
    submarket's Portuguese label (for example `SE (SUDESTE)`).
17. Navigate to a chart with an interchange-pair entity selector (for example `INT_SBP`, labelled
    `Par de submercados`) and confirm its `<select>` offers one option per submarket pair, each
    showing a label of the form `<origem> para <destino>`.

    **Expected result:** both selectors are populated, ordered, and their options' Portuguese
    labels match what the corresponding chart plots when an option is picked.

18. Still inside the `Submercado` level, pick a **different** submarket on two different charts —
    for example `SE (SUDESTE)` on `CMO_SBM` and `S (SUL)` on `MER_SBM`. Then switch to another
    level and back.

    **Expected result:** each chart keeps its own selection. The two selectors do not synchronise,
    picking on one does not redraw the other, and both choices survive the level round trip. Entity
    selection is per chart by design (ticket-026 requirement 5), so a shared selection is a defect.

## 7. Avisos section

19. Build (or reuse a build of) a scenario tree where one scenario is missing a deck date that
    another scenario has, so `DashboardData.add_warning` records the gap.
20. Confirm a section headed `Avisos` renders below the controls and above the charts, listing one
    Portuguese warning message per missing combination.

    **Expected result:** the `Avisos` section is present only when there is at least one warning,
    and every listed message names the affected scenario and deck date.

## 8. Plant name and code filters

The plant-level (`UHE`/`UTE`) charts' entity `<select>` narrows as the operator types into either
of two text inputs, by hiding the options that stop matching (ticket-028). Option hiding inside a
native `<select>` element is browser-dependent behaviour that no Python assertion can observe,
which is why -- like every other interactive check in this document -- it is verified here rather
than in the automated suite (epic decision E3-1).

21. Navigate to `Usinas hidrelétricas` and open one of its charts (for example `Geração`). Type a
    partial plant name into the `Filtrar por nome` field.

    **Expected result:** the entity dropdown narrows, as each character is typed, to only the
    options whose name contains the typed text, matched case- and accent-insensitively; the chart
    redraws to the first matching plant whenever the plant it was showing no longer matches, and
    stays put otherwise.

22. Clear the name field and type a partial plant code into the `Filtrar por código` field.

    **Expected result:** the dropdown narrows the same way, this time to the options whose code
    contains the typed digits.

23. With the code field still holding text, also type a partial name into the `Filtrar por nome`
    field, choosing a name and a code that both match at least one common plant.

    **Expected result:** only the options matching both the name filter and the code filter
    remain in the dropdown, proving the two fields combine with AND rather than widening the list.

24. Type, in either field, text that matches no plant.

    **Expected result:** the message `Nenhuma usina corresponde ao filtro` appears under the two
    fields, every option stays hidden, and the chart keeps showing the curve it displayed before
    the non-matching text was typed -- it must not blank or reset.

25. Clear both fields.

    **Expected result:** the full option list returns unfiltered, and the message from step 24 is
    no longer shown.

26. On two different charts of the `Usinas hidrelétricas` level (for example `Geração` and
    `Turbinamento`), type a different filter into each and pick a different plant on each. Then
    switch to another level and back.

    **Expected result:** each chart keeps its own filter text and its own selected plant; the two
    charts' filters and selections do not synchronise with each other, and both survive the level
    round trip.

## 9. Cost and time bar charts

`Custo Presente, Futuro e Total` and `Tempo Computacional` (tickets 030 and 031) are the
dashboard's only two grouped-bar charts; every other step above verifies a line chart. Both render
through the same kind-driven bar path, so this one section covers them together.

27. Navigate to `Execução`.

    **Expected result:** two charts appear, `Custo Presente, Futuro e Total` and `Tempo
    Computacional`, each drawing vertical bars rather than lines.

28. On `Custo Presente, Futuro e Total`, hover any bar and read its category label on the X axis.

    **Expected result:** each category label combines a deck date and a parcel name (for example
    `03/03/2024 - PRESENTE`) -- never a raw timestamp and never a date the browser has reparsed,
    since the label is the same deck key shown elsewhere in the dashboard. One bar per scenario
    appears at each category, in the scenario's own colour.

29. Still on the cost chart, hover over one category (the unified hover shows every bar at that
    category at once) and compare the `TOTAL` bar's value against the sum of the parcel bars
    beside it.

    **Expected result:** at every category, `TOTAL` equals the sum of the parcel bars beside it,
    to the number of decimals configured in `output.decimals`.

    As a known and accepted caveat: `PRESENTE` and `FUTURO` are expected to differ by orders of
    magnitude, so the `PRESENTE` bar may be invisible at the default zoom next to `FUTURO` and
    `TOTAL`. Read it through the unified hover instead, or a box zoom on the Y axis around the
    smaller bars. A log axis was rejected for this chart because it cannot render the signed
    Diferença view of step 31 below -- a log scale has no representation for a negative or zero
    difference. **Read and record** the two magnitudes shown for `PRESENTE` and `FUTURO` at one
    category on this build: that measurement, not an assumption, is what settles whether the scale
    gap is large enough to warrant a further ticket.

    As a reference order of magnitude -- a value read from the committed
    `reference/parquet-schemas.txt` dump, not a promise about this build's own data -- `PRESENTE`
    is about `5.87e4` and `FUTURO` is about `2.28e8`, both in `10^3 R$`, on that reference deck. If
    this build's own `PRESENTE`/`FUTURO` pair differs from that pair by a further factor of about
    1000 in either direction, suspect a unit regression on the Y-axis label (epic-04 boundary
    review finding 1) rather than accepting the chart at face value.

30. On `Tempo Computacional`, repeat steps 28 and 29 for the `MILP`, `PL`, `Leitura` and `TOTAL`
    bars.

    **Expected result:** the Y axis reads `min`. Record the four values shown for `MILP`, `PL`,
    `Leitura` and `TOTAL` at one category rather than judging them against a plausibility band --
    a single etapa can legitimately run from under a minute to close to two hours, so no fixed
    band is a valid pass/fail criterion. The one relation that must hold exactly, to the configured
    decimals, is `TOTAL == MILP + PL + Leitura`. As a reference value -- read from the committed
    `reference/parquet-schemas.txt` dump, not a promise about this build's own data -- `TOTAL` on
    the reference deck is the sum of every row of `TEMPO.tempo` divided by 60, about `198.1` min.

31. Switch the value toggle (`#value-toggle`) from `Absoluto` to `Diferença` while `Execução` is
    the active level.

    **Expected result:** on both charts, the reference scenario's bars fall to exactly zero at
    every category, every other scenario's bar becomes `scenario - referência`, and each chart's
    Y-axis title gains the suffix ` (diferença)`.

32. Switch back to `Absoluto`, then exercise the mode toggle (`Por deck` / `Encadeado`) and the
    deck selector while `Execução` stays active.

    **Expected result:** neither bar chart changes at all -- the bars, their categories and their
    values are identical across every combination of view mode and deck (`planning-context.md`
    decision 5), since both charts already show every deck at once.
