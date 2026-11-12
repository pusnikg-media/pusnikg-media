// Pusnik G 3D scenes - shared building blocks (original Vice-City-style look, no game assets).
import * as THREE from "three";
import { mergeGeometries } from "three/addons/utils/BufferGeometryUtils.js";

export const PINK = 0xff2e88, TEAL = 0x12d6df, YELLOW = 0xffe600;

export function rng(seed) {
  let a = (seed >>> 0) || 1;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const mod = (a, n) => ((a % n) + n) % n;
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const easeOutExpo = (x) => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
export const easeOutBack = (x) => 1 + 2.70158 * Math.pow(x - 1, 3) + 1.70158 * Math.pow(x - 1, 2);

export const PALETTES = {
  // sky stops from zenith to horizon, plus fog / light colours
  sunset: { sky: ["#140a3c", "#5b1a8a", "#ff3d8b", "#ffb347"], fog: 0x5a1c66, fogD: 0.0030, sun: true, amb: 0xff7ab8, ambI: 1.1, key: 0xffa060, keyI: 0.9, lit: 0.3, stars: 0.25 },
  night: { sky: ["#01010a", "#0a0630", "#2c0f66", "#c0267e"], fog: 0x14083a, fogD: 0.0034, sun: false, amb: 0x6a5cff, ambI: 0.9, key: 0xff2e88, keyI: 0.6, lit: 0.48, stars: 1 },
  dusk: { sky: ["#07062a", "#2a1a7a", "#b0308f", "#ff7a59"], fog: 0x351866, fogD: 0.0032, sun: true, amb: 0xb48cff, ambI: 1.0, key: 0xff6fa0, keyI: 0.75, lit: 0.4, stars: 0.6 },
};

function canvas(w, h) {
  const c = document.createElement("canvas"); c.width = w; c.height = h; return [c, c.getContext("2d")];
}
function tex(c, opts = {}) {
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; Object.assign(t, opts); return t;
}

/** Gradient sky dome (follows the camera) + stars. */
export function makeSky(pal, rand) {
  const g = new THREE.Group();
  const [c, x] = canvas(4, 512);
  const gr = x.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, pal.sky[0]); gr.addColorStop(0.28, pal.sky[1]); gr.addColorStop(0.43, pal.sky[2]); gr.addColorStop(0.5, pal.sky[3]);
  gr.addColorStop(0.51, pal.sky[2]); gr.addColorStop(1, pal.sky[0]);
  x.fillStyle = gr; x.fillRect(0, 0, 4, 512);
  const dome = new THREE.Mesh(new THREE.SphereGeometry(900, 32, 32),
    new THREE.MeshBasicMaterial({ map: tex(c), side: THREE.BackSide, fog: false, depthWrite: false, toneMapped: false }));
  dome.renderOrder = -10; g.add(dome);
  const n = 700, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const th = rand() * Math.PI * 2, ph = Math.acos(rand() * 0.95);  // upper hemisphere
    pos.set([850 * Math.sin(ph) * Math.cos(th), 850 * Math.cos(ph), 850 * Math.sin(ph) * Math.sin(th)], i * 3);
  }
  const sg = new THREE.BufferGeometry(); sg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const stars = new THREE.Points(sg, new THREE.PointsMaterial({ color: 0xffffff, size: 2.2, sizeAttenuation: false, fog: false, transparent: true, opacity: pal.stars, depthWrite: false }));
  stars.renderOrder = -9; g.add(stars);
  return g;
}

/** Striped synthwave sun on the horizon (add to the sky group; sits at -z). */
export function makeSun(radius = 150) {
  const [c, x] = canvas(512, 512);
  const gr = x.createLinearGradient(0, 0, 0, 512);
  gr.addColorStop(0, "#fff3a0"); gr.addColorStop(0.45, "#ffb040"); gr.addColorStop(1, "#ff2e88");
  x.fillStyle = gr; x.beginPath(); x.arc(256, 256, 250, 0, Math.PI * 2); x.fill();
  x.globalCompositeOperation = "destination-out";
  for (let i = 0; i < 7; i++) { const y = 290 + i * 34; x.fillRect(0, y, 512, 5 + i * 3.2); }
  const m = new THREE.Mesh(new THREE.PlaneGeometry(radius * 2, radius * 2),
    new THREE.MeshBasicMaterial({ map: tex(c), transparent: true, fog: false, depthWrite: false, toneMapped: false, color: new THREE.Color(1.0, 1.0, 1.0) }));
  m.renderOrder = -8;
  const [c2, x2] = canvas(256, 256);
  const rg = x2.createRadialGradient(128, 128, 20, 128, 128, 128);
  rg.addColorStop(0, "rgba(255,150,120,0.4)"); rg.addColorStop(0.5, "rgba(255,60,140,0.12)"); rg.addColorStop(1, "rgba(255,46,136,0)");
  x2.fillStyle = rg; x2.fillRect(0, 0, 256, 256);
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(radius * 5, radius * 5),
    new THREE.MeshBasicMaterial({ map: tex(c2), transparent: true, fog: false, depthWrite: false, toneMapped: false, blending: THREE.AdditiveBlending }));
  halo.position.z = -2; halo.renderOrder = -8.5; m.add(halo);
  return m;
}

/** Small studio-less environment map taken from the sky colours (for car paint / water reflections). */
export function makeEnv(renderer, pal) {
  const s = new THREE.Scene(); const r = rng(7);
  const sky = makeSky(pal, r); s.add(sky);
  if (pal.sun) { const sun = makeSun(170); sun.position.set(0, 60, -800); s.add(sun); }
  for (const [col, x, y, z] of [[PINK, -300, 120, 100], [TEAL, 300, 160, 200], [0xffffff, 0, 400, 0]]) {  // soft light cards
    const card = new THREE.Mesh(new THREE.PlaneGeometry(260, 120), new THREE.MeshBasicMaterial({ color: new THREE.Color(col).multiplyScalar(1.2), side: THREE.DoubleSide, fog: false }));
    card.position.set(x, y, z); card.lookAt(0, 0, 0); s.add(card);
  }
  const pm = new THREE.PMREMGenerator(renderer); const rt = pm.fromScene(s, 0.02, 1, 2000); pm.dispose();
  return rt.texture;
}

/** Facade texture with randomly lit windows; used as colour and emissive map. */
export function windowTexture(rand, lit) {
  const [c, x] = canvas(128, 256);
  x.fillStyle = "#07040f"; x.fillRect(0, 0, 128, 256);
  const cols = ["#ff2e88", "#12d6df", "#ffe600", "#ffd9a0", "#ffd9a0", "#b48cff"];
  const main = cols[Math.floor(rand() * cols.length)];
  for (let r = 0; r < 16; r++) for (let q = 0; q < 8; q++) {
    if (rand() > lit) continue;
    x.fillStyle = rand() < 0.7 ? main : cols[Math.floor(rand() * cols.length)];
    x.globalAlpha = 0.55 + rand() * 0.45; x.fillRect(q * 16 + 3, r * 16 + 4, 10, 8);
  }
  x.globalAlpha = 1;
  return tex(c, { wrapS: THREE.RepeatWrapping, wrapT: THREE.RepeatWrapping, magFilter: THREE.NearestFilter });
}

/** One palm (trunk + fronds) merged into a single geometry, height ~h. */
export function palmGeometry(rand, h = 9) {
  const lean = (rand() - 0.5) * 2.2, parts = [];
  const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 0), new THREE.Vector3(lean * 0.35, h * 0.5, 0), new THREE.Vector3(lean, h, 0)]);
  parts.push(new THREE.TubeGeometry(curve, 10, 0.2, 6, false));
  const nf = 11;
  for (let i = 0; i < nf; i++) {
    const len = 3.4 + rand() * 1.4, g = new THREE.PlaneGeometry(len, 1.0, 8, 2);
    const p = g.attributes.position;
    for (let k = 0; k < p.count; k++) {
      const u = p.getX(k) / len + 0.5, v = p.getY(k);
      p.setXYZ(k, u * len, 0.5 * u - 1.9 * u * u * (0.7 + 0.5 * (i % 2)) - Math.abs(v) * 0.5, v * (1 - u * 0.92) * (0.5 + 2 * u * (1 - u) + 0.3));
    }
    g.rotateY((i / nf) * Math.PI * 2 + rand() * 0.3); g.translate(lean, h - 0.1, 0); parts.push(g);
  }
  const nonIdx = parts.map((g) => { const n = g.index ? g.toNonIndexed() : g; n.deleteAttribute("uv"); n.computeVertexNormals(); return n; });
  return mergeGeometries(nonIdx);
}

function roadTexture() {
  const [c, x] = canvas(256, 512);
  x.fillStyle = "#0b0714"; x.fillRect(0, 0, 256, 512);
  x.fillStyle = "#12d6df"; x.fillRect(6, 0, 5, 512); x.fillRect(245, 0, 5, 512);       // glowing kerb lines
  x.fillStyle = "#ffe600"; x.fillRect(125, 0, 6, 250);                                     // centre dashes
  x.fillStyle = "rgba(255,255,255,0.55)"; x.fillRect(66, 40, 3, 170); x.fillRect(187, 296, 3, 170);
  return tex(c, { wrapS: THREE.ClampToEdgeWrapping, wrapT: THREE.RepeatWrapping });
}

/**
 * Endless avenue that recycles itself around the camera (drive direction: -z).
 * opts: behind (metres of world kept behind the camera, default 20; raise it for backward-looking shots), palette name, seed, city (true: towers both sides, false: coast - water left, palms + low houses right)
 * returns { group, pal, update(camZ, t) }
 */
export function makeWorld(scene, renderer, opts) {
  const pal = PALETTES[opts.palette] || PALETTES.sunset, rand = rng(opts.seed || 1), city = opts.city !== false;
  const L = 420, AHEAD = L - (opts.behind ?? 20), items = [];
  scene.fog = new THREE.FogExp2(pal.fog, pal.fogD * (city ? 1 : 0.8));
  const env = makeEnv(renderer, pal); scene.environment = env; scene.environmentIntensity = 0.55;
  const sky = makeSky(pal, rand); scene.add(sky);
  if (pal.sun) { const sun = makeSun(opts.sunSize || 150); sun.position.set(opts.sunX || 0, opts.sunY ?? 92, -860); sky.add(sun); }
  scene.add(new THREE.HemisphereLight(pal.amb, 0x120824, pal.ambI));
  const key = new THREE.DirectionalLight(pal.key, pal.keyI); key.position.set(-0.3, 0.5, -1); scene.add(key); scene.add(key.target);
  const rim = new THREE.DirectionalLight(TEAL, 0.5); rim.position.set(1, 0.6, 0.6); scene.add(rim); scene.add(rim.target);

  const follow = new THREE.Group(); scene.add(follow);   // things glued to the camera's z
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2400, 2400), new THREE.MeshStandardMaterial({ color: 0x06030c, roughness: 0.95, metalness: 0 }));
  ground.rotation.x = -Math.PI / 2; ground.position.y = -0.06; follow.add(ground);
  const rt = roadTexture(); rt.repeat.set(1, 1400 / 24);
  const road = new THREE.Mesh(new THREE.PlaneGeometry(17, 1400), new THREE.MeshStandardMaterial({ map: rt, emissiveMap: rt, emissive: 0xffffff, emissiveIntensity: 0.9, roughness: 0.38, metalness: 0.55, envMapIntensity: 1.3 }));
  road.rotation.x = -Math.PI / 2; road.position.set(0, 0, -400); follow.add(road);
  if (!city) {  // ocean on the left, catching the sky
    const water = new THREE.Mesh(new THREE.PlaneGeometry(1400, 2400), new THREE.MeshStandardMaterial({ color: 0x0a1030, roughness: 0.16, metalness: 0.95, envMapIntensity: 2.2 }));
    water.rotation.x = -Math.PI / 2; water.position.set(-712, -0.03, 0); follow.add(water);
    const [gc, gx] = canvas(64, 256); const gg = gx.createLinearGradient(0, 0, 64, 0);
    gg.addColorStop(0, "rgba(255,120,120,0)"); gg.addColorStop(0.5, "rgba(255,200,130,0.9)"); gg.addColorStop(1, "rgba(255,120,120,0)");
    gx.fillStyle = gg; gx.fillRect(0, 0, 64, 256);
    const glit = new THREE.Mesh(new THREE.PlaneGeometry(60, 900), new THREE.MeshBasicMaterial({ map: tex(gc), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.55 }));
    glit.rotation.x = -Math.PI / 2; glit.position.set(-70, 0.02, -480); follow.add(glit);
  }

  const add = (obj, z0) => { obj.userData.z0 = z0; scene.add(obj); items.push(obj); return obj; };
  // --- buildings
  const texs = Array.from({ length: 7 }, () => windowTexture(rand, pal.lit));
  const box = new THREE.BoxGeometry(1, 1, 1); box.translate(0, 0.5, 0);
  const neon = [PINK, TEAL, YELLOW, 0xb48cff].map((c) => new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(1.25), toneMapped: false }));
  const roofMat = new THREE.MeshStandardMaterial({ color: 0x0a0614, roughness: 0.9 });
  const building = (x, z, w, d, h) => {
    const t = texs[Math.floor(rand() * texs.length)].clone(); t.repeat.set(Math.max(1, Math.round(w / 9)), Math.max(1, Math.round(h / 16))); t.needsUpdate = true;
    const g = new THREE.Group();
    const m = new THREE.Mesh(box, new THREE.MeshStandardMaterial({ map: t, emissiveMap: t, emissive: 0xffffff, emissiveIntensity: 1.0, roughness: 0.7, metalness: 0.1 }));
    m.scale.set(w, h, d); g.add(m);
    if (rand() < 0.7) { const s = new THREE.Mesh(box, neon[Math.floor(rand() * neon.length)]); s.scale.set(w + 0.3, 0.35, d + 0.3); s.position.y = h; g.add(s);
      const cap = new THREE.Mesh(box, roofMat); cap.scale.set(w - 0.5, 0.42, d - 0.5); cap.position.y = h; g.add(cap); }
    if (rand() < 0.35 && h > 18) {  // vertical neon sign on the street side
      const s = new THREE.Mesh(box, neon[Math.floor(rand() * neon.length)]); s.scale.set(0.35, h * 0.45, 1.6);
      s.position.set(-Math.sign(x) * (w / 2 + 0.25), h * 0.3, (rand() - 0.5) * d * 0.6); g.add(s);
    }
    g.position.set(x, 0, 0); return add(g, z);
  };
  const sides = city ? [-1, 1] : [1];
  for (const side of sides) {
    for (let row = 0; row < 3; row++) {
      let z = 0;
      while (z < L) {
        const w = 10 + rand() * 12, d = 12 + rand() * 14, h = city ? [10 + rand() * 22, 26 + rand() * 40, 50 + rand() * 70][row] : [5 + rand() * 6, 10 + rand() * 14, 22 + rand() * 30][row];
        const x = side * ((city ? 19 : 26) + row * 27 + rand() * 6 + w / 2);
        if (rand() < 0.88) building(x, -z - d / 2, w, d, h);
        z += d + 2 + rand() * (city ? 6 : 16);
      }
    }
  }
  // --- palms + street lamps along the kerb
  const palmMat = new THREE.MeshStandardMaterial({ color: 0x1a1030, roughness: 0.75, metalness: 0.1, side: THREE.DoubleSide, flatShading: true });
  const palms = Array.from({ length: 5 }, () => palmGeometry(rand, 8 + rand() * 4));
  const lampMat = new THREE.MeshStandardMaterial({ color: 0x1c1430, roughness: 0.5, metalness: 0.6 });
  const pole = new THREE.CylinderGeometry(0.09, 0.12, 6.2, 6); pole.translate(0, 3.1, 0);
  for (let z = 0; z < L; z += 14) {
    for (const side of [-1, 1]) {
      if ((z / 14) % 3 === 2) {
        const g = new THREE.Group(); g.add(new THREE.Mesh(pole, lampMat));
        const head = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.12, 0.3), neon[side < 0 ? 0 : 1]); head.position.set(-side * 0.7, 6.2, 0); g.add(head);
        g.position.x = side * 10.2; add(g, -z);
      } else {
        const m = new THREE.Mesh(palms[Math.floor(rand() * palms.length)], palmMat);
        m.position.x = side * (11.5 + rand() * 2.5); m.rotation.y = rand() * 6.28; add(m, -z - rand() * 4);
        if (!city && side < 0 && rand() < 0.5) m.position.x = side * (11.5 + rand() * 5);
      }
    }
  }
  // --- traffic: light streaks (moved in update with their own speed)
  const cars = [];
  if (opts.traffic !== false) {
    const bodyMat = new THREE.MeshStandardMaterial({ color: 0x0c0a14, roughness: 0.3, metalness: 0.8 });
    const red = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.8, 0.1, 0.15), toneMapped: false }), white = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.7, 1.6, 1.3), toneMapped: false });
    for (let i = 0; i < (opts.trafficN || 12); i++) {
      const g = new THREE.Group(), onc = i % 2 === 0;
      const b = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.75, 4.2), bodyMat); b.position.y = 0.6; g.add(b);
      const cab = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.5, 2), bodyMat); cab.position.set(0, 1.15, 0.2); g.add(cab);
      for (const sx of [-0.62, 0.62]) {
        const tl = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.14, 0.08), red); tl.position.set(sx, 0.72, 2.12); g.add(tl);
        const hl = new THREE.Mesh(new THREE.BoxGeometry(0.36, 0.14, 0.08), white); hl.position.set(sx, 0.66, -2.12); g.add(hl);
      }
      if (onc) g.rotation.y = Math.PI;
      g.position.x = onc ? -(2.2 + (i % 4 === 0 ? 3.6 : 0)) : (i % 4 === 1 ? 5.8 : 2.2);
      if (opts.clearLane && !onc && g.position.x < 4) g.position.x = 5.8;
      g.userData = { z0: -rand() * L, v: onc ? -(14 + rand() * 8) : 15 + rand() * 9 }; scene.add(g); cars.push(g);
    }
  }
  return {
    pal, env, sky,
    update(camZ, t) {
      sky.position.set(0, 0, camZ); follow.position.z = camZ; rt.offset.y = -camZ / 24;
      key.target.position.set(0, 0, camZ); key.position.set(-40, 60, camZ - 120); rim.position.set(60, 40, camZ + 40); rim.target.position.set(0, 0, camZ);
      for (const o of items) o.position.z = camZ + (L - AHEAD) - mod(camZ + (L - AHEAD) - o.userData.z0, L);
      for (const c of cars) c.position.z = camZ + (L - AHEAD) - mod(camZ + (L - AHEAD) - (c.userData.z0 - c.userData.v * t), L);
    },
  };
}
