"""Build a HyperFrames countdown short (index.html) from tts timing + exact word times.
Usage: python3 build_cd.py job.json project_dir   (called by render_hf.py; clips already in project_dir/assets/v/)"""
import json, os, re, sys, html as _h
job = json.load(open(sys.argv[1])); proj = sys.argv[2]
vo, day = job["vo_dir"], job["day"]
esc = lambda x: _h.escape(str(x))
timing = json.load(open(os.path.join(vo, "timing.json"))); words = json.load(open(os.path.join(vo, "words.json")))
GAP, TAIL = 0.22, 0.6
wins, t = [], 0.0
for i, ln in enumerate(timing):
    wins.append((t, t + ln["dur"])); t += ln["dur"] + (GAP if i < len(timing) - 1 else 0)
TOTAL = round(t + TAIL, 3)
SHOTS = [[(os.path.splitext(os.path.basename(c["file"]))[0], c.get("start", 0)) for c in line] for line in job["shots"]]
H = []; JS = []; z = 1
# --- footage: one timed <video> per shot inside an untimed Ken-Burns wrapper
cuts = []
for i, shots in enumerate(SHOTS):
    a = wins[i][0]; b = wins[i + 1][0] if i + 1 < len(wins) else TOTAL; d = (b - a) / len(shots)
    for k, (src, ms) in enumerate(shots):
        n = len(cuts); s = a + k * d; cuts.append(s)
        H.append(f'<div id="kb{n}" class="kb"><div id="pk{n}" class="pk"><video id="v{n}" class="clip" src="assets/v/{src}.mp4" muted playsinline '
                 f'data-start="{s:.3f}" data-duration="{d:.3f}" data-media-start="{ms}" data-track-index="0"></video></div></div>')
        z0, z1 = (1.0, 1.12) if n % 2 == 0 else (1.12, 1.0); x1 = 30 if n % 3 == 0 else (-30 if n % 3 == 1 else 0)
        JS.append(f'tl.fromTo("#kb{n}",{{scale:{z0},x:0}},{{scale:{z1},x:{x1},duration:{d:.3f},ease:"none"}},{s:.3f});')
# --- zoom-punch on keywords (job["punch"] = list of word stems): footage kicks to 1.14x and settles in 0.3 s
for li, ws in enumerate(words):
    for w in ws:
        if any(re.sub(r"[^a-z0-9]", "", w["w"].lower()).startswith(p.lower()) for p in job.get("punch", [])):
            t0 = wins[li][0] + w["s"]; n = max(i for i, c in enumerate(cuts) if c <= t0 + 1e-3)
            JS.append(f'tl.fromTo("#pk{n}",{{scale:1.14}},{{scale:1,duration:0.3,ease:"power3.out"}},{t0:.3f});')
            JS.append(f'tl.fromTo("#flash",{{opacity:0.25}},{{opacity:0,duration:0.1}},{t0:.3f});')
# --- white flash on every cut (not the first frame)
JS.append('tl.set("#flash",{opacity:0},0);')
for c in cuts[1:]:
    JS.append(f'tl.fromTo("#flash",{{opacity:0.55}},{{opacity:0,duration:0.14,ease:"power2.out"}},{c:.3f});')
JS.append(f'tl.fromTo("#bar",{{scaleX:0}},{{scaleX:1,duration:{TOTAL},ease:"none"}},0);')
# --- hook (frame 0 already readable): giant number + subline synced to "That's"
he = wins[0][1] + GAP; w0 = words[0]
H.append(f'<div id="hook" class="clip" data-start="0" data-duration="{he:.3f}" data-track-index="2"><div id="hook-in">'
         f'<div id="hook-num">{esc(job.get("hook_big", day))}</div><div id="hook-days">{esc(job.get("hook_mid", "DAYS LEFT"))}</div>'
         f'<div id="hook-sub">{esc(job.get("hook_sub", ""))}</div></div></div>')
JS += ['tl.fromTo("#hook-num",{scale:1.25},{scale:1,duration:0.35,ease:"back.out(2)"},0);',
       'tl.fromTo("#hook-days",{y:0},{y:0,duration:0.01},0);',
       f'tl.fromTo("#hook-sub",{{opacity:0,y:30}},{{opacity:1,y:0,duration:0.18,ease:"power3.out"}},{w0[min(2, len(w0) - 1)]["s"]:.3f});',
       f'tl.fromTo("#hook-in",{{scale:1}},{{scale:0.9,opacity:0,duration:0.16,ease:"power2.in"}},{he-0.17:.3f});']
# --- optional big card (e.g. a date) slammed in on a keyword: job["card"] = {"line","word","top","big","bottom"}
card = job.get("card")
if card:
    li = card["line"]; ws = words[li]
    ts = wins[li][0] + next((w["s"] for w in ws if w["w"].lower().strip(".,!?").startswith(card["word"].lower())), ws[0]["s"])
    de = wins[li + 1][0] if li + 1 < len(wins) else TOTAL
    H.append(f'<div id="date" class="clip" data-start="{ts:.3f}" data-duration="{de-ts:.3f}" data-track-index="3"><div id="date-in">'
             f'<div id="date-m">{esc(card.get("top", ""))}</div><div id="date-d">{esc(card["big"])}</div><div id="date-y">{esc(card.get("bottom", ""))}</div></div></div>')
    JS += [f'tl.fromTo("#date-in",{{scale:1.6,opacity:0,rotation:-6}},{{scale:1,opacity:1,rotation:0,duration:0.28,ease:"back.out(1.8)"}},{ts:.3f});']
# --- follow pill on the CTA line
li = len(timing) - 1; ts = wins[li][0] + words[li][0]["s"]
H.append(f'<div id="cta" class="clip" data-start="{ts:.3f}" data-duration="{TOTAL-ts:.3f}" data-track-index="3"><div id="cta-in">FOLLOW</div></div>')
JS += [f'tl.fromTo("#cta-in",{{scale:0.4,opacity:0}},{{scale:1,opacity:1,duration:0.3,ease:"back.out(2.2)"}},{ts:.3f});',
       f'tl.fromTo("#cta-in",{{y:0}},{{y:-18,duration:0.25,ease:"sine.inOut",yoyo:true,repeat:3}},{ts+0.5:.3f});']
# --- karaoke captions: exact word times, 2-3 word groups, active word yellow + pop
weak = {"a", "an", "the", "and", "or", "to", "of", "for", "in", "your", "so", "you"}
gid = 0
for li in range(1, len(timing)):
    a, _ = wins[li]; ws = words[li]; groups, cur = [], []
    for j, w in enumerate(ws):
        cur.append(j)
        if len(cur) >= 3 or re.search(r"[,.?!]$", w["w"]) or j == len(ws) - 1:
            carry = []
            while len(cur) > 1 and ws[cur[-1]]["w"].lower() in weak and j < len(ws) - 1:
                carry.insert(0, cur.pop())  # never end a group on a weak word
            groups.append(cur); cur = carry
    if cur: groups.append(cur)
    m = []  # merge flash-groups (<0.45 s) into the next one, max 4 words
    for g in groups:
        if m and ws[g[0]]["s"] - ws[m[-1][0]]["s"] < 0.45 and len(m[-1]) + len(g) <= 4: m[-1] = m[-1] + g
        else: m.append(g)
    groups = m
    line_end = wins[li + 1][0] if li + 1 < len(wins) else TOTAL
    for gi, g in enumerate(groups):
        gs = a + ws[g[0]]["s"] - 0.06
        ge = (a + ws[groups[gi + 1][0]]["s"] - 0.06) if gi + 1 < len(groups) else min(line_end, a + ws[g[-1]]["e"] + 0.45)
        spans = "".join(f'<span id="w{gid}_{k}" class="w">{re.sub(r"[.,!?]", "", ws[j]["w"]).upper()}</span>' for k, j in enumerate(g))
        chars = sum(len(re.sub(r"[.,!?]", "", ws[j]["w"])) for j in g) + 1.2 * (len(g) - 1)
        fs = int(min(112, 930 / (chars * 0.47 * 1.12)))  # Anton ~0.47 em per caps char, room for the 1.12 pop
        spans = spans.replace('class="w"', f'class="w" style="font-size:{fs}px"')
        H.append(f'<div id="cap{gid}" class="clip cap" data-start="{gs:.3f}" data-duration="{ge-gs:.3f}" data-track-index="4">'
                 f'<div id="capin{gid}" class="capin">{spans}</div></div>')
        JS.append(f'tl.fromTo("#capin{gid}",{{y:24,scale:0.92}},{{y:0,scale:1,duration:0.12,ease:"power3.out"}},{gs:.3f});')
        for k, j in enumerate(g):
            s = a + ws[j]["s"]; e = (a + ws[g[k + 1]]["s"]) if k + 1 < len(g) else ge
            JS.append(f'tl.fromTo("#w{gid}_{k}",{{color:"#ffffff",scale:1}},{{color:"#ffe600",scale:1.12,duration:0.08,ease:"power2.out"}},{s:.3f});')
            JS.append(f'tl.to("#w{gid}_{k}",{{color:"#ffffff",scale:1,duration:0.08}},{max(e-0.08, s+0.09):.3f});')
        gid += 1
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cd_template.html")).read()
html = tpl.replace("%TOTAL%", str(TOTAL)).replace("%BADGE%", esc(job.get("badge", f"GTA 6 \u2022 DAY {day}"))).replace("%BODY%", "\n      ".join(H)).replace("%JS%", "\n      ".join(JS))
open(os.path.join(proj, "index.html"), "w").write(html)
print("TOTAL", TOTAL, "shots", len(cuts), "captions", gid)
