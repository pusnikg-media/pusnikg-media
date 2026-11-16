"""Frame checks for IRL campaign clips (free, local, OpenCV + numpy only; no network, no credits).

Added 16.11.2026 for the JasonTheWeen campaign ("Jason is the main focus", "no logos / overlays of any kind"):

  crop       cut a strip off the source before anything else (burned-in Twitch chat + counters sit in the top ~15 %).
             Option "crop": 0.15 (top share) or {"top": .15, "bottom": 0, "left": 0, "right": 0}.
  face       "Jason in the picture": a face of at least `min_w` (share of the picture WIDTH) must be there in at least
             `min_share` of the sampled frames and there must be no gap without a face longer than `max_gap` s -> else the clip is rejected.
             Haar cascades (frontal + both profiles) - weak on caps / turned heads, so the limits are generous and measured on real Jason
             material (see claude/livewatch-stand.md). It cannot tell WHO the face is: a clip of somebody else passes.
  tiles      multi-window layouts (chat window + browser + webcam tiles, "stream starting" screens, black bars around small windows):
             rejected. Measured as lasting straight edges that cut the picture into parts + black borders.
  logo       WARNING only (never rejects): static overlays that stay put while the scene moves (counters, chat, watermarks, alert boxes)
             and big text blobs. Logos printed on clothing / signs / lanyards CANNOT be found cheaply - every clip still needs a look by hand.

Everything here is pure functions over numpy frames (gray, uint8) except `sample_frames` / `check_clip`, so the tests run on synthetic pictures."""
import subprocess

DEFAULTS = {
    "face": {"min_w": 0.07, "min_share": 0.45, "max_gap": 6.0, "fps": 1.5},   # share of sampled frames with a big enough face / longest gap in s
    "tiles": {"line_cov": 0.62, "min_lines": 2, "black": 0.30},
    "logo": {"static_cov": 0.9, "min_area": 0.004, "max_area": 0.25},
}


def norm_crop(v):
    """Crop option -> (top, bottom, left, right) as shares 0-0.5, or None. Number = top share."""
    if v in (None, False, 0): return None
    if isinstance(v, (int, float)): t = (float(v), 0.0, 0.0, 0.0)
    elif isinstance(v, dict): t = tuple(float(v.get(k, 0) or 0) for k in ("top", "bottom", "left", "right"))
    elif isinstance(v, (list, tuple)) and len(v) == 4: t = tuple(float(x) for x in v)
    else: raise ValueError(f"crop must be a number or {{top,bottom,left,right}}, got {v!r}")
    if any(x < 0 or x > 0.5 for x in t): raise ValueError(f"crop shares must be 0-0.5, got {t}")
    return t if any(t) else None


def crop_rect(crop, w, h):
    """(x, y, cw, ch) in px, even numbers (yuv420), for a source of w x h."""
    t, b, l, r = crop
    x, y = int(l * w) // 2 * 2, int(t * h) // 2 * 2
    cw, ch = int(w - x - int(r * w)) // 2 * 2, int(h - y - int(b * h)) // 2 * 2
    return x, y, max(cw, 16), max(ch, 16)


def sample_frames(src, a, b, fps=1.5, width=480, max_n=70):
    """Gray frames of [a, b] at `fps` -> uint8 array (n, h, w); empty array when unreadable."""
    import numpy as np
    dur = max(b - a, 0.1); fps = min(fps, max_n / dur)
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True)
    try: sw_, sh_ = (int(x) for x in p.stdout.strip().split(",")[:2])
    except Exception: return np.zeros((0, 2, 2), np.uint8)
    h = max(2, int(round(sh_ * width / sw_ / 2)) * 2)
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", src, "-an", "-vf", f"fps={fps:.4f},scale={width}:{h},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True, timeout=600)
    n = len(r.stdout) // (width * h)
    return np.frombuffer(r.stdout[:n * width * h], np.uint8).reshape(n, h, width) if n else np.zeros((0, h, width), np.uint8)


# ---------------------------------------------------------------- face ("Jason in the picture")
def face_widths(F):
    """Per frame: width of the biggest face as a share of the picture width (0 = none). Needs OpenCV; returns None without it."""
    try: import cv2
    except ImportError: return None
    cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    pc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    if cc.empty(): return None
    out = []
    for g in F:
        sh, sw = g.shape; m = max(sh // 14, 12); best = 0.0
        # the Haar cascade is a hit-and-miss detector on a down-scaled frame: equalise, then ask frontal, then profiles (both sides)
        e = cv2.equalizeHist(g)
        for det, img, flip in ((cc, e, False), (pc, e, False), (pc, cv2.flip(e, 1), True)):
            if det.empty(): continue
            for (x, y, w, h) in det.detectMultiScale(img, 1.1, 5, minSize=(m, m)): best = max(best, w / sw)
        out.append(best)
    return out


def face_verdict(widths, dt, cfg=None):
    """widths = face width share per sampled frame, dt = seconds between frames -> {"ok", "share", "max_gap", "reason"}. Pure."""
    c = {**DEFAULTS["face"], **(cfg if isinstance(cfg, dict) else {})}
    if not widths: return {"ok": False, "share": 0.0, "max_gap": 0.0, "reason": "no frames to look at"}
    hit = [w >= c["min_w"] for w in widths]; share = sum(hit) / len(hit)
    gap = best = 0
    for h in hit:
        gap = 0 if h else gap + 1; best = max(best, gap)
    gap_s = best * dt; v = {"ok": True, "share": round(share, 2), "max_gap": round(gap_s, 1), "reason": ""}
    if share < c["min_share"]: v.update(ok=False, reason=f"face big enough in only {share:.0%} of the picture time (need {c['min_share']:.0%})")
    elif gap_s > c["max_gap"]: v.update(ok=False, reason=f"no face for {gap_s:.0f} s in a row (limit {c['max_gap']:g} s)")
    return v


# ---------------------------------------------------------------- multi-window layouts
def tile_metrics(F):
    """Lasting straight edges + black borders. Median over time of the edge maps, so only what stays in EVERY frame counts
    (a room's furniture lines move with the camera, a window frame / webcam tile border does not).
    -> {"vlines": [x shares], "hlines": [y shares], "black": share of the picture that is pure black in the median frame}"""
    import numpy as np
    if len(F) < 3: return {"vlines": [], "hlines": [], "black": 0.0}
    G = F.astype(np.int16)
    ex = np.abs(np.diff(G, axis=2)); ey = np.abs(np.diff(G, axis=1))
    mx = np.median(ex, axis=0); my = np.median(ey, axis=0)          # (h, w-1), (h-1, w): the edge must be there in most frames
    h, w = F.shape[1:]
    # a line = a column (row) where a strong edge runs along >= 62 % of the height (width) - inner part only (the outer 6 % are the picture's border)
    colcov = (mx >= 18).mean(axis=0); rowcov = (my >= 18).mean(axis=1)
    def peaks(cov, n, lo=0.06, hi=0.94):
        idx = [i for i in range(int(n * lo), int(n * hi)) if cov[i] >= DEFAULTS["tiles"]["line_cov"]]
        out, run = [], []
        for i in idx:
            if run and i - run[-1] > 3: out.append(run); run = []
            run.append(i)
        if run: out.append(run)
        return [round((r[0] + r[-1]) / 2 / n, 3) for r in out]
    med = np.median(F, axis=0)
    return {"vlines": peaks(colcov, w - 1), "hlines": peaks(rowcov, h - 1), "black": round(float((med <= 12).mean()), 3)}


def tile_verdict(m, cfg=None):
    """Pure decision on tile_metrics. Multi-window = >= 2 lasting straight lines (any direction) or a mostly black picture
    (small windows on a black desktop / "stream starting" screens)."""
    c = {**DEFAULTS["tiles"], **(cfg if isinstance(cfg, dict) else {})}
    n = len(m["vlines"]) + len(m["hlines"])
    if m["black"] >= c["black"]: return {"ok": False, "reason": f"{m['black']:.0%} of the picture is black: windows on a desktop / waiting screen", **m}
    if n >= c["min_lines"]: return {"ok": False, "reason": f"multi-window layout ({n} lasting straight edges cut the picture)", **m}
    return {"ok": True, "reason": "", **m}


# ---------------------------------------------------------------- logo / overlay warning (never rejects)
def static_overlays(F):
    """Regions that keep their content while the rest of the picture moves = burned-in overlays, counters, watermarks.
    -> list of {"box": [x, y, w, h] shares, "area": share}. A static scene (tripod, desk) shows nothing here: the rest of the picture must move."""
    import numpy as np
    if len(F) < 4: return []
    G = F.astype(np.int16); n, h, w = G.shape
    d = np.abs(np.diff(G, axis=0)).mean(axis=0)                     # mean frame-to-frame change per pixel
    # structure that is there in every frame: edges that survive in the 25th percentile over time
    ed = np.abs(np.diff(G, axis=2))[:, :-1, :]; ed2 = np.abs(np.diff(G, axis=1))[:, :, :-1]
    edge = ed + ed2
    keep = np.percentile(edge, 25, axis=0) >= 14
    still = d[:-1, :-1] <= 1.2
    mov = float(np.median(d))
    if mov < 4.0: return []                                          # the scene itself hardly moves: cannot separate overlay from scene
    m = (keep & still).astype(np.uint8)
    try:
        import cv2
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)); m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        k, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    except ImportError: return []
    out = []
    for i in range(1, k):
        x, y, bw, bh, ar = st[i]; area = bw * bh / (w * h)
        if DEFAULTS["logo"]["min_area"] <= area <= DEFAULTS["logo"]["max_area"] and ar / max(bw * bh, 1) >= 0.12:
            out.append({"box": [round(x / w, 3), round(y / h, 3), round(bw / w, 3), round(bh / h, 3)], "area": round(area, 3)})
    return sorted(out, key=lambda o: -o["area"])[:4]


def text_blobs(F):
    """Big text-like blobs (lettering) that stay in the picture over time: dense small high-contrast strokes in a compact box.
    -> list of {"box", "area"} (warning for 'big lettering in the foreground'; shop signs, shirts, banners). Needs OpenCV."""
    try: import cv2, numpy as np
    except ImportError: return []
    if len(F) < 3: return []
    sel = F[:: max(len(F) // 6, 1)][:6]; h, w = sel.shape[1:]; hits = np.zeros((h, w), np.float32)
    for g in sel:
        grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        _, bw = cv2.threshold(grad, 40, 255, cv2.THRESH_BINARY)
        con = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3)))
        k, lab, st, _ = cv2.connectedComponentsWithStats(con, connectivity=8)
        for i in range(1, k):
            x, y, bw_, bh_, ar = st[i]
            if 0.018 * w <= bw_ <= 0.5 * w and 0.02 * h <= bh_ <= 0.12 * h and bw_ >= 2.2 * bh_ and ar / (bw_ * bh_) >= 0.45 and bw_ * bh_ >= 0.004 * w * h:
                hits[y:y + bh_, x:x + bw_] += 1
    m = (hits >= max(3, len(sel) - 1)).astype(np.uint8)
    k, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((7, 7), np.uint8)), connectivity=8)
    out = []
    for i in range(1, k):
        x, y, bw_, bh_, ar = st[i]; area = bw_ * bh_ / (w * h)
        if area >= 0.006: out.append({"box": [round(x / w, 3), round(y / h, 3), round(bw_ / w, 3), round(bh_ / h, 3)], "area": round(area, 3)})
    return sorted(out, key=lambda o: -o["area"])[:4]


# ---------------------------------------------------------------- one call for the Clipfabrik
def check_clip(src, a, b, spec=True):
    """spec = True or {"face": bool|dict, "tiles": bool|dict, "logo": bool}. Returns
    {"ok": bool, "reasons": [...], "warnings": [...], "metrics": {...}}. Frames are taken from `src` as it is (crop first, then check)."""
    spec = {} if spec is True else dict(spec)
    r = {"ok": True, "reasons": [], "warnings": [], "metrics": {}}
    fc = spec.get("face", True); fps = (fc if isinstance(fc, dict) else {}).get("fps", DEFAULTS["face"]["fps"])
    F = sample_frames(src, a, b, fps=fps)
    if not len(F): r["warnings"].append("frame check skipped: no frames readable"); return r
    dt = (b - a) / len(F)
    if spec.get("tiles", True):
        v = tile_verdict(tile_metrics(F), spec.get("tiles")); r["metrics"]["tiles"] = {k: v[k] for k in ("vlines", "hlines", "black")}
        if not v["ok"]: r["ok"] = False; r["reasons"].append(v["reason"])
    if fc:
        wd = face_widths(F)
        if wd is None: r["warnings"].append("face check skipped: OpenCV missing")
        else:
            v = face_verdict(wd, dt, fc); r["metrics"]["face"] = {"share": v["share"], "max_gap": v["max_gap"], "best_w": round(max(wd), 3)}
            if not v["ok"]: r["ok"] = False; r["reasons"].append(v["reason"])
    if spec.get("logo", True):
        so = static_overlays(F); tb = text_blobs(F)
        if so: r["warnings"].append(f"static overlay/logo candidate(s) at {[o['box'] for o in so]} - check by hand"); r["metrics"]["static"] = so
        if tb: r["warnings"].append(f"big lettering in the picture at {[o['box'] for o in tb]} - check by hand"); r["metrics"]["text"] = tb
    return r
