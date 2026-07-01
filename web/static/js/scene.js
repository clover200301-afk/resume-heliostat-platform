// 3D heliostat-field scene built with Three.js.
//
// Coordinate convention used throughout the engine: ENU (x = East, y = North,
// z = Up).  Three.js by default uses y-up so we set scene.up = (0, 0, 1) and
// keep our positions in ENU directly.
//
// Exports a singleton `Scene` object with these methods:
//   await Scene.init(container, fieldData)
//   Scene.updateSun(sunVecEnu, dni)
//   Scene.updateMirrors(perMirrorEta)    // colour each mirror by efficiency
//   Scene.setHelpers({trajectory: bool})
//
// All numeric inputs use the same units as the backend (metres).

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const TOWER_HEIGHT = 80;
const RECEIVER_HEIGHT = 8;
const RECEIVER_RADIUS = 3.5;
const FIELD_RADIUS = 350;
const EXCL_RADIUS = 100;

class HeliostatScene {
  constructor () {
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.mirrorMesh = null;
    this.mirrorCount = 0;
    this.mirrorBase = [];   // {x, y, z, W, H}
    this.tower = [0, 0];
    this.sunMesh = null;
    this.sunLight = null;
    this.beamGroup = null;   // optional rays from mirror -> receiver
    this.trajLine = null;
    this.cachedSunVec = new THREE.Vector3(0, 0, 1);
  }

  async init (container, fieldData) {
    const w = container.clientWidth || 600;
    const h = container.clientHeight || 400;

    this.scene = new THREE.Scene();
    this.scene.up.set(0, 0, 1);   // we use Z-up everywhere
    this.scene.background = new THREE.Color(0x0c1424);
    this.scene.fog = new THREE.Fog(0x0c1424, 600, 1400);

    this.camera = new THREE.PerspectiveCamera(45, w / h, 1, 4000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(560, -720, 300);

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(window.devicePixelRatio);
    this.renderer.setSize(w, h);
    this.renderer.shadowMap.enabled = false;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(this.tower[0], this.tower[1], 40);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.maxDistance = 2200;
    this.controls.minDistance = 60;
    this.controls.maxPolarAngle = Math.PI * 0.495;
    this.controls.update();

    this._addLights();
    this._addGround();
    this._addTower(fieldData.tower);
    this._addMirrors(fieldData);
    this._addSun();
    this._addCompass();

    this.resize = this.resize.bind(this);
    window.addEventListener('resize', () => this.resize(container));
    // sometimes container hasn't laid out fully at first tick
    requestAnimationFrame(() => this.resize(container));
    setTimeout(() => this.resize(container), 200);
    this._animate();
  }

  resize (container) {
    if (!this.renderer) return;
    const w = container.clientWidth, h = container.clientHeight;
    this.renderer.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  _addLights () {
    const amb = new THREE.AmbientLight(0x445577, 0.35);
    this.scene.add(amb);
    this.ambientLight = amb;
    this.sunLight = new THREE.DirectionalLight(0xfff4d6, 1.0);
    this.sunLight.position.set(0, 0, 1000);
    this.scene.add(this.sunLight);
  }

  _addGround () {
    // golden-yellow desert sand
    const groundGeo = new THREE.CircleGeometry(1500, 96);
    const groundMat = new THREE.MeshStandardMaterial({
      color: 0xd4a94a,               // warm sandy yellow
      roughness: 0.95, metalness: 0.0
    });
    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.position.set(0, 0, -0.1);
    this.scene.add(ground);
    this.groundMat = groundMat;

    // field-circle marker (darker for contrast against yellow)
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(FIELD_RADIUS - 0.4, FIELD_RADIUS + 0.4, 128),
      new THREE.MeshBasicMaterial({ color: 0x4a2f0a, side: THREE.DoubleSide })
    );
    ring.position.z = 0.05;
    this.scene.add(ring);

    // grid helper underneath for depth perception
    const grid = new THREE.GridHelper(1000, 40, 0x8a6d3a, 0x6e5628);
    grid.rotation.x = Math.PI / 2;  // Z-up
    grid.position.z = -0.05;
    grid.material.opacity = 0.28;
    grid.material.transparent = true;
    this.scene.add(grid);
  }

  _addTower (tower) {
    this.tower = tower;
    const [tx, ty] = tower;

    // exclusion zone ring around tower
    const excl = new THREE.Mesh(
      new THREE.RingGeometry(EXCL_RADIUS - 0.4, EXCL_RADIUS + 0.4, 96),
      new THREE.MeshBasicMaterial({ color: 0x8b3820, side: THREE.DoubleSide,
                                    transparent: true, opacity: 0.7 })
    );
    excl.position.set(tx, ty, 0.06);
    this.scene.add(excl);

    // -------- Tower assembly (grouped for easy positioning) --------
    const towerGroup = new THREE.Group();
    towerGroup.position.set(tx, ty, 0);

    // 1. Concrete base pedestal (bottom 8 m)
    const baseGeo = new THREE.CylinderGeometry(6, 8, 8, 24);
    const baseMat = new THREE.MeshStandardMaterial({
      color: 0x9a9a9a, roughness: 0.85, metalness: 0.15
    });
    const base = new THREE.Mesh(baseGeo, baseMat);
    base.rotation.x = Math.PI / 2;
    base.position.z = 4;
    towerGroup.add(base);

    // 2. Main shaft (8 m -> 68 m): tapered white metallic cylinder
    const shaftGeo = new THREE.CylinderGeometry(2.2, 3.6, 60, 32, 4);
    const shaftMat = new THREE.MeshStandardMaterial({
      color: 0xeef2f7, roughness: 0.35, metalness: 0.75,
      emissive: 0x0d1830, emissiveIntensity: 0.05
    });
    const shaft = new THREE.Mesh(shaftGeo, shaftMat);
    shaft.rotation.x = Math.PI / 2;
    shaft.position.z = 8 + 30;
    towerGroup.add(shaft);

    // 2b. Three horizontal accent rings on the shaft for visual detail
    for (const [zLevel, r] of [[18, 3.0], [38, 2.8], [58, 2.5]]) {
      const bandGeo = new THREE.TorusGeometry(r + 0.05, 0.15, 12, 48);
      const bandMat = new THREE.MeshStandardMaterial({
        color: 0xffb84d, roughness: 0.4, metalness: 0.9,
        emissive: 0x422200, emissiveIntensity: 0.4
      });
      const band = new THREE.Mesh(bandGeo, bandMat);
      band.position.z = zLevel;
      towerGroup.add(band);
    }

    // 3. Cap / catwalk platform (68 -> 72 m): wider disc, "service floor"
    const capGeo = new THREE.CylinderGeometry(5.5, 4.5, 4, 24);
    const capMat = new THREE.MeshStandardMaterial({
      color: 0xbfc4cc, roughness: 0.5, metalness: 0.6
    });
    const cap = new THREE.Mesh(capGeo, capMat);
    cap.rotation.x = Math.PI / 2;
    cap.position.z = 70;
    towerGroup.add(cap);

    // catwalk railing (thin torus around the cap)
    const railGeo = new THREE.TorusGeometry(5.5, 0.12, 8, 48);
    const railMat = new THREE.MeshStandardMaterial({
      color: 0x555f70, roughness: 0.7, metalness: 0.6
    });
    const rail = new THREE.Mesh(railGeo, railMat);
    rail.position.z = 72;
    towerGroup.add(rail);

    // 4. Receiver (72 -> 80 m): glowing golden crystal
    const recGeo = new THREE.CylinderGeometry(RECEIVER_RADIUS, RECEIVER_RADIUS,
                                              RECEIVER_HEIGHT, 32, 4);
    const recMat = new THREE.MeshStandardMaterial({
      color: 0xffd280,
      emissive: 0xff9622, emissiveIntensity: 0.9,
      roughness: 0.25, metalness: 0.85
    });
    const rec = new THREE.Mesh(recGeo, recMat);
    rec.rotation.x = Math.PI / 2;
    rec.position.z = 76;
    towerGroup.add(rec);
    this.receiverPos = new THREE.Vector3(tx, ty, 76);

    // 5. Antenna spire on top
    const spireGeo = new THREE.CylinderGeometry(0.15, 0.6, 6, 8);
    const spireMat = new THREE.MeshStandardMaterial({
      color: 0xd4d8e0, roughness: 0.4, metalness: 0.85
    });
    const spire = new THREE.Mesh(spireGeo, spireMat);
    spire.rotation.x = Math.PI / 2;
    spire.position.z = 83;
    towerGroup.add(spire);

    // Aviation warning light: small red glowing sphere at spire tip
    const beaconGeo = new THREE.SphereGeometry(0.5, 12, 8);
    const beaconMat = new THREE.MeshBasicMaterial({ color: 0xff3030 });
    const beacon = new THREE.Mesh(beaconGeo, beaconMat);
    beacon.position.z = 86.5;
    towerGroup.add(beacon);
    this.beaconMesh = beacon;

    this.scene.add(towerGroup);

    // 6. Halo (visualises power level) — two concentric glow spheres
    const halo = new THREE.Mesh(
      new THREE.SphereGeometry(RECEIVER_RADIUS + 1.2, 32, 20),
      new THREE.MeshBasicMaterial({ color: 0xffd06a, transparent: true,
                                    opacity: 0.18 })
    );
    halo.position.set(tx, ty, 76);
    this.haloMesh = halo;
    this.scene.add(halo);

    // outer soft glow
    const halo2 = new THREE.Mesh(
      new THREE.SphereGeometry(RECEIVER_RADIUS + 3.5, 32, 20),
      new THREE.MeshBasicMaterial({ color: 0xffb84d, transparent: true,
                                    opacity: 0.06 })
    );
    halo2.position.set(tx, ty, 76);
    this.haloMesh2 = halo2;
    this.scene.add(halo2);
  }

  _addMirrors (fieldData) {
    const N = fieldData.positions.length;
    this.mirrorCount = N;
    const W = fieldData.width, H = fieldData.height, z = fieldData.install_height;

    const geo = new THREE.PlaneGeometry(W, H);
    const mat = new THREE.MeshStandardMaterial({
      color: 0xbfd8ff,
      roughness: 0.18, metalness: 0.85,
      side: THREE.DoubleSide
    });
    const mesh = new THREE.InstancedMesh(geo, mat, N);
    mesh.frustumCulled = false;
    this.mirrorMesh = mesh;
    this.mirrorGeom = geo;
    this.mirrorMat = mat;
    this.scene.add(mesh);

    // small mount stems for visual grounding (one for each mirror).
    // Stem thickness shrinks with mirror size to avoid a "forest of poles"
    // look at high mirror-count settings.
    const stemRadius = Math.max(0.08, Math.min(0.22, W * 0.04));
    const stemGeo = new THREE.CylinderGeometry(stemRadius, stemRadius, z, 6);
    const stemMat = new THREE.MeshStandardMaterial({
      color: 0x5d6c84, roughness: 0.9
    });
    const stems = new THREE.InstancedMesh(stemGeo, stemMat, N);
    stems.frustumCulled = false;
    this.stemMesh = stems;
    this.stemGeom = stemGeo;
    this.stemMat = stemMat;
    this.scene.add(stems);

    const _m = new THREE.Matrix4();
    const _q = new THREE.Quaternion();
    const _p = new THREE.Vector3();
    const _s = new THREE.Vector3(1, 1, 1);
    const _z = new THREE.Vector3(0, 0, 1);

    this.mirrorBase = [];
    for (let i = 0; i < N; i++) {
      const [x, y] = fieldData.positions[i];
      this.mirrorBase.push({ x, y, z });
      // initial: face up
      _p.set(x, y, z);
      _q.identity();
      _m.compose(_p, _q, _s);
      mesh.setMatrixAt(i, _m);
      // stem
      _p.set(x, y, z / 2);
      const stemQ = new THREE.Quaternion().setFromUnitVectors(
        new THREE.Vector3(0, 1, 0), _z);
      _m.compose(_p, stemQ, new THREE.Vector3(1, 1, 1));
      stems.setMatrixAt(i, _m);
    }
    mesh.instanceMatrix.needsUpdate = true;
    stems.instanceMatrix.needsUpdate = true;

    // per-instance color (used after we know efficiencies)
    mesh.instanceColor = new THREE.InstancedBufferAttribute(
      new Float32Array(N * 3), 3);
    for (let i = 0; i < N; i++) {
      mesh.instanceColor.setXYZ(i, 0.75, 0.85, 1.0);
    }
    mesh.instanceColor.needsUpdate = true;
  }

  /**
   * Swap the mirror + stem InstancedMeshes for a new field definition.
   * Called when the user changes the "mirror count" slider — we dispose
   * the previous instanced meshes to avoid a GPU-memory leak.
   */
  rebuildMirrors (fieldData) {
    if (this.mirrorMesh) {
      this.scene.remove(this.mirrorMesh);
      this.mirrorMesh.dispose();
      this.mirrorGeom.dispose();
      this.mirrorMat.dispose();
    }
    if (this.stemMesh) {
      this.scene.remove(this.stemMesh);
      this.stemMesh.dispose();
      this.stemGeom.dispose();
      this.stemMat.dispose();
    }
    this._addMirrors(fieldData);
    // reapply the current sun so the new mirrors immediately face the sun
    this._reorientMirrors(
      this.cachedSunVec.x, this.cachedSunVec.y, this.cachedSunVec.z,
      Math.max(0, this.cachedSunVec.z),
    );
  }

  _addSun () {
    const sun = new THREE.Mesh(
      new THREE.SphereGeometry(18, 24, 18),
      new THREE.MeshBasicMaterial({ color: 0xffd560 })
    );
    sun.position.set(0, -800, 600);
    this.sunMesh = sun;
    this.scene.add(sun);

    // optional trajectory polyline (filled later on each day update)
    const trajGeo = new THREE.BufferGeometry();
    const trajMat = new THREE.LineBasicMaterial({
      color: 0x8da9ff, transparent: true, opacity: 0.45
    });
    this.trajLine = new THREE.Line(trajGeo, trajMat);
    this.scene.add(this.trajLine);
  }

  _addCompass () {
    // N/E/S/W labels via tiny coloured spheres + lines
    const r = FIELD_RADIUS + 30;
    const colours = { N: 0x99c2ff, E: 0xffc299, S: 0xffd0d0, W: 0xc6e6ff };
    const offsets = { N: [0, r], E: [r, 0], S: [0, -r], W: [-r, 0] };
    Object.entries(offsets).forEach(([k, [x, y]]) => {
      const m = new THREE.Mesh(
        new THREE.SphereGeometry(4, 12, 8),
        new THREE.MeshBasicMaterial({ color: colours[k] })
      );
      m.position.set(x, y, 4);
      this.scene.add(m);
    });
  }

  /**
   * Update sun position and re-orient every mirror to keep its reflected
   * ray pointing at the receiver centre.
   * @param sunVec  [sE, sN, sU] unit vector (ENU)
   * @param dni     kW/m^2 (drives light intensity & receiver glow)
   */
  updateSun (sunVec, dni) {
    if (!this.sunMesh) return;
    const [sE, sN, sU] = sunVec;
    this.cachedSunVec.set(sE, sN, sU);
    const length = Math.hypot(sE, sN, sU) || 1;
    const ux = sE / length, uy = sN / length, uz = sU / length;

    // -------- Time-of-day *only affects the SKY* --------
    // Update the background gradient / sky dome based on sun altitude uz.
    // Ground, lights and mirrors stay bright so the field is always readable.
    this._updateSky(uz, ux, uy);

    // Sun disc position: always visible above horizon so users still see
    // where the sun is even when it's "set".
    const D = 750;
    const dispZ = Math.max(uz * D, 60);       // never let it dip below ~60m
    this.sunMesh.position.set(ux * D, uy * D, dispZ);

    // Sun disc colour: warm-red near horizon (visual only)
    const intensity = Math.max(0, uz);
    const warm = Math.pow(1 - intensity, 2);
    if (this.sunMesh.material) {
      const sr = 1.0;
      const sg = 0.55 + 0.42 * intensity;
      const sb = 0.20 + 0.55 * intensity;
      this.sunMesh.material.color.setRGB(sr, sg, sb);
      this.sunMesh.scale.setScalar(1.0 + 1.2 * warm);
    }

    // -------- CONSTANT lighting: keep the field crisp at any hour --------
    // The directional light still tracks the sun (so mirror highlights point
    // the right way), but intensity stays high and colour stays warm-white.
    this.sunLight.position.set(ux * D, uy * D, Math.abs(uz) * D + 200);
    this.sunLight.intensity = 1.15;
    this.sunLight.color.setRGB(1.0, 0.95, 0.85);
    if (this.ambientLight) {
      this.ambientLight.intensity = 0.55;
      this.ambientLight.color.setRGB(0.85, 0.87, 0.95);
    }

    // Halo (receiver glow) still reacts to DNI to give a "generating"
    // indicator — but never fully vanishes.
    if (this.haloMesh) {
      const haloOpacity = 0.15 + 0.5 * Math.min(1, dni || 0);
      this.haloMesh.material.opacity = haloOpacity;
      this.haloMesh.scale.setScalar(1 + 0.6 * (dni || 0));
    }
    if (this.haloMesh2) {
      this.haloMesh2.material.opacity = 0.04 + 0.20 * Math.min(1, dni || 0);
      this.haloMesh2.scale.setScalar(1 + 0.35 * (dni || 0));
    }

    // Mirror orientation: physics — normal = norm(sun + aim).
    this._reorientMirrors(ux, uy, uz, intensity);
  }

  /**
   * Update sky background as a function of sun altitude.
   * There is no gradient sky dome — just a single flat colour for the sky
   * plus a matching fog colour, so the ground and sky meet cleanly at the
   * horizon without any bright band in between.
   */
  _updateSky (uz, ux, uy) {
    if (!this.scene) return;
    let sky;
    if (uz > 0.20) {
      // clear daytime sky (deeper blue as sun climbs)
      const t = Math.min(1, (uz - 0.20) / 0.80);
      sky = _lerpRGB([0x6f, 0xa4, 0xd8], [0x24, 0x54, 0x94], t);
    } else if (uz > 0) {
      // dawn / dusk — warm orange near horizon
      const t = uz / 0.20;
      sky = _lerpRGB([0xff, 0x8a, 0x3d], [0x6f, 0xa4, 0xd8], t);
    } else {
      // night — deep blue-purple
      const t = Math.min(1, -uz / 0.30);
      sky = _lerpRGB([0x22, 0x1c, 0x38], [0x05, 0x07, 0x12], t);
    }
    const skyHex = _rgbToHex(sky);
    this.scene.background = new THREE.Color(skyHex);
    // fog matches the sky exactly so distant ground fades into it
    this.scene.fog.color = new THREE.Color(skyHex);

    // If a legacy sky dome was created earlier, remove it so the flat
    // background is what the camera actually sees.
    if (this._skyDome) {
      this.scene.remove(this._skyDome);
      this._skyDome.geometry.dispose();
      this._skyDome.material.dispose();
      this._skyDome = null;
    }
    // Note: ground colour is deliberately NOT tinted — only the SKY reflects
    // the time of day, so the field stays crisply readable at any hour.
  }

  _reorientMirrors (sx, sy, sz, sunHeight) {
    if (!this.mirrorMesh) return;
    const recPos = this.receiverPos;
    const _m = new THREE.Matrix4();
    const _q = new THREE.Quaternion();
    const _p = new THREE.Vector3();
    const _s = new THREE.Vector3(1, 1, 1);
    const N = this.mirrorCount;
    const planeNormal = new THREE.Vector3(0, 0, 1);   // plane geometry faces +z

    for (let i = 0; i < N; i++) {
      const b = this.mirrorBase[i];
      // aim vector (mirror -> receiver)
      let ax = recPos.x - b.x;
      let ay = recPos.y - b.y;
      let az = recPos.z - b.z;
      const al = Math.hypot(ax, ay, az) || 1;
      ax /= al; ay /= al; az /= al;
      // mirror normal
      let nx = sx + ax, ny = sy + ay, nz = sz + az;
      const nl = Math.hypot(nx, ny, nz) || 1;
      nx /= nl; ny /= nl; nz /= nl;
      // if sun below horizon, lay mirror flat (z up)
      if (sunHeight <= 0) { nx = 0; ny = 0; nz = 1; }

      _q.setFromUnitVectors(planeNormal, new THREE.Vector3(nx, ny, nz));
      _p.set(b.x, b.y, b.z);
      _m.compose(_p, _q, _s);
      this.mirrorMesh.setMatrixAt(i, _m);
    }
    this.mirrorMesh.instanceMatrix.needsUpdate = true;
  }

  /**
   * Update per-mirror colour by efficiency (gradient blue -> orange -> red).
   * @param eta array (N,) of values in [0,1]
   */
  updateMirrors (eta) {
    if (!eta || !this.mirrorMesh || !this.mirrorMesh.instanceColor) return;
    const ic = this.mirrorMesh.instanceColor;
    const N = Math.min(eta.length, this.mirrorCount);
    for (let i = 0; i < N; i++) {
      const e = Math.max(0, Math.min(1, eta[i]));
      // viridis-ish: low = dark purple/blue, high = warm yellow
      const r = 0.30 + 0.70 * Math.pow(e, 1.3);
      const g = 0.20 + 0.80 * Math.pow(e, 0.6);
      const b = 0.95 - 0.85 * e;
      ic.setXYZ(i, r, g, b);
    }
    ic.needsUpdate = true;
  }

  /**
   * Update the full-day sun trajectory (an arc of points), given a function
   * that returns a sun vector for each ST in [5, 20].
   */
  updateTrajectory (sunVecFn) {
    if (!this.trajLine) return;
    const pts = [];
    const D = 750;
    for (let t = 4.5; t <= 19.5; t += 0.25) {
      const v = sunVecFn(t);
      if (!v) continue;
      const [sx, sy, sz] = v;
      if (sz <= 0) continue;
      pts.push(new THREE.Vector3(sx * D, sy * D, sz * D));
    }
    this.trajLine.geometry.dispose();
    this.trajLine.geometry = new THREE.BufferGeometry().setFromPoints(pts);
  }

  _animate () {
    requestAnimationFrame(() => this._animate());
    this.controls.update();
    // aviation beacon blink (~1 Hz)
    if (this.beaconMesh) {
      const t = performance.now() * 0.001;
      const on = (Math.sin(t * 2 * Math.PI) + 1) * 0.5;
      const brightness = 0.4 + 0.6 * on;
      this.beaconMesh.material.color.setRGB(brightness, 0.08 * on, 0.08 * on);
      this.beaconMesh.scale.setScalar(0.9 + 0.25 * on);
    }
    this.renderer.render(this.scene, this.camera);
  }
}

export const Scene = new HeliostatScene();

// --- helpers ---
function _lerpRGB (a, b, t) {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
  ];
}
function _rgbToHex (rgb) {
  return (rgb[0] << 16) | (rgb[1] << 8) | rgb[2];
}
