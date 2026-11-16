"""Synthetic gaming-stream footage for the facecam picker (needs opencv + scikit-image; tests skip without them).
Face = the bundled astronaut photo (a real face the Haar cascades find). Layout: 1280x720, noisy 'gameplay' background,
optional facecam box with border at a side, optional 'game character' face in the middle."""
import subprocess
import numpy as np


def make(path, side=None, centre=False, second_side=None, secs=4, fps=25):
    import cv2
    from skimage import data
    face = cv2.cvtColor(data.astronaut(), cv2.COLOR_RGB2BGR)[0:300, 100:400]            # head and shoulders
    W, H = 1280, 720; rng = np.random.default_rng(1)
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast", path]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(secs * fps):
        bg = np.full((H, W, 3), 90, np.uint8)
        for k in range(14):                                                                # moving blocks = 'gameplay'
            x = int((k * 97 + i * (6 + k)) % (W - 120)); y = int((k * 53 + i * (3 + k % 5)) % (H - 80)); cv2.rectangle(bg, (x, y), (x + 120, y + 80), (20 + k * 15, 200 - k * 9, 60 + k * 10), -1)
        bg = cv2.add(bg, rng.integers(0, 25, bg.shape, dtype=np.uint8))
        def put(cx, cy, w, border):
            h = int(w * 0.8); f = cv2.resize(face, (w, h)); j = int(6 * np.sin(i / 4)); f = cv2.convertScaleAbs(f, alpha=1.0, beta=8 * np.sin(i / 3))
            x0, y0 = int(cx - w / 2), int(cy - h / 2); M = np.roll(f, j, axis=1); bg[y0:y0 + h, x0:x0 + w] = M
            if border: cv2.rectangle(bg, (x0 - 3, y0 - 3), (x0 + w + 3, y0 + h + 3), (255, 255, 255), 6)
        if side == "left": put(190, 560, 300, True)
        if side == "right": put(W - 190, 150, 300, True)
        if second_side == "right": put(W - 190, 150, 300, True)
        if centre: put(W // 2, 380, 280, False)
        pr.stdin.write(bg.tobytes())
    pr.stdin.close(); pr.wait(); return path
