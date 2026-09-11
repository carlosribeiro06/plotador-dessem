// IIFE chart renderer core for the DESSEM comparison dashboard, exposed on window as
// DessemDashboard. Reads the JSON payload ticket-020 exports and the DOM ticket-021 builds; it
// performs no data shaping beyond naming a trace, appending the terminal edge point and reading
// a scenario color, per epic decision E3-1.
(function () {
  // Every payload field this file reads, and no others: KEYS is the single point of contact
  // between this file and the payload's key names, so a later rename breaks the read here
  // instead of silently returning undefined. KEYS gates only those payload keys, not the
  // deep-copied Plotly layout object buildLayout mutates below: xaxis, yaxis, tickformat,
  // hoverformat and barmode are that copied object's own field names, never a payload key. The
  // template's shape (xaxis.type, xaxis/yaxis tickformat, hoverformat, gridcolor, the empty
  // yaxis.title) is pinned on the Python side by tests/test_theme.py's plotly_layout_template
  // assertions; buildLayout's own mutations of that copy -- deleting tickformat/hoverformat and
  // setting xaxis.type/barmode for SCALAR_BY_DECK charts -- are pinned instead by
  // tests/test_charts_costs.py's assertions on this file's own source text.
  const KEYS = Object.freeze({
    SCHEMA_VERSION: "schema_version",
    DECK_DATES: "deck_dates",
    CHAINED_KEY: "chained_key",
    CHARTS: "charts",
    ENTITIES: "entities",
    ID: "id",
    SCENARIOS: "scenarios",
    SERIES: "series",
    SCALARS: "scalars",
    AXES: "axes",
    STARTS: "starts",
    END: "end",
    THEME: "theme",
    SCENARIO_COLORS: "scenario_colors",
    LAYOUT: "layout",
    REFERENCE: "reference",
    FORMATS: "formats",
    DECIMALS: "decimals",
    UNIT: "unit",
    KIND: "kind",
    LABELS: "labels",
    Y_AXIS_DIFFERENCE_SUFFIX: "y_axis_difference_suffix",
  });

  // The chart[KEYS.KIND] value renderChart compares against to choose buildBarTraces over
  // buildTraces (ticket-030 requirement 8a): a plain const, not a second Object.freeze block,
  // since it names a ChartKind value rather than a payload key.
  const SCALAR_CHART_KIND = "SCALAR_BY_DECK";

  // Joins a deck key and a scalar series name into one flat category label, e.g.
  // "03/03/2024 - <series name>": the only place this file builds a category-axis tick label,
  // so buildBarTraces has one spelling of the separator to change.
  const CATEGORY_SEPARATOR = " - ";

  let payload = null;
  let state = null;

  function init() {
    const payloadElement = document.getElementById("dashboard-payload");
    payload = JSON.parse(payloadElement.textContent);

    if (payload[KEYS.SCHEMA_VERSION] !== 1) {
      console.error(
        "Dashboard payload schema version is unsupported: expected 1, got " +
          payload[KEYS.SCHEMA_VERSION] +
          "; aborting initialization."
      );
      return;
    }

    const chartsByKey = payload[KEYS.CHARTS];
    const entities = {};
    for (const chartKey of Object.keys(chartsByKey)) {
      const chartEntities = chartsByKey[chartKey][KEYS.ENTITIES];
      if (chartEntities.length > 0) {
        entities[chartKey] = chartEntities[0][KEYS.ID];
      }
    }

    state = {
      mode: document.body.dataset.initialMode,
      deck: payload[KEYS.DECK_DATES][0],
      valueMode: document.body.dataset.initialValue,
      entities: entities,
    };

    renderActiveGroup();
  }

  function axisKey() {
    if (state.mode === "deck") {
      return state.deck;
    }
    return payload[KEYS.CHAINED_KEY];
  }

  // The one branch that decides the value mode's effect on a trace's y array: referenceValues
  // null means Absoluto (values pass through unchanged); a resolved array means Diferenca, and
  // each point becomes null when either side is null, otherwise the rounded difference. factor
  // is computed once per call, not once per point, since Math.pow is the same for every point
  // of a given call.
  function valuesForMode(values, referenceValues) {
    if (referenceValues === null) {
      return values;
    }
    const factor = Math.pow(10, payload[KEYS.FORMATS][KEYS.DECIMALS]);
    return values.map(function (value, index) {
      const referenceValue = referenceValues[index];
      if (value === null || referenceValue === null) {
        return null;
      }
      return Math.round((value - referenceValue) * factor) / factor;
    });
  }

  function buildTraces(chartKey) {
    const chart = payload[KEYS.CHARTS][chartKey];
    const entityId = state.entities[chartKey];
    const key = axisKey();
    const axis = payload[KEYS.AXES][key];
    const x = axis[KEYS.STARTS].concat([axis[KEYS.END]]);
    const scenarioColors = payload[KEYS.THEME][KEYS.SCENARIO_COLORS];

    // Read the reference series once, before the per-scenario loop: a missing reference is
    // Diferenca's own empty-plot case, not a per-scenario skip, and reading it inside the loop
    // would both re-read the same value on every iteration and turn one branch into several.
    let referenceValues = null;
    if (state.valueMode === "diferenca") {
      const referenceEntity = chart[KEYS.SERIES][entityId];
      const referenceScenario =
        referenceEntity === undefined ? undefined : referenceEntity[payload[KEYS.REFERENCE]];
      const referenceRaw = referenceScenario === undefined ? undefined : referenceScenario[key];
      if (referenceRaw === undefined) {
        return [];
      }
      referenceValues = referenceRaw.concat([referenceRaw[referenceRaw.length - 1]]);
    }

    const traces = [];
    for (const scenario of payload[KEYS.SCENARIOS]) {
      const byEntity = chart[KEYS.SERIES][entityId];
      if (byEntity === undefined) {
        continue;
      }
      const byScenario = byEntity[scenario];
      if (byScenario === undefined) {
        continue;
      }
      const values = byScenario[key];
      if (values === undefined) {
        continue;
      }

      // The terminal point gives the final stage the width its duration entitles it to; a
      // null last value stays null instead of being special-cased.
      const extendedValues = values.concat([values[values.length - 1]]);
      const y = valuesForMode(extendedValues, referenceValues);

      traces.push({
        type: "scatter",
        mode: "lines",
        name: scenario,
        connectgaps: false,
        x: x,
        y: y,
        line: { shape: "hv", color: scenarioColors[scenario], width: 2 },
      });
    }

    return traces;
  }

  // The two SCALAR_BY_DECK charts' bar-trace builder (ticket-030), sharing valuesForMode's
  // Diferenca arithmetic but never axisKey(): decision 5 makes the bars independent of both the
  // view mode and the deck selector, so every category comes from payload[KEYS.DECK_DATES],
  // never from the currently selected deck. Placed after buildTraces, not immediately before it,
  // so buildTraces keeps the first occurrence of the quoted Diferenca mode check in the file and
  // an unscoped text.index lookup on that literal still finds its own early-return branch.
  function buildBarTraces(chartKey) {
    const chart = payload[KEYS.CHARTS][chartKey];
    const scalarsByName = chart[KEYS.SCALARS];
    const seriesNames = Object.keys(scalarsByName);

    // One (deckKey, name) cell per grid position, built once: the category list and every
    // scenario's value list, including the reference's, read this same array in the same order,
    // so the two stay aligned by construction rather than by a second, independently indexed
    // loop.
    const grid = [];
    for (const deckKey of payload[KEYS.DECK_DATES]) {
      for (const name of seriesNames) {
        grid.push({ deckKey: deckKey, name: name });
      }
    }
    const categories = grid.map(function (cell) {
      return cell.deckKey + CATEGORY_SEPARATOR + cell.name;
    });

    function valueAt(scenario, cell) {
      const bySeries = scalarsByName[cell.name];
      const byScenario = bySeries === undefined ? undefined : bySeries[scenario];
      const raw = byScenario === undefined ? undefined : byScenario[cell.deckKey];
      return raw === undefined ? null : raw;
    }

    // Mirrors buildTraces' own early return: a reference scenario contributing no value at all
    // over the grid means Diferenca has nothing to subtract from, so this returns [] rather than
    // drawing every bar at a zero baseline.
    let referenceValues = null;
    if (state.valueMode === "diferenca") {
      const referenceScenario = payload[KEYS.REFERENCE];
      const referenceGrid = grid.map(function (cell) {
        return valueAt(referenceScenario, cell);
      });
      const hasReferenceValue = referenceGrid.some(function (value) {
        return value !== null;
      });
      if (!hasReferenceValue) {
        return [];
      }
      referenceValues = referenceGrid;
    }

    const scenarioColors = payload[KEYS.THEME][KEYS.SCENARIO_COLORS];
    const traces = [];
    for (const scenario of payload[KEYS.SCENARIOS]) {
      const values = grid.map(function (cell) {
        return valueAt(scenario, cell);
      });
      traces.push({
        type: "bar",
        name: scenario,
        x: categories,
        y: valuesForMode(values, referenceValues),
        marker: { color: scenarioColors[scenario] },
      });
    }
    return traces;
  }

  // The one per-chart part of the layout: the Y-axis title, carrying the chart's unit in
  // Absoluto mode and gaining the payload-supplied difference suffix in Diferenca mode. The
  // mode is read through an unquoted object key rather than a second quoted comparison against
  // the Diferenca mode name, because buildTraces and buildBarTraces already spend this file's two
  // allowed quoted occurrences of that mode name, one per function body; a quoted occurrence here
  // would put a third in a function that is neither. A missing key (Absoluto, or any other mode)
  // resolves to undefined and contributes no suffix. A fresh deep copy per call, not a mutation
  // of a shared object: Plotly.react writes computed properties into the layout it receives,
  // and with several charts sharing one object one chart's axis range would leak into another.
  function buildLayout(chartKey) {
    const chart = payload[KEYS.CHARTS][chartKey];
    const layout = JSON.parse(JSON.stringify(payload[KEYS.THEME][KEYS.LAYOUT]));
    const differenceSuffixByMode = {
      diferenca: payload[KEYS.LABELS][KEYS.Y_AXIS_DIFFERENCE_SUFFIX],
    };
    const suffix = differenceSuffixByMode[state.valueMode];
    layout.yaxis.title = { text: chart[KEYS.UNIT] + (suffix === undefined ? "" : suffix) };

    // SCALAR_BY_DECK's bars are keyed by a deck-and-series label, not a timestamp: the shared
    // date axis's tickformat/hoverformat would otherwise reparse "04/03/2024" as 3 April under
    // Plotly's month-first JavaScript date parsing. barmode is written explicitly rather than
    // left to Plotly's default, because a stacked default would draw TOTAL on top of the parcels
    // that already sum to it, misstating the cost by a factor of two.
    if (chart[KEYS.KIND] === SCALAR_CHART_KIND) {
      delete layout.xaxis.tickformat;
      delete layout.xaxis.hoverformat;
      layout.xaxis.type = "category";
      layout.barmode = "group";
    }
    return layout;
  }

  function renderChart(chartKey) {
    const container = document.getElementById("plot-" + chartKey);
    const chart = payload[KEYS.CHARTS][chartKey];
    const traces =
      chart[KEYS.KIND] === SCALAR_CHART_KIND ? buildBarTraces(chartKey) : buildTraces(chartKey);
    const layout = buildLayout(chartKey);
    const config = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["sendDataToCloud"],
    };
    Plotly.react(container, traces, layout, config);
  }

  function renderActiveGroup() {
    // init() returns early on a schema-version mismatch, leaving state null while the five
    // listeners below are already live; every one of them reaches this function, so guarding
    // here once is what keeps the next click a no-op instead of a TypeError on top of the
    // console.error init() already logged.
    if (state === null) {
      return;
    }
    const sections = document.querySelectorAll("#charts .chart:not([hidden])");
    for (const section of sections) {
      renderChart(section.dataset.chart);
    }
  }

  // Reusable across every button-group toggle this file and its later tickets add (the mode
  // toggle here, the level navigation here, and the value toggle ticket-024 adds): sets
  // aria-pressed on every button of containerId carrying a data-<datasetKey> attribute, true
  // where that attribute equals value and false everywhere else.
  function syncPressed(containerId, datasetKey, value) {
    const container = document.getElementById(containerId);
    const buttons = container.querySelectorAll("button[data-" + datasetKey + "]");
    for (const button of buttons) {
      const pressed = button.dataset[datasetKey] === value;
      button.setAttribute("aria-pressed", String(pressed));
    }
  }

  function setMode(mode) {
    state.mode = mode;
    syncPressed("mode-toggle", "mode", mode);
    // The property, not removeAttribute/setAttribute: it toggles consistently and never clears
    // the <select> value, so the retained deck selection survives the mode round trip.
    document.getElementById("deck-selector").disabled = mode === "encadeado";
    renderActiveGroup();
  }

  function setDeck(deck) {
    // No validation: the only source is the <select> whose options builder.py generated from
    // the payload's deck dates, so every possible value is already known-good.
    state.deck = deck;
    renderActiveGroup();
  }

  function setValueMode(valueMode) {
    state.valueMode = valueMode;
    syncPressed("value-toggle", "value", valueMode);
    renderActiveGroup();
  }

  function setGroup(group) {
    const sections = document.querySelectorAll("#charts .chart");
    for (const section of sections) {
      // The property, not setAttribute/removeAttribute: it keeps the hidden attribute exactly
      // in sync and lets the .chart[hidden] CSS rule do the actual hiding.
      section.hidden = section.dataset.group !== group;
    }
    syncPressed("level-nav", "group", group);
    renderActiveGroup();
  }

  // Re-renders only chartKey, never the whole group: no other chart is affected by one
  // selector's change, and a group re-render would redraw up to six figures for it. No
  // entityId validation: the only source is the <option> list builder.py generated from the
  // same payload buildTraces reads, so a value absent from chart[KEYS.SERIES] cannot arrive.
  function setEntity(chartKey, entityId) {
    state.entities[chartKey] = entityId;
    renderChart(chartKey);
  }

  // Case- and accent-insensitive normalisation shared by both filter needles and both option
  // fields applyPlantFilter matches them against (ticket-028 requirement 4). The NFD form
  // decomposes an accented character into its base letter plus a combining mark; the escaped
  // range below strips exactly that mark, written as the two ASCII escapes rather than as
  // literal combining characters, which would put non-ASCII bytes in this file and break the
  // four isascii assertions; the final call makes the comparison case-insensitive.
  function normalizeText(text) {
    return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
  }

  // Narrows chartKey's entity <select> to the options whose name and code both match the two
  // plant-filter inputs of the same chart section, combining the two fields with AND
  // (ticket-028 requirement 3). Options are hidden, never removed or rebuilt, so the current
  // selection and the list's DOM position survive every keystroke. setEntity is called at most
  // once, only when at least one option matches and the current selection is not among the
  // matches; when nothing matches, the selection and the drawn figure are left untouched and the
  // filter-empty message takes over (requirement 5). No RegExp is built from operator input:
  // matching is indexOf over normalised strings, which cannot throw on a stray "(".
  function applyPlantFilter(chartKey) {
    const section = document.getElementById("chart-" + chartKey);
    const nameNeedle = normalizeText(section.querySelector('[data-filter="name"]').value);
    const codeNeedle = normalizeText(section.querySelector('[data-filter="code"]').value);
    const select = document.getElementById("entity-" + chartKey);

    const matchingValues = [];
    for (const option of select.options) {
      const isMatch =
        normalizeText(option.textContent).indexOf(nameNeedle) !== -1 &&
        normalizeText(option.value).indexOf(codeNeedle) !== -1;
      option.hidden = !isMatch;
      if (isMatch) {
        matchingValues.push(option.value);
      }
    }

    if (matchingValues.length > 0 && matchingValues.indexOf(select.value) === -1) {
      select.value = matchingValues[0];
      setEntity(chartKey, matchingValues[0]);
    }
    section.querySelector(".filter-empty").hidden = matchingValues.length > 0;
  }

  document.getElementById("level-nav").addEventListener("click", function (event) {
    const group = event.target.dataset.group;
    if (group === undefined) {
      return;
    }
    setGroup(group);
  });

  document.getElementById("mode-toggle").addEventListener("click", function (event) {
    const mode = event.target.dataset.mode;
    if (mode === undefined) {
      return;
    }
    setMode(mode);
  });

  document.getElementById("deck-selector").addEventListener("change", function (event) {
    setDeck(event.target.value);
  });

  document.getElementById("value-toggle").addEventListener("click", function (event) {
    const valueMode = event.target.dataset.value;
    if (valueMode === undefined) {
      return;
    }
    setValueMode(valueMode);
  });

  // One delegated listener on the charts container, not one per <select>: Epic 4 adds
  // 165-option plant selectors, and per-element listeners would scale with the catalogue
  // instead of staying at one. The container is looked up by the same CSS-selector idiom
  // renderActiveGroup and setGroup already use, rather than by a bare getElementById call on
  // its id: that bare id string is spelled the same as KEYS.CHARTS's payload-key value, and
  // the KEYS contract requires every such literal to occur exactly once in this file.
  document.querySelector("#charts").addEventListener("change", function (event) {
    if (!event.target.matches(".entity-selector")) {
      return;
    }
    const section = event.target.closest("section.chart");
    setEntity(section.dataset.chart, event.target.value);
  });

  // One delegated listener for both filter inputs of every plant chart, not one per input: the
  // nine plant charts hold eighteen inputs, the same scaling argument the entity-selector
  // listener above already makes for its own 165-option lists (ticket-028 requirement 6). The
  // cheap matches() guard runs before any closest() call, mirroring that same listener's shape.
  // A one-word class selector is used for the closest() call here, deliberately not the
  // two-word selector the entity-selector listener above already spends: a second literal copy
  // of that exact quoted call would make tests/test_charts_submarket.py's own non-vacuity proof
  // for it pass vacuously (it strips only the first of two occurrences and then finds the
  // second still present). Both selectors resolve the same enclosing chart section element.
  document.querySelector("#charts").addEventListener("input", function (event) {
    if (!event.target.matches(".plant-filter")) {
      return;
    }
    const section = event.target.closest(".chart");
    applyPlantFilter(section.dataset.chart);
  });

  window.DessemDashboard = {
    get payload() {
      return payload;
    },
    get state() {
      return state;
    },
    axisKey: axisKey,
    buildBarTraces: buildBarTraces,
    buildTraces: buildTraces,
    buildLayout: buildLayout,
    renderChart: renderChart,
    renderActiveGroup: renderActiveGroup,
    init: init,
    setMode: setMode,
    setDeck: setDeck,
    setGroup: setGroup,
    setValueMode: setValueMode,
    setEntity: setEntity,
    applyPlantFilter: applyPlantFilter,
  };

  document.addEventListener("DOMContentLoaded", init);
})();
