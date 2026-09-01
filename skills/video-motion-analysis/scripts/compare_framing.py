#!/usr/bin/env python3
"""Measure how far a generated clip has drifted from its source, in framing and content.

Video models push in over a shot. You cannot eyeball a 6 percent zoom, but it
compounds: by the end of a clip it reads as "the AI shot is less wide than the
original" without anyone being able to say why. This measures it.

For each sample it searches the zoom (and centre) that best maps the SOURCE frame
onto the GENERATED frame, and reports:

  zoom  1.00 means identical framing; 1.20 means the generated frame shows only
        83 percent of the source width, i.e. it has pushed in.
  corr  normalised correlation. Falling corr across a clip means the model is
        inventing content rather than animating the source.

Usage:
  # drift across a generated clip against the matching span of its source
  python3 compare_framing.py --source raw.MP4 --source-in 27.652 \
      --generated clip.mp4 --duration 3.587

  # is the tail landing on the approved end frame? (run on the UNTRIMMED output)
  python3 compare_framing.py --source raw.MP4 --source-in 27.652 \
      --generated raw_gen.mp4 --duration 3.587 --check-tail
"""
import argparse, io, itertools, subprocess, sys
import numpy as np
from PIL import Image

GW, GH = 320, 180


def frame(path, t):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", path,
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True)
    if not p.stdout:
        return None
    return Image.open(io.BytesIO(p.stdout)).convert("L")


def norm(a):
    a = a.astype(np.float32)
    a -= a.mean()
    s = a.std()
    return a / s if s > 1e-6 else a


def best_zoom(src_im, gen_im, zmax=1.7, coarse=0.25):
    if src_im is None or gen_im is None:
        return None
    g = norm(np.asarray(gen_im.resize((GW, GH), Image.LANCZOS)))
    W, H = src_im.size
    best = None
    for s in np.arange(1.00, zmax, 0.01):
        cw, ch = W / s, H / s
        for fx, fy in itertools.product(np.arange(0, 1.01, coarse), repeat=2):
            x0, y0 = (W - cw) * fx, (H - ch) * fy
            c = src_im.crop((round(x0), round(y0), round(x0 + cw), round(y0 + ch)))
            v = norm(np.asarray(c.resize((GW, GH), Image.LANCZOS)))
            sc = float((v * g).mean())
            if best is None or sc > best[0]:
                best = (sc, float(s))
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--source-in", type=float, default=0.0)
    ap.add_argument("--generated", required=True)
    ap.add_argument("--duration", type=float, required=True,
                    help="length of the shot in the SOURCE, i.e. the slot length")
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--check-tail", action="store_true",
                    help="also compare the generated clip's own final frame to the source's last frame")
    a = ap.parse_args()

    gen_dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                    "format=duration", "-of", "csv=p=0", a.generated],
                                   capture_output=True, text=True).stdout)
    print(f"source {a.source} @{a.source_in:.3f}s for {a.duration:.3f}s")
    print(f"generated {a.generated} ({gen_dur:.3f}s)\n")
    print(f"{'progress':>9}  {'zoom':>6}  {'width kept':>10}  {'corr':>6}")
    worst = 1.0
    for i in range(a.samples):
        p = i / max(1, a.samples - 1)
        r = best_zoom(frame(a.source, a.source_in + p * a.duration),
                      frame(a.generated, p * gen_dur))
        if not r:
            print(f"{p * 100:8.0f}%   (no frame)")
            continue
        sc, z = r
        worst = max(worst, z)
        print(f"{p * 100:8.0f}%  {z:6.2f}  {100 / z:9.0f}%  {sc:6.3f}")

    if a.check_tail:
        fps_t = 1 / 24.0
        r = best_zoom(frame(a.source, a.source_in + a.duration - fps_t),
                      frame(a.generated, gen_dur - fps_t))
        if r:
            sc, z = r
            print(f"\ntail frame vs source last frame: zoom={z:.2f} corr={sc:.3f}")
            print("  zoom near 1.00 with high corr means the end keyframe was honoured.")
            print("  If it is, do NOT trim this clip: remap it (see fit_to_slot.py).")

    if worst >= 1.05:
        print(f"\nworst drift {worst:.2f}x. If this clip was trimmed rather than remapped, "
              f"that is likely the cause: the anchored tail was discarded.")


if __name__ == "__main__":
    main()
