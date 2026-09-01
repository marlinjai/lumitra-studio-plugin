#!/usr/bin/env python3
"""Fit a generated clip into an edit slot WITHOUT losing either keyframe.

Video models emit a fixed or minimum length (Kling 5s, Seedance 4s minimum) that
rarely equals the slot the clip has to fill. Trimming to the slot is the obvious
move and it is wrong: a two-keyframe generation converges on the approved END
frame only at its very end, so trimming throws that anchor away and leaves you on
the middle of the arc, which is exactly where the model has wandered furthest
from the source. Measured on a real shot: the trimmed tail sat at 1.12x zoom with
0.82 correlation to the source, while the untrimmed tail was 1.00x at 0.95.

So: time-remap the WHOLE clip onto the slot. Both keyframes survive by
construction. The cost is playback speed, and there are two ways to pay it:

  linear   every frame is sped up by the same ratio. Correct default.
  eased    the first and last `--protect` seconds stay at natural speed and the
           middle absorbs the compression. Use when the ratio is above ~1.5x,
           since the cut points are where a wrong pace reads as wrong.

Compensate in the PROMPT too: if you know the clip will be sped up 1.4x, ask the
model for a slow, deliberate performance so the remapped result lands natural.

Usage:
  python3 fit_to_slot.py in.mp4 out.mp4 --slot 3.586917 --fps 24000/1001
  python3 fit_to_slot.py in.mp4 out.mp4 --slot 2.377375 --mode eased --protect 0.3
"""
import argparse, subprocess, sys


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def build_filter(src_dur, slot, fps, mode, protect):
    ratio = src_dur / slot
    if mode == "linear" or protect <= 0 or ratio <= 1.0:
        # setpts scales presentation time; minterpolate then lands on the target
        # rate. Stretch/compress FIRST, interpolate second: interpolating first
        # only resamples frames that are about to be retimed again.
        return f"setpts={slot / src_dur:.9f}*PTS,minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1", ratio
    # eased: hold real time for `protect` at each end, absorb the rest mid-clip.
    # Solve the middle ratio so the total lands exactly on the slot.
    ends = 2 * protect
    if ends >= slot or ends >= src_dur:
        sys.exit(f"--protect {protect}s is too long for a {slot:.3f}s slot")
    mid_src, mid_out = src_dur - ends, slot - ends
    if mid_out <= 0:
        sys.exit("slot too short to protect both ends; use --mode linear")
    k = mid_out / mid_src
    # piecewise-linear PTS: t<protect -> 1:1; middle -> k; tail -> 1:1
    expr = (f"if(lt(T,{protect}),T,"
            f"if(lt(T,{src_dur - protect}),{protect}+(T-{protect})*{k:.9f},"
            f"{protect}+{mid_out:.9f}+(T-{src_dur - protect})))")
    return (f"setpts='({expr})/TB',"
            f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"), ratio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--slot", type=float, required=True, help="target duration in seconds")
    ap.add_argument("--fps", default="24000/1001")
    ap.add_argument("--mode", choices=("linear", "eased"), default="linear")
    ap.add_argument("--protect", type=float, default=0.3,
                    help="seconds of natural speed kept at each end in eased mode")
    ap.add_argument("--crf", default="16")
    a = ap.parse_args()

    src_dur = probe(a.src)
    vf, ratio = build_filter(src_dur, a.slot, a.fps, a.mode, a.protect)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", a.src, "-vf", vf, "-an",
                    "-t", f"{a.slot:.6f}", "-c:v", "libx264", "-preset", "slow",
                    "-crf", a.crf, "-pix_fmt", "yuv420p", "-r", a.fps, a.dst], check=True)
    got = probe(a.dst)
    print(f"{a.src} {src_dur:.3f}s -> {a.dst} {got:.3f}s "
          f"(slot {a.slot:.3f}s, {ratio:.2f}x faster, {a.mode})")
    if ratio > 1.5 and a.mode == "linear":
        print(f"  note: {ratio:.2f}x is a lot for a linear remap. Consider --mode eased, "
              f"and prompt for a slower performance next generation.")


if __name__ == "__main__":
    main()
