// Leaflet world map for site selection.  Click anywhere on land to set
// the latitude/longitude.  Calls back with {lat, lng}.
/* global L */

export function createMap (containerId, initLat, initLng, onPick) {
  const map = L.map(containerId, {
    center: [initLat, initLng],
    zoom: 2,
    minZoom: 1,
    maxZoom: 8,
    worldCopyJump: true,
    attributionControl: true,
  });

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap & CARTO',
    subdomains: 'abcd',
  }).addTo(map);

  // marker for current site
  const marker = L.circleMarker([initLat, initLng], {
    radius: 8, color: '#ffb84d', weight: 2,
    fillColor: '#ffb84d', fillOpacity: 0.45,
  }).addTo(map);
  marker.bindTooltip('当前选址', { permanent: false, direction: 'top' });

  // candidate-site markers (saved)
  const candidates = L.layerGroup().addTo(map);

  map.on('click', (e) => {
    const { lat, lng } = e.latlng;
    const wrapped = ((lng + 540) % 360) - 180;
    marker.setLatLng([lat, wrapped]);
    onPick(lat, wrapped);
  });

  // Leaflet needs its container to have a non-zero size when initialised;
  // if the sidebar was still laying out we invalidate on the next frame.
  requestAnimationFrame(() => map.invalidateSize());
  setTimeout(() => map.invalidateSize(), 200);
  window.addEventListener('resize', () => map.invalidateSize());

  return {
    setCurrent (lat, lng) { marker.setLatLng([lat, lng]); map.panTo([lat, lng]); },
    addCandidate (lat, lng, label) {
      const m = L.circleMarker([lat, lng], {
        radius: 5, color: '#4dd6a8', weight: 1,
        fillColor: '#4dd6a8', fillOpacity: 0.7,
      }).addTo(candidates);
      m.bindTooltip(label, { permanent: false, direction: 'top' });
      return m;
    },
    clearCandidates () { candidates.clearLayers(); },
  };
}
