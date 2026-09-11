# Manual Release Checklist — Dashboard (Epic 3)

## Purpose

Epic decision E3-1 forbids executing any JavaScript in the automated test suite (`node` and `npm`
are not installed in this WSL environment), so `src/dessem_dashboard/dashboard/assets/dashboard.js`
carries only static, Python-side assertions (`tests/test_renderer_contract.py`). This checklist is
the behavioural gate that stands in for a browser test. Walk it once per release, against the
dashboard HTML file built for that release, and record a pass or fail for every numbered step —
none of them should require interpretation.

Every step below covers the whole of Epic 3 (tickets 019–026): the offline shell, the renderer
core, the view-mode and deck controls, the Absoluto/Diferença toggle, and the SIN, submarket and
interchange charts. The Epic 4 plant-level filters are not in scope; see the placeholder section at
the end of this file.

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

   **Note on the two levels Epic 3 does not populate:** clicking `Usinas hidrelétricas`,
   `Usinas termelétricas` or `Execução` must still switch — the nav button becomes pressed and the
   previous level's charts disappear — but their chart areas are expected to be **empty frames**
   until Epic 4 renders them. Empty plot areas under those three headings are correct at this
   milestone; a nav button that does not respond is not.

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

## Epic 4 placeholder — plant name and code filters (ticket-028)

**Not yet written.** The plant-level (`UHE`/`UTE`) charts' name and code filter controls belong to
Epic 4; ticket-028 owns adding the checklist steps that cover them. Do not fill in this section
before ticket-028 lands.
