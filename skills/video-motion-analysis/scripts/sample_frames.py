#!/usr/bin/env python3
"""Sample a video at a fixed interval and tile the frames with burnt-in timestamps.

The point is to READ what actually happens instead of guessing at it. Use coarse
sampling to locate an event, then fine sampling to reconstruct it:

    # locate: where are the cuts, transitions and effects?
    python3 sample_frames.py video.mp4 --ms 200

    # reconstruct: what exactly happens across that transition?
    python3 sample_frames.py video.mp4 --ms 40 --from 7.6 --to 8.2

    # study one action, cropped to the hands
    python3 sample_frames.py raw.MP4 --ms 150 --from 27.65 --to 31.24 \
        --crop 0.03,0.38,0.62,0.42

Sheets are paged so each stays readable. Labels are drawn with PIL because many
ffmpeg builds ship without drawtext (no freetype).
"""
import argparse, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFont


def label_font(size):
    for path in ("/System/Library/Fonts/Menlo.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grab(src, t, dst, crop=None, width=420, label=None):
    """Extract one frame. Returns False when the sample lands past the last frame."""
    vf = []
    if crop:
        x, y, w, h = crop
        vf.append(f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}")
    vf.append(f"scale={width}:-1")
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.4f}", "-i", src,
                        "-frames:v", "1", "-vf", ",".join(vf), dst, "-y"],
                       capture_output=True)
    if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) == 0:
        return False
    if label:
        im = Image.open(dst).convert("RGB")
        d = ImageDraw.Draw(im)
        f = label_font(20)
        d.rectangle([4, 4, 4 + 10 * len(label) + 8, 30], fill=(0, 0, 0))
        d.text((9, 7), label, fill=(255, 220, 0), font=f)
        im.save(dst, quality=92)
    return True


def tile(paths, dst, cols):
    ims = [Image.open(p) for p in paths]
    w, h = ims[0].size
    rows = (len(ims) + cols - 1) // cols
    pad = 5
    sheet = Image.new("RGB", (cols * w + (cols + 1) * pad, rows * h + (rows + 1) * pad), (0, 0, 0))
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        sheet.paste(im, (pad + c * (w + pad), pad + r * (h + pad)))
    sheet.save(dst, quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--ms", type=int, default=200, help="sampling interval, default 200")
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--crop", help="x,y,w,h as fractions of the frame")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("--per-page", type=int, default=30)
    ap.add_argument("--out", default="motion-analysis")
    a = ap.parse_args()

    crop = tuple(float(v) for v in a.crop.split(",")) if a.crop else None
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                "-of", "csv=p=0", a.path],
                               capture_output=True, text=True).stdout or 0)
    if not dur:
        sys.exit(f"could not read a duration from {a.path}")
    t1 = a.t1 if a.t1 is not None else dur
    tag = os.path.splitext(os.path.basename(a.path))[0].replace(" ", "_")[:24] + f"_{a.ms}ms"

    os.makedirs(a.out, exist_ok=True)
    for f in os.listdir(a.out):
        if f.startswith(tag):
            os.remove(os.path.join(a.out, f))

    step, frames, t, i = a.ms / 1000.0, [], a.t0, 0
    while t < t1 - 1e-6:
        p = os.path.join(a.out, f"{tag}_f{i:04d}.jpg")
        if grab(a.path, t, p, crop=crop, label=f"{t:07.3f}s"):
            frames.append(p)
        t += step
        i += 1

    sheets = []
    for pg in range((len(frames) + a.per_page - 1) // a.per_page):
        dst = os.path.join(a.out, f"{tag}_page{pg + 1:02d}.jpg")
        tile(frames[pg * a.per_page:(pg + 1) * a.per_page], dst, a.cols)
        sheets.append(dst)
    for p in frames:
        os.remove(p)

    print(f"{len(frames)} frames every {a.ms}ms over {t1 - a.t0:.3f}s -> {len(sheets)} sheet(s)")
    for s in sheets:
        print("  " + s)


if __name__ == "__main__":
    main()
