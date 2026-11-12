// Pusnik G 3D scenes: city flyover, hero car, countdown number. Each returns { camera, update(t), bloom }.
import * as THREE from "three";
import { TTFLoader } from "three/addons/loaders/TTFLoader.js";
import { Font } from "three/addons/loaders/FontLoader.js";
import { TextGeometry } from "three/addons/geometries/TextGeometry.js";
import { makeWorld, rng, clamp, easeOutExpo, easeOutBack, mod, PINK, TEAL, YELLOW } from "./common.js";

const cam = (fov, aspect) => new THREE.PerspectiveCamera(fov, aspect, 0.3, 2500);

/** city: flight down a neon avenue. p: palette, seed, mode street|aerial|rise, speed */
export function city(scene, renderer, aspect, p) {
  const world = makeWorld(scene, renderer, { palette: p.palette, seed: p.seed, city: p.coast ? false : true, sunY: p.mode === "aerial" ? 120 : 92 });
  const camera = cam(p.mode === "aerial" ? 62 : 70, aspect), v = p.speed || 26;
  return {
    camera, bloom: { strength: 0.38, radius: 0.5, threshold: 0.92 },
    update(t) {
      const z = -v * t;
      if (p.mode === "aerial") {
        camera.position.set(Math.sin(t * 0.35) * 5, 58 - t * 1.6, z); camera.lookAt(Math.sin(t * 0.35 + 0.6) * 3, 22, z - 150);
      } else if (p.mode === "rise") {  // starts on the tarmac, climbs above the roofs
        const k = clamp(t / 6); const y = 2.2 + 30 * k * k;
        camera.position.set(0, y, z); camera.lookAt(0, y * 0.75 + 5, z - 90);
      } else {
        camera.position.set(Math.sin(t * 0.5) * 1.6 - 2.2, 2.6 + Math.sin(t * 0.8) * 0.25, z); camera.lookAt(0, 9, z - 70);
        camera.rotation.z += Math.sin(t * 0.5) * 0.035;
      }
      world.update(z, t);
    },
  };
}

function makeCar(color, env) {
  const g = new THREE.Group(), W = 1.96;
  const s = new THREE.Shape();   // side profile, nose at +x
  s.moveTo(-2.15, 0.3); s.lineTo(-2.2, 0.78); s.quadraticCurveTo(-2.15, 0.98, -1.75, 1.0);
  s.quadraticCurveTo(-1.2, 1.02, -0.95, 1.06); s.lineTo(0.75, 0.9); s.quadraticCurveTo(1.7, 0.78, 2.18, 0.56);
  s.quadraticCurveTo(2.3, 0.42, 2.22, 0.3); s.lineTo(1.72, 0.3); s.absarc(1.34, 0.3, 0.4, 0, Math.PI, false);
  s.lineTo(-0.98, 0.3); s.absarc(-1.38, 0.3, 0.4, 0, Math.PI, false); s.lineTo(-2.15, 0.3);
  const paint = new THREE.MeshPhysicalMaterial({ color, metalness: 0.55, roughness: 0.22, clearcoat: 1, clearcoatRoughness: 0.08, envMap: env, envMapIntensity: 1.7 });
  const body = new THREE.Mesh(new THREE.ExtrudeGeometry(s, { depth: W - 0.24, bevelEnabled: true, bevelThickness: 0.12, bevelSize: 0.1, bevelSegments: 4, curveSegments: 16 }), paint);
  body.position.z = -(W - 0.24) / 2; g.add(body);
  const c = new THREE.Shape();   // glass canopy
  c.moveTo(-1.25, 1.0); c.quadraticCurveTo(-0.75, 1.36, -0.25, 1.37); c.quadraticCurveTo(0.2, 1.36, 0.95, 0.9); c.lineTo(-1.25, 1.0);
  const glass = new THREE.MeshPhysicalMaterial({ color: 0x05060c, metalness: 0.9, roughness: 0.06, envMap: env, envMapIntensity: 2.4 });
  const cab = new THREE.Mesh(new THREE.ExtrudeGeometry(c, { depth: W - 0.62, bevelEnabled: true, bevelThickness: 0.1, bevelSize: 0.08, bevelSegments: 3, curveSegments: 14 }), glass);
  cab.position.z = -(W - 0.62) / 2; g.add(cab);
  const dark = new THREE.MeshStandardMaterial({ color: 0x08080c, roughness: 0.6, metalness: 0.4 });
  const rimMat0 = new THREE.MeshStandardMaterial({ color: 0xd8dcf0, metalness: 1, roughness: 0.25, envMap: env });
  const wing = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.05, W - 0.1), dark); wing.position.set(-2.0, 1.24, 0); g.add(wing);
  for (const z of [-0.7, 0.7]) { const st = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.24, 0.06), dark); st.position.set(-1.98, 1.1, z); g.add(st); }
  const grille = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.16, W - 0.7), dark); grille.position.set(2.27, 0.42, 0); g.add(grille);
  const split = new THREE.Mesh(new THREE.BoxGeometry(4.3, 0.06, W + 0.06), dark); split.position.set(0, 0.26, 0); g.add(split);
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.26, W - 0.16), dark); panel.position.set(-2.29, 0.8, 0); g.add(panel);
  const diff = new THREE.Mesh(new THREE.BoxGeometry(0.3, 0.3, W - 0.3), dark); diff.position.set(-2.12, 0.44, 0); g.add(diff);
  for (const z of [-0.32, 0.32]) { const ex = new THREE.Mesh(new THREE.CylinderGeometry(0.075, 0.075, 0.12, 12), rimMat0); ex.rotation.z = Math.PI / 2; ex.position.set(-2.3, 0.46, z); g.add(ex); }
  const tail = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.08, W - 0.3), new THREE.MeshBasicMaterial({ color: new THREE.Color(2.2, 0.08, 0.2), toneMapped: false }));
  tail.position.set(-2.33, 0.8, 0); g.add(tail);
  const hmat = new THREE.MeshBasicMaterial({ color: new THREE.Color(1.9, 1.85, 1.6), toneMapped: false });
  for (const z of [-0.68, 0.68]) { const h = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.07, 0.42), hmat); h.position.set(2.24, 0.6, z); g.add(h); }
  const tyre = new THREE.CylinderGeometry(0.37, 0.37, 0.3, 24); tyre.rotateX(Math.PI / 2);
  const rim = new THREE.CylinderGeometry(0.24, 0.24, 0.31, 10); rim.rotateX(Math.PI / 2);
  const spoke = new THREE.BoxGeometry(0.46, 0.07, 0.32);
  const rimMat = new THREE.MeshStandardMaterial({ color: 0xd8dcf0, metalness: 1, roughness: 0.25, envMap: env });
  const wheels = [];
  for (const [x, z] of [[1.34, 0.97], [1.34, -0.97], [-1.38, 0.97], [-1.38, -0.97]]) {
    const w = new THREE.Group(); w.add(new THREE.Mesh(tyre, dark)); w.add(new THREE.Mesh(rim, rimMat));
    const sp = new THREE.Mesh(spoke, dark); w.add(sp); const sp2 = sp.clone(); sp2.rotation.z = Math.PI / 2; w.add(sp2);
    w.position.set(x, 0.37, z); g.add(w); wheels.push(w);
  }
  const cv = document.createElement("canvas"); cv.width = cv.height = 128; const cx = cv.getContext("2d");
  const rg = cx.createRadialGradient(64, 64, 4, 64, 64, 64); rg.addColorStop(0, "rgba(255,46,136,1)"); rg.addColorStop(1, "rgba(255,46,136,0)");
  cx.fillStyle = rg; cx.fillRect(0, 0, 128, 128);
  const glow = new THREE.Mesh(new THREE.PlaneGeometry(7.2, 4.2), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.45, toneMapped: false }));
  glow.rotation.x = -Math.PI / 2; glow.position.y = 0.03; g.add(glow);
  const pivot = new THREE.Group(); g.rotation.y = Math.PI / 2; pivot.add(g);   // nose towards -z
  pivot.userData.wheels = wheels; return pivot;
}

/** car: hero car on the avenue or coast road. p: palette, seed, color, view chase|rear34|front34|low, coast */
export function car(scene, renderer, aspect, p) {
  const world = makeWorld(scene, renderer, { palette: p.palette, seed: p.seed, city: !p.coast, clearLane: true, trafficN: 8, sunY: 96, sunSize: 150, behind: p.view === "front34" ? 300 : 20 });
  const camera = cam(p.view === "chase" ? 62 : 50, aspect), v = p.speed || 34;
  const c = makeCar(p.color ?? PINK, world.env); scene.add(c);
  const spot = new THREE.PointLight(PINK, 6, 14); scene.add(spot);
  return {
    camera, bloom: { strength: 0.36, radius: 0.5, threshold: 0.92 },
    update(t) {
      const z = -v * t, x = 2.2 + Math.sin(t * 0.6) * 0.5;
      c.position.set(x, Math.sin(t * 9) * 0.008, z); c.rotation.y = -Math.cos(t * 0.6) * 0.012; c.rotation.z = Math.sin(t * 0.6) * 0.012;
      for (const w of c.userData.wheels) w.rotation.z = -(v * t) / 0.37;
      spot.position.set(x, 0.5, z);
      const k = t * 0.22;
      if (p.view === "chase") { camera.position.set(x + Math.sin(k * 2) * 1.1, 2.3, z + 8.6); camera.lookAt(x, 3.4, z - 14); }
      else if (p.view === "front34") { camera.position.set(x - 3.6 + k * 1.4, 1.25, z - 9.2); camera.lookAt(x, 2.0, z + 1); }
      else if (p.view === "low") { camera.position.set(x + 3.0, 0.5, z + 8.4 - k * 1.2); camera.lookAt(x - 0.2, 2.1, z - 4); }
      else { camera.position.set(x + 4.4 - k * 1.5, 1.9, z + 9.2); camera.lookAt(x - 0.2, 2.5, z - 3); }
      world.update(z, t);
    },
  };
}

let FONT = null;
export async function loadFont(url) {
  if (!FONT) FONT = new Font(await new Promise((ok, bad) => new TTFLoader().load(url, ok, undefined, bad)));
  return FONT;
}

/** countdown: giant number flies down a neon tunnel into the camera. p: text, sub, seed, colour a|b */
export function countdown(scene, renderer, aspect, p) {
  const rand = rng(p.seed || 3), camera = cam(64, aspect), v = 46, L = 320;
  scene.background = new THREE.Color(0x070314); scene.fog = new THREE.FogExp2(0x0a0420, 0.0065);
  const cols = p.colors === "b" ? [TEAL, 0xb48cff] : [PINK, TEAL];
  const mats = cols.map((c) => new THREE.MeshBasicMaterial({ color: new THREE.Color(c).multiplyScalar(1.15), toneMapped: false }));
  const frames = [], RW = 13, RH = 23;
  const bar = new THREE.BoxGeometry(1, 1, 1);
  for (let i = 0; i < 40; i++) {
    const g = new THREE.Group(), m = mats[i % 2], th = 0.3;
    for (const [sx, sy, px, py] of [[RW + th, th, 0, RH / 2], [RW + th, th, 0, -RH / 2], [th, RH, RW / 2, 0], [th, RH, -RW / 2, 0]]) {
      const b = new THREE.Mesh(bar, m); b.scale.set(sx, sy, th); b.position.set(px, py, 0); g.add(b);
    }
    g.userData.z0 = -i * (L / 40); g.rotation.z = (i % 2 ? 1 : -1) * 0.0; scene.add(g); frames.push(g);
  }
  const n = 900, pos = new Float32Array(n * 3);   // streaking dust
  for (let i = 0; i < n; i++) pos.set([(rand() - 0.5) * 60, (rand() - 0.5) * 80, -rand() * L], i * 3);
  const pg = new THREE.BufferGeometry(); pg.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const dust = new THREE.Points(pg, new THREE.PointsMaterial({ color: 0xffffff, size: 0.13, transparent: true, opacity: 0.8, depthWrite: false }));
  const dust2 = dust.clone(); scene.add(dust, dust2);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x200a40, 0.5));
  const pl = new THREE.PointLight(PINK, 120, 80); scene.add(pl);
  const pl2 = new THREE.PointLight(TEAL, 90, 80); scene.add(pl2);
  // number
  const num = new THREE.Group(); scene.add(num);
  const tg = (txt, size, depth) => { const g = new TextGeometry(txt, { font: FONT, size, depth, curveSegments: 10, bevelEnabled: true, bevelThickness: 0.14, bevelSize: 0.09, bevelSegments: 3 }); g.center(); return g; };
  const face = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.42, roughness: 0.3, metalness: 0.1 });
  const side = new THREE.MeshStandardMaterial({ color: PINK, emissive: PINK, emissiveIntensity: 0.7, roughness: 0.4 });
  const hc = document.createElement("canvas"); hc.width = hc.height = 256; const hx = hc.getContext("2d");
  const hg = hx.createRadialGradient(128, 128, 0, 128, 128, 128); hg.addColorStop(0, "rgba(255,46,136,0.75)"); hg.addColorStop(0.45, "rgba(120,40,200,0.28)"); hg.addColorStop(1, "rgba(18,214,223,0)");
  hx.fillStyle = hg; hx.fillRect(0, 0, 256, 256);
  const halo = new THREE.Mesh(new THREE.PlaneGeometry(34, 34), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(hc), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
  scene.add(halo);
  const txt = String(p.text ?? ""); num.visible = txt.length > 0;
  const g1 = tg(txt || "0", 7, 1.8); g1.computeBoundingBox();
  const bb = g1.boundingBox, w = bb.max.x - bb.min.x, h = bb.max.y - bb.min.y, sc = Math.min(7.2 / w, 7.6 / h, 1.25);
  const big = new THREE.Mesh(g1, [face, side]); big.scale.setScalar(sc); num.add(big);
  if (p.sub) {
    const g2 = tg(String(p.sub), 1.5, 0.5); g2.computeBoundingBox(); const w2 = g2.boundingBox.max.x - g2.boundingBox.min.x;
    const sub = new THREE.Mesh(g2, [new THREE.MeshStandardMaterial({ color: YELLOW, emissive: YELLOW, emissiveIntensity: 0.45 }), new THREE.MeshStandardMaterial({ color: 0x8a6a00 })]);
    sub.scale.setScalar(Math.min(1, 7.2 / w2)); sub.position.y = -(h * sc) / 2 - 0.95; num.add(sub);
  }
  const ringMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(PINK).multiplyScalar(1.3), toneMapped: false, transparent: true });
  const shock = new THREE.Mesh(new THREE.TorusGeometry(1, 0.05, 8, 64), ringMat); scene.add(shock);
  const HIT = 0.5, NY = 3.4;
  return {
    camera, bloom: { strength: 0.62, radius: 0.55, threshold: 0.84 },
    update(t) {
      const z = -v * t, k = clamp(t / HIT), shake = t > HIT ? Math.exp(-(t - HIT) * 9) : 0;
      camera.position.set(Math.sin(t * 61) * 0.25 * shake, Math.cos(t * 53) * 0.25 * shake, z);
      camera.rotation.set(0, 0, Math.sin(t * 0.4) * 0.05);
      for (const f of frames) f.position.z = z + 14 - mod(z + 14 - f.userData.z0, L);
      dust.position.z = z + 10 - mod(z + 10, L) + L; dust2.position.z = dust.position.z - L;
      const d = 70 - 54 * easeOutExpo(k) - clamp(t - HIT, 0, 99) * 0.22;   // distance camera -> number
      const pop = t < HIT ? 1 : 1 + 0.16 * Math.exp(-(t - HIT) * 7) * Math.cos((t - HIT) * 16);
      num.position.set(0, NY, z - d); num.scale.setScalar(pop);
      num.rotation.set(Math.sin(t * 0.9) * 0.05, (1 - easeOutExpo(k)) * 1.2 + Math.sin(t * 0.7) * 0.16, 0);
      pl.position.set(-6, 5, z - d + 9); pl2.position.set(6, -3, z - d + 8);
      const s = t > HIT ? (t - HIT) : 0; shock.visible = s > 0 && s < 0.9;
      shock.position.set(0, NY, z - d + 1); halo.position.set(0, NY, z - d - 3); shock.scale.setScalar(4 + easeOutExpo(s / 0.9) * 26); ringMat.opacity = 1 - s / 0.9;
    },
  };
}

export const SCENES = { city, car, countdown };
