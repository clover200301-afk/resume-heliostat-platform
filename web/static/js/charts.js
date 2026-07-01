// Charts (Chart.js): monthly power/efficiency curve & multi-site comparison.
/* global Chart */

const monthLabels = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];

export function createMonthlyChart (canvas) {
  const ctx = canvas.getContext('2d');
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: monthLabels,
      datasets: [
        {
          type: 'bar', yAxisID: 'y',
          label: '月均功率 (MW)',
          backgroundColor: 'rgba(255, 184, 77, 0.75)',
          borderColor: 'rgba(255, 184, 77, 1)',
          borderWidth: 1,
          data: new Array(12).fill(0),
        },
        {
          type: 'line', yAxisID: 'y1',
          label: '月均光学效率 η',
          borderColor: 'rgba(77, 214, 168, 1)',
          backgroundColor: 'rgba(77, 214, 168, 0.2)',
          pointRadius: 3, pointBackgroundColor: 'rgba(77, 214, 168, 1)',
          tension: 0.3, borderWidth: 2,
          data: new Array(12).fill(0),
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 250 },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.06)' },
             ticks: { color: '#8b94ad' },
             title: { display: true, text: '月份', color: '#8b94ad' } },
        y: { position: 'left',
             grid: { color: 'rgba(255,255,255,0.06)' },
             ticks: { color: '#ffb84d' },
             title: { display: true, text: '功率 (MW)', color: '#ffb84d' } },
        y1: { position: 'right',
              min: 0, max: 1,
              grid: { drawOnChartArea: false },
              ticks: { color: '#4dd6a8' },
              title: { display: true, text: '光学效率 η', color: '#4dd6a8' } },
      },
      plugins: {
        legend: { labels: { color: '#e6ebf5', font: { size: 11 } } },
        tooltip: { backgroundColor: '#1c2436' },
      },
    },
  });
}

export function updateMonthlyChart (chart, monthly) {
  chart.data.datasets[0].data = monthly.map((m) => m.power_mw);
  chart.data.datasets[1].data = monthly.map((m) => m.eta);
  chart.update();
}

export function createCompareChart (canvas) {
  const ctx = canvas.getContext('2d');
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: [],
      datasets: [
        {
          label: '年均功率 (MW)',
          yAxisID: 'y',
          backgroundColor: 'rgba(255, 184, 77, 0.75)',
          borderColor: 'rgba(255, 184, 77, 1)',
          borderWidth: 1,
          data: [],
        },
        {
          label: 'ppa (kW/m²)',
          yAxisID: 'y1',
          backgroundColor: 'rgba(77, 214, 168, 0.7)',
          borderColor: 'rgba(77, 214, 168, 1)',
          borderWidth: 1,
          data: [],
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 250 },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.06)' },
             ticks: { color: '#8b94ad', font: { size: 10 } } },
        y: { grid: { color: 'rgba(255,255,255,0.06)' },
             ticks: { color: '#ffb84d' },
             title: { display: true, text: 'P (MW)', color: '#ffb84d' } },
        y1: { position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { color: '#4dd6a8' },
              title: { display: true, text: 'ppa (kW/m²)', color: '#4dd6a8' } },
      },
      plugins: { legend: { labels: { color: '#e6ebf5', font: { size: 11 } } } },
    },
  });
}

export function updateCompareChart (chart, sites) {
  chart.data.labels = sites.map((s) => s.label);
  chart.data.datasets[0].data = sites.map((s) => s.power_mw);
  chart.data.datasets[1].data = sites.map((s) => s.ppa_kw_m2);
  chart.update();
}
