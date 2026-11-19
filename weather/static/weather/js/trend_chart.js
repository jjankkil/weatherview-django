'use strict';

import { state } from './state.js';
import { labels } from './render.js';

/** @brief Singleton Chart.js instance; destroyed and recreated on each render. */
let _chartInstance = null;

/**
 * @brief Render (or update) the temperature/precipitation history trend chart.
 *
 * Uses a Chart.js time scale (via chartjs-adapter-date-fns) so temperature and
 * precipitation can have independent resolutions: temperature at 10-minute buckets
 * for a smooth line, precipitation at hourly buckets for one solid bar per hour.
 *
 * @param {Object|null} historyData  Response from /api/station-history/<id>/ or null.
 *   - temp_series:   Array of {time (ISO 8601 UTC), temperature (°C|null)}
 *   - precip_series: Array of {time (ISO 8601 UTC), precipitation (mm/h|null)}
 *   - has_precipitation: boolean
 *   - rain_sum_24h: number|null, total precipitation (mm) over the trailing 24h
 */
export function renderTrendChart(historyData) {
  const section = document.getElementById('trend-section');
  const canvas  = document.getElementById('trend-chart');
  if (!section || !canvas) return;

  const empty = !historyData
    || !historyData.temp_series
    || historyData.temp_series.length === 0;

  if (!state.showHistory || empty) {
    destroyTrendChart();
    return;
  }

  section.classList.remove('hidden');

  const { temp_series, precip_series = [], has_precipitation, rain_sum_24h = null } = historyData;

  // Temperature: {x: ISO timestamp, y: °C}
  const tempData = temp_series.map(b => ({ x: b.time, y: b.temperature }));
  const temperatureValues = tempData
    .map(point => point.y)
    .filter(Number.isFinite);
  const minTemperature = temperatureValues.length ? Math.min(...temperatureValues) : -10;
  const maxTemperature = temperatureValues.length ? Math.max(...temperatureValues) : 10;
  const tempAxisMin = Math.min(-10, Math.floor(minTemperature / 5) * 5);
  const tempAxisMax = Math.max(10, Math.ceil(maxTemperature / 5) * 5);

  if (_chartInstance) {
    _chartInstance.destroy();
    _chartInstance = null;
  }

  const datasets = [
    {
      type: 'line',
      label: labels().tempLegend,
      data: tempData,
      borderColor: '#ff7043',
      backgroundColor: 'rgba(255,112,67,0.08)',
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 3,
      fill: false,
      tension: 0.3,
      yAxisID: 'yTemp',
      spanGaps: true,
      order: 1,
    },
  ];

  renderRainSummary(precip_series, has_precipitation, rain_sum_24h);

  let maxPrecip = 0;
  if (has_precipitation) {
    // Precipitation: {x: ISO timestamp, y: mm/h} — one point per hour.
    // With a time scale Chart.js automatically sizes each bar to span one hour.
    const precipData = precip_series.map(b => ({ x: b.time, y: b.precipitation }));
    maxPrecip = precipData.reduce(
      (max, point) => Number.isFinite(point.y) ? Math.max(max, point.y) : max,
      0,
    );
    datasets.push({
      type: 'bar',
      label: labels().precipLegend,
      data: precipData,
      backgroundColor: 'rgba(74,158,255,0.55)',
      borderColor: 'rgba(74,158,255,0.85)',
      borderWidth: 1,
      // barPercentage < 1 leaves a visible gap between each hourly bar
      barPercentage: 0.85,
      yAxisID: 'yPrecip',
      order: 2,
    });
  }

  const scaleDefaults = {
    ticks: { font: { size: 10 } },
    grid:  { color: 'rgba(255,255,255,0.06)' },
    border: { color: 'rgba(255,255,255,0.1)' },
  };

  _chartInstance = new Chart(canvas, {
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            color: '#8892a0',
            font: { size: 11 },
            boxWidth: 12,
            padding: 12,
          },
        },
        tooltip: {
          backgroundColor: 'rgba(20,28,38,0.92)',
          titleColor: '#c0c8d0',
          bodyColor: '#c0c8d0',
          borderColor: 'rgba(255,255,255,0.12)',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          type: 'time',
          time: {
            unit: 'hour',
            displayFormats: { hour: 'HH' },
            tooltipFormat: 'HH:mm',
          },
          adapters: { date: {} },
          ...scaleDefaults,
          ticks: {
            ...scaleDefaults.ticks,
            color: '#8892a0',
            maxTicksLimit: state.historyHours + 1,
            maxRotation: 0,
          },
        },
        yTemp: {
          type: 'linear',
          position: 'left',
          min: tempAxisMin,
          max: tempAxisMax,
          ...scaleDefaults,
          grid: {
            ...scaleDefaults.grid,
            color: context => context.tick?.value === 0
              ? 'rgba(77,208,225,0.22)'
              : scaleDefaults.grid.color,
            lineWidth: context => context.tick?.value === 0 ? 1.25 : 1,
          },
          ticks: {
            ...scaleDefaults.ticks,
            color: '#ff9575',
            stepSize: 5,
            autoSkip: false,
          },
        },
        ...(has_precipitation ? {
          yPrecip: {
            type: 'linear',
            position: 'right',
            ...scaleDefaults,
            min: 0,
            max: Math.max(5, Math.ceil(maxPrecip / 5) * 5),
            grid: { drawOnChartArea: false },
            ticks: { ...scaleDefaults.ticks, color: '#4a9eff' },
          },
        } : {}),
      },
    },
  });
}

/**
 * @brief Render the two rain sum numbers below the chart: a fixed trailing-24h
 *   total (from the backend, independent of the shown history window) and the
 *   total over the currently shown history window. The shown-window total is
 *   hidden when the history length is 24h, since it would equal the 24h total.
 * @param {Array} precipSeries  Shown-window series: {time, precipitation (mm/h|null)}, one per hour.
 * @param {boolean} hasPrecipitation  Whether the station reports precipitation at all.
 * @param {?number} rainSum24h  Total precipitation (mm) over the trailing 24h, from the backend.
 */
function renderRainSummary(precipSeries, hasPrecipitation, rainSum24h) {
  const summary = document.getElementById('trend-summary');
  const item24h = document.getElementById('trend-summary-24h');
  const itemShown = document.getElementById('trend-summary-total');
  if (!summary || !item24h || !itemShown) return;

  if (!hasPrecipitation || rainSum24h == null) {
    summary.classList.add('hidden');
    return;
  }

  document.getElementById('trend-summary-24h-value').textContent = `${rainSum24h.toFixed(1)} mm`;
  document.getElementById('trend-summary-24h-label').textContent = labels().rainSum24h;
  item24h.classList.remove('hidden');

  const shownHours = precipSeries.length;
  if (shownHours > 0 && shownHours < 24) {
    const shownSum = precipSeries.reduce((acc, b) => acc + (b.precipitation || 0), 0);
    document.getElementById('trend-summary-total-value').textContent = `${shownSum.toFixed(1)} mm`;
    document.getElementById('trend-summary-total-label').textContent = labels().rainSumTotal.replace('{h}', shownHours);
    itemShown.classList.remove('hidden');
  } else {
    itemShown.classList.add('hidden');
  }

  summary.classList.remove('hidden');
}

/**
 * @brief Hide the trend section and destroy the Chart.js instance.
 */
export function destroyTrendChart() {
  if (_chartInstance) {
    _chartInstance.destroy();
    _chartInstance = null;
  }
  const section = document.getElementById('trend-section');
  if (section) section.classList.add('hidden');
}
