// Top-level controller that wires together: map, 3D scene, UI sliders,
// charts, and the backend APIs.
//
// State lives in a single `state` object; any change calls
// `refresh(level)`:
//   - 'fast'   → recompute sun direction locally + redraw 3D scene only
//   - 'instant'→ same as fast + fetch /api/instant for accurate efficiencies
//   - 'annual' → same as instant + fetch /api/annual for the monthly chart
//
// Most UI sliders only trigger 'instant'; map click also triggers 'annual'.

import { Scene } from './scene.js';
import { sunVector, dni as dniJs } from './solar.js';
import { createMap } from './map.js';
import { createMonthlyChart, updateMonthlyChart,
         createCompareChart, updateCompareChart } from './charts.js';

const state = {
  lat: 39.4,
  lng: 98.5,
  altKm: 3.0,
  clear: 1.0,
  date: '2023-06-21',
  time: 12.0,
  mirrorSize: 5.0,      // metres, in [2, 8], step 0.5
  nMirrors: 0,          // populated from the /api/field response
  candidates: [],
};

async function api (path, body) {
  const r = await fetch(`/api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`api/${path} failed: ${r.status}`);
  return r.json();
}

async function fetchField (mirrorSize) {
  const r = await fetch(`/api/field?mirror_size=${mirrorSize}`);
  return r.json();
}

// ------------------------------------------------------------------
// Debounce utility
// ------------------------------------------------------------------
function debounce (fn, wait) {
  let h = null, lastArgs = null;
  return (...args) => {
    lastArgs = args;
    clearTimeout(h);
    h = setTimeout(() => fn(...lastArgs), wait);
  };
}

// ------------------------------------------------------------------
// DOM helpers
// ------------------------------------------------------------------
const $ = (id) => document.getElementById(id);

function fmt (x, digits = 2) {
  if (x === null || x === undefined || isNaN(x)) return '—';
  return Number(x).toFixed(digits);
}

function setKpis (m, sun) {
  $('kpiPower').innerHTML = `${fmt(m.power_full_mw, 1)} <small>MW</small>`;
  $('kpiPpa').innerHTML = `${fmt(m.ppa_kw_m2, 3)} <small>kW/m²</small>`;
  $('kpiDni').innerHTML = `${fmt(m.dni, 3)} <small>kW/m²</small>`;
  $('kpiEta').textContent = fmt(m.efficiencies.total, 3);
  $('kpiSun').textContent =
    `${fmt(sun.alt_deg, 1)}° / ${fmt(sun.az_deg, 0)}°`;
  const e = m.efficiencies;
  $('kpiEffs').textContent =
    `${fmt(e.cos, 2)} / ${fmt(e.sb, 2)} / ${fmt(e.trunc, 2)}`;
}

function setAnnual (a) {
  $('annualPower').textContent = fmt(a.annual.power_mw, 2);
  $('annualPpa').textContent = fmt(a.annual.ppa_kw_m2, 3);
  $('annualEta').textContent = fmt(a.annual.eta, 3);
}

function setLabels () {
  const h = Math.floor(state.time);
  const m = Math.round((state.time - h) * 60);
  const tstr = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  $('lblTime').textContent = tstr;
  $('lblAlt').textContent = `${state.altKm.toFixed(1)} km`;
  $('lblClear').textContent = state.clear.toFixed(2);
  const sizeEl = $('lblSize'); if (sizeEl) sizeEl.textContent = `${state.mirrorSize.toFixed(1)} m`;
  const nEl = $('lblN'); if (nEl) nEl.textContent = `${state.nMirrors} 面`;
  const latStr = `${Math.abs(state.lat).toFixed(2)}°${state.lat >= 0 ? 'N' : 'S'}`;
  const lngStr = `${Math.abs(state.lng).toFixed(2)}°${state.lng >= 0 ? 'E' : 'W'}`;
  $('lblLat').textContent = latStr;
  $('lblLng').textContent = lngStr;
  const bt = $('badgeTime'); if (bt) bt.textContent = tstr;
  const bl = $('badgeLoc');  if (bl) bl.textContent = `${latStr} ${lngStr}`;
}

// ------------------------------------------------------------------
// Refresh pipeline
// ------------------------------------------------------------------
function refreshSceneLocal () {
  // Local-only sun + mirror reorientation, no backend round-trip.
  const sun = sunVector(state.lat, state.date, state.time);
  Scene.updateSun(sun.vec, dniJs(sun.altDeg * Math.PI / 180, state.altKm, state.clear));
  Scene.updateTrajectory((t) => {
    const s = sunVector(state.lat, state.date, t);
    return s.altDeg > 0 ? s.vec : null;
  });
}

const refreshInstant = debounce(async () => {
  try {
    const m = await api('instant', {
      lat: state.lat, lng: state.lng,
      altitude_km: state.altKm, clearness: state.clear,
      date: state.date, time_hours: state.time,
      mirror_size: state.mirrorSize,
    });
    setKpis(m, m.sun);
    Scene.updateMirrors(m.per_mirror_eta);
  } catch (e) { console.warn(e); }
}, 220);

const refreshAnnual = debounce(async () => {
  try {
    const a = await api('annual', {
      lat: state.lat, lng: state.lng,
      altitude_km: state.altKm, clearness: state.clear,
    });
    setAnnual(a);
    updateMonthlyChart(monthlyChart, a.monthly);
  } catch (e) { console.warn(e); }
}, 350);

const refreshField = debounce(async () => {
  try {
    const field = await fetchField(state.mirrorSize);
    state.nMirrors = field.n;
    setLabels();
    Scene.rebuildMirrors(field);
    refreshSceneLocal();
    refreshInstant();
  } catch (e) { console.warn('refreshField', e); }
}, 300);

function refresh (level) {
  setLabels();
  refreshSceneLocal();
  if (level === 'fast') return;
  refreshInstant();
  if (level === 'annual') refreshAnnual();
}

// ------------------------------------------------------------------
// Site comparison
// ------------------------------------------------------------------
let monthlyChart, compareChart, mapApi;

function renderSiteList () {
  const ul = $('siteList');
  ul.innerHTML = '';
  state.candidates.forEach((c, idx) => {
    const li = document.createElement('li');
    li.innerHTML = `
      <span>${c.label}</span>
      <span style="color:#ffb84d">${fmt(c.power_mw, 1)} MW</span>
      <span style="color:#4dd6a8">${fmt(c.ppa_kw_m2, 3)} kW/m²</span>
      <button class="rm" data-i="${idx}">✕</button>`;
    li.querySelector('.rm').addEventListener('click', () => {
      state.candidates.splice(idx, 1);
      mapApi.clearCandidates();
      state.candidates.forEach((cc) => mapApi.addCandidate(cc.lat, cc.lng, cc.label));
      renderSiteList();
      updateCompareChart(compareChart, state.candidates);
    });
    ul.appendChild(li);
  });
  $('compareHint').textContent =
    state.candidates.length === 0
      ? '点击「保存为对比场地」收集更多候选'
      : `已收集 ${state.candidates.length} 个候选场地`;
}

async function saveCurrentAsCandidate () {
  const a = await api('annual', {
    lat: state.lat, lng: state.lng,
    altitude_km: state.altKm, clearness: state.clear,
  });
  const label = `(${state.lat.toFixed(1)}°, ${state.lng.toFixed(1)}°, ${state.altKm.toFixed(1)} km)`;
  const cand = {
    label, lat: state.lat, lng: state.lng,
    altKm: state.altKm, clear: state.clear,
    power_mw: a.annual.power_mw,
    ppa_kw_m2: a.annual.ppa_kw_m2,
    eta: a.annual.eta,
  };
  state.candidates.push(cand);
  mapApi.addCandidate(cand.lat, cand.lng, label);
  renderSiteList();
  updateCompareChart(compareChart, state.candidates);
}

// ------------------------------------------------------------------
// Day-playback
// ------------------------------------------------------------------
let playing = null;
function togglePlay () {
  if (playing) {
    clearInterval(playing); playing = null;
    $('btnPlay').textContent = '▶ 播放一天';
    return;
  }
  $('btnPlay').textContent = '⏸ 暂停';
  let t = 5.0;
  playing = setInterval(() => {
    t += 0.15;
    if (t > 19.5) t = 5.0;
    state.time = Math.round(t * 10) / 10;
    $('time').value = state.time;
    refresh('instant');
  }, 90);
}

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------
async function main () {
  // 1. fetch heliostat field with the initial mirror size, build 3D scene
  const field = await fetchField(state.mirrorSize);
  state.nMirrors = field.n;
  await Scene.init($('scene'), field);

  // 2. map
  mapApi = createMap('map', state.lat, state.lng, (lat, lng) => {
    state.lat = lat; state.lng = lng;
    refresh('annual');
  });

  // 3. charts
  monthlyChart = createMonthlyChart($('chartMonthly'));
  compareChart = createCompareChart($('chartCompare'));

  // 4. sliders
  $('date').addEventListener('input', (e) => {
    state.date = e.target.value; refresh('annual');
  });
  $('time').addEventListener('input', (e) => {
    state.time = parseFloat(e.target.value); refresh('instant');
  });
  $('alt').addEventListener('input', (e) => {
    state.altKm = parseFloat(e.target.value); refresh('annual');
  });
  $('clear').addEventListener('input', (e) => {
    state.clear = parseFloat(e.target.value); refresh('annual');
  });
  $('nmirrors')?.remove?.();   // no-op if the old id is gone
  const msize = $('msize');
  if (msize) msize.addEventListener('input', (e) => {
    state.mirrorSize = parseFloat(e.target.value);
    setLabels();
    refreshField();
  });
  $('btnSave').addEventListener('click', saveCurrentAsCandidate);
  $('btnPlay').addEventListener('click', togglePlay);

  // preset city quick-select buttons
  document.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.lat = parseFloat(btn.dataset.lat);
      state.lng = parseFloat(btn.dataset.lng);
      state.altKm = parseFloat(btn.dataset.alt);
      $('alt').value = state.altKm;
      mapApi.setCurrent(state.lat, state.lng);
      refresh('annual');
    });
  });

  // initial paint
  refresh('annual');
}

main();
