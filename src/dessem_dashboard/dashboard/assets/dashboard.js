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
  });

  // ticket-024 replaces this line with a read of the initial value-mode attribute it adds.
  const INITIAL_VALUE_MODE = "absoluto";

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
      valueMode: INITIAL_VALUE_MODE,
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

  function buildTraces(chartKey) {
    const chart = payload[KEYS.CHARTS][chartKey];
    const entityId = state.entities[chartKey];
    const key = axisKey();
    const axis = payload[KEYS.AXES][key];
    const x = axis[KEYS.STARTS].concat([axis[KEYS.END]]);
    const scenarioColors = payload[KEYS.THEME][KEYS.SCENARIO_COLORS];
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
      const y = values.concat([values[values.length - 1]]);

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

  function renderChart(chartKey) {
    const container = document.getElementById("plot-" + chartKey);
    const traces = buildTraces(chartKey);
    // A fresh copy per call: Plotly.react writes computed properties into the layout object it
    // receives, so sharing one object across charts would leak one chart's axis range into
    // another.
    const layout = JSON.parse(JSON.stringify(payload[KEYS.THEME][KEYS.LAYOUT]));
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

  window.DessemDashboard = {
    get payload() {
      return payload;
    },
    get state() {
      return state;
    },
    axisKey: axisKey,
    buildTraces: buildTraces,
    renderChart: renderChart,
    renderActiveGroup: renderActiveGroup,
    init: init,
  };

  document.addEventListener("DOMContentLoaded", init);
})();
