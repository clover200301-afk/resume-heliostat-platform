// Pure-JS solar geometry, ported from engine_web.py so that the 3D scene
// can animate the sun without round-trips to the server.  Kept identical
// formulas to the Python backend, so the visualised sun direction matches
// the backend's metrics 1:1.
const DEG = Math.PI / 180;

export function dayNumberFromDate (dateStr) {
  const parts = dateStr.split('-').map(Number);
  let y, m, d;
  if (parts.length === 3) { [y, m, d] = parts; } else { [m, d] = parts; y = 2023; }
  const target = Date.UTC(y, m - 1, d);
  const ref = Date.UTC(y, 2, 21);   // March 21
  return Math.round((target - ref) / 86400000);
}

export function sunVector (latDeg, dateStr, timeHours) {
  const D = dayNumberFromDate(dateStr);
  const phi = latDeg * DEG;
  const declSin = Math.sin(2 * Math.PI * D / 365) * Math.sin(23.45 * DEG);
  const delta = Math.asin(Math.max(-1, Math.min(1, declSin)));
  const omega = (Math.PI / 12) * (timeHours - 12);
  const sinAlt = Math.sin(phi) * Math.sin(delta)
               + Math.cos(phi) * Math.cos(delta) * Math.cos(omega);
  const alt = Math.asin(Math.max(-1, Math.min(1, sinAlt)));
  const sE = -Math.cos(delta) * Math.sin(omega);
  const sN = Math.cos(phi) * Math.sin(delta) - Math.sin(phi) * Math.cos(delta) * Math.cos(omega);
  const sU = sinAlt;
  const l = Math.hypot(sE, sN, sU) || 1;
  const az = (Math.atan2(sE, sN) / DEG + 360) % 360;
  return {
    vec: [sE / l, sN / l, sU / l],
    altDeg: alt / DEG,
    azDeg: az,
  };
}

export function dni (altRad, hKm, clearness = 1.0) {
  const sa = Math.sin(altRad);
  if (sa <= 0) return 0.0;
  const G0 = 1.366;
  const a = 0.4237 - 0.00821 * Math.pow(6 - hKm, 2);
  const b = 0.5055 + 0.00595 * Math.pow(6.5 - hKm, 2);
  const c = 0.2711 + 0.01858 * Math.pow(2.5 - hKm, 2);
  return clearness * G0 * (a + b * Math.exp(-c / sa));
}
