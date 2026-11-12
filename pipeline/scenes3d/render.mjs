// Pusnik G 3D clip renderer: Three.js scenes -> headless Chrome (software WebGL) -> ffmpeg -> 1080x1920 mp4.
// Usage: node render.mjs clips.json outdir [--only id1,id2] [--skip id1,id2] [--frames 0,45,90] [--scale 0.5]
//   clips.json: {"clips":[{"id","scene","params","duration","tags"}]}   (see clips.json)
//   --frames writes single JPEGs (outdir/<id>_f<frame>.jpg) instead of videos - for quick visual checks.
// Deterministic: every frame is computed from its index, so a slow machine only renders slower, never differently.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { spawn, execSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2), opt = (k) => { const i = args.indexOf(k); return i < 0 ? null : args[i + 1]; };
const [listFile, outDir] = args;
if (!listFile || !outDir) { console.error("usage: node render.mjs clips.json outdir [--only a,b] [--skip a,b] [--frames 0,45] [--scale 0.5]"); process.exit(2); }
const only = opt("--only")?.split(","), skip = opt("--skip")?.split(",") || [], stills = opt("--frames")?.split(",").map(Number), scale = Number(opt("--scale") || 1);
const FPS = 30, W = Math.round((1080 * scale) / 2) * 2, H = Math.round((1920 * scale) / 2) * 2;
const clips = JSON.parse(fs.readFileSync(listFile, "utf8")).clips.filter((c) => (!only || only.includes(c.id)) && !skip.includes(c.id));
fs.mkdirSync(outDir, { recursive: true });

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json", ".ttf": "font/ttf" };
const FONT = path.join(HERE, "..", "fonts", "Anton-Regular.ttf");
const server = http.createServer((req, res) => {
  const u = decodeURIComponent(req.url.split("?")[0]);
  const f = u === "/font.ttf" ? (fs.existsSync(FONT) ? FONT : path.join(HERE, "Anton-Regular.ttf")) : path.join(HERE, path.normalize(u));
  if (!f.startsWith(HERE) && u !== "/font.ttf") { res.writeHead(403).end(); return; }
  fs.readFile(f, (e, b) => { if (e) { res.writeHead(404).end(); return; } res.writeHead(200, { "content-type": MIME[path.extname(f)] || "application/octet-stream" }).end(b); });
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const port = server.address().port;

const chrome = process.env.CHROME_PATH || ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"].map((c) => { try { return execSync(`command -v ${c}`).toString().trim(); } catch { return ""; } }).find(Boolean);
if (!chrome) { console.error("S3D FAIL: no Chrome found (set CHROME_PATH)"); process.exit(1); }
const browser = await puppeteer.launch({
  executablePath: chrome, headless: true, protocolTimeout: 600000,
  args: ["--no-sandbox", "--use-angle=swiftshader", "--use-gl=angle", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--disable-gpu-vsync", "--hide-scrollbars", `--window-size=${W},${H}`],
});
let failed = 0;
for (const c of clips) {
  const t0 = Date.now(), page = await browser.newPage();
  try {
    page.on("pageerror", (e) => console.error("  page error:", String(e).slice(0, 400)));
    page.on("console", (m) => { if (m.type() === "error") console.error("  console:", m.text().slice(0, 300)); });
    await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}/scene.html`, { waitUntil: "load" });
    await page.waitForFunction("window.s3dReady === true", { timeout: 60000 });
    await page.evaluate((spec) => window.s3dSetup(spec), { scene: c.scene, params: c.params || {}, width: W, height: H, fps: FPS });
    const grab = async (i) => Buffer.from((await page.evaluate((i) => window.s3dFrame(i), i)).split(",")[1], "base64");
    if (stills) {
      for (const i of stills) fs.writeFileSync(path.join(outDir, `${c.id}_f${String(i).padStart(3, "0")}.jpg`), await grab(i));
      console.log(`STILLS ${c.id} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    } else {
      const n = Math.round((c.duration || 6) * FPS), out = path.join(outDir, `${c.id}.mp4`);
      const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-", "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-g", "15", "-movflags", "+faststart", "-r", String(FPS), out], { stdio: ["pipe", "inherit", "inherit"] });
      const done = new Promise((ok, bad) => ff.on("close", (code) => (code ? bad(new Error("ffmpeg exit " + code)) : ok())));
      for (let i = 0; i < n; i++) { if (!ff.stdin.write(await grab(i))) await new Promise((r) => ff.stdin.once("drain", r)); }
      ff.stdin.end(); await done;
      console.log(`CLIP_OK ${c.id} ${n} frames ${((Date.now() - t0) / 1000).toFixed(0)}s ${(fs.statSync(out).size / 1e6).toFixed(1)} MB`);
    }
  } catch (e) { failed++; console.error(`CLIP_FAIL ${c.id}: ${String(e).slice(0, 500)}`); }
  await page.close();
}
await browser.close(); server.close();
console.log(failed ? `S3D DONE with ${failed} failed` : "S3D_OK " + clips.length);
process.exit(failed && failed === clips.length ? 1 : 0);
