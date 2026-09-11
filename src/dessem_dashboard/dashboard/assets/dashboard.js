// IIFE chart renderer core for the DESSEM comparison dashboard, exposed on window as
// DessemDashboard. Reads the JSON payload ticket-020 exports and the DOM ticket-021 builds; it
// performs no data shaping beyond naming a trace, appending the terminal edge point and reading
// a scenario color, per epic decision E3-1.
(function () {
  // Every payload field this file reads, and no others: KEYS is the single point of contact
  // between this file and the payload's key names, so a later rename breaks the read here
  // instead of silently returning undefined.
  const KEYS = Object.freeze({
    SCHEMA_VERSION: "schema_version",
    DECK_DATES: "deck_dates",
    CHAINED_KEY: "chained_key",
    CHARTS: "charts",
    ENTITIES: "entities",
    ID: "id",
    SCENARIOS: "scenarios",
    SERIES: "series",
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
    LABELS: "labels",
    Y_AXIS_DIFFERENCE_SUFFIX: "y_axis_difference_suffix",
  });

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

  // The one per-chart part of the layout: the Y-axis title, carrying the chart's unit in
  // Absoluto mode and gaining the payload-supplied difference suffix in Diferenca mode. The
  // mode is read through an unquoted object key rather than a second quoted comparison against
  // the Diferenca mode name, because buildTraces already spends this file's one allowed quoted
  // occurrence of that mode name; a second quoted occurrence here would silently double the
  // count a sibling ticket's test locks at one. A missing key (Absoluto, or any other mode)
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
    return layout;
  }

  function renderChart(chartKey) {
    const container = document.getElementById("plot-" + chartKey);
    const traces = buildTraces(chartKey);
    const layout = buildLayout(chartKey);
    const config = {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ["sendDataToCloud"],
    };
    Plotly.react(container, traces, layout, config);
  }

  function renderActiveGroup() {
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

  window.DessemDashboard = {
    get payload() {
      return payload;
    },
    get state() {
      return state;
    },
    axisKey: axisKey,
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
  };

  document.addEventListener("DOMContentLoaded", init);
})();
