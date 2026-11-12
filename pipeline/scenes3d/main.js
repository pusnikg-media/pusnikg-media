// Browser side of the 3D renderer: window.s3dSetup(spec) builds one scene, window.s3dFrame(i) draws frame i and returns a JPEG data URL.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { SCENES, loadFont } from "./scenes.js";

let renderer, composer, cur, fps = 30;

window.s3dSetup = async (spec) => {
  const W = spec.width || 1080, H = spec.height || 1920; fps = spec.fps || 30;
  if (renderer) { renderer.dispose(); renderer.domElement.remove(); }
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, powerPreference: "high-performance" });
  renderer.setPixelRatio(1); renderer.setSize(W, H); document.body.appendChild(renderer.domElement);
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  if (spec.scene === "countdown") await loadFont("/font.ttf");
  const scene = new THREE.Scene();
  cur = SCENES[spec.scene](scene, renderer, W / H, spec.params || {});
  composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, samples: 4 })); composer.setSize(W, H);
  composer.addPass(new RenderPass(scene, cur.camera));
  const b = cur.bloom; composer.addPass(new UnrealBloomPass(new THREE.Vector2(W / 2, H / 2), b.strength, b.radius, b.threshold));
  composer.addPass(new OutputPass());
  return true;
};

window.s3dFrame = (i, q = 0.93) => {
  cur.update(i / fps); composer.render();
  return renderer.domElement.toDataURL("image/jpeg", q);
};
window.s3dReady = true;
