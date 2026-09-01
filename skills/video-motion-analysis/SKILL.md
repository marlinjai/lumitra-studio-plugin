---
name: video-motion-analysis
description: >
  Read what footage actually does before prompting a video model, and verify what
  the model gave back. Use when generating video from real footage (character
  replacement, shot recreation, b-roll matched to an edit), when generated motion
  looks "weird" or "not like the original", when a generated clip seems more
  zoomed in or less wide than its source, when reconstructing transitions and
  effects from a finished video, or when fitting a fixed-length generation into a
  shorter edit slot. Triggers on "the hands move wrong", "doesn't match the
  original", "less wide than the original", "rebuild this transition", "why does
  it drift", "sample the footage", "analyse the motion".
---

# Video motion analysis

Video models are bad at inventing motion and good at interpolating between anchors
you give them. Most "the AI clip looks wrong" problems are therefore not model
problems. They are one of three things, and all three are measurable:

1. the prompt described no actual action, so the model invented one;
2. the generation was trimmed, throwing away the anchored end;
3. the slot it was cut into does not correspond to the source it was matched from.

Never re-roll on a hunch. Measure first, then change one thing.

## 1. Read the motion before you write the prompt

A prompt like "small precise hand movements" gives a model nothing to hold onto and
it will fill the time with plausible-looking wander. Sample the source and describe
what is actually there: which limb moves, in which direction, how many times, and
with what cadence.

```bash
# one shot, cropped to the hands, fine enough to count repetitions
python3 scripts/sample_frames.py raw.MP4 --ms 150 --from 27.65 --to 31.24 \
    --crop 0.03,0.38,0.62,0.42
```

Read off the sheet and write the cycle into the prompt: the stroke, its direction,
the reset between strokes, how many fit in the shot. "Presses the file down and
pushes it the full length of the strip, lifts it clear, returns to the near end,
pushes again, about three times" beats any amount of adjectives.

## 2. Coarse to locate, fine to reconstruct

Two passes, different intervals, different jobs.

```bash
# locate: where are the cuts, transitions, effects? 200ms over the whole file
python3 scripts/sample_frames.py finished-video.mp4 --ms 200

# reconstruct: what exactly happens across one transition? 40ms over a 0.6s window
python3 scripts/sample_frames.py finished-video.mp4 --ms 40 --from 7.6 --to 8.2
```

200ms is too coarse to see a transition, which typically runs 6 to 12 frames. It is
the right interval to FIND one. Once located, resample the window at 40ms (roughly
one frame at 24fps) to see the mechanism: which direction it wipes, whether there
is a blur, a scale punch, an offset, how many frames each stage takes.

Study effects on the FINISHED export, never the raw footage. Raw footage contains
the action; only the export contains the grade, the transitions and the effects.

## 3. Verify the generation against its source

```bash
python3 scripts/compare_framing.py --source raw.MP4 --source-in 27.652 \
    --generated clip.mp4 --duration 3.587 --check-tail
```

Two numbers matter. `zoom` above 1.00 means the generation pushed in: 1.20 means the
viewer sees only 83 percent of the original width. Falling `corr` across the clip
means the model is inventing rather than animating.

Rising zoom plus falling corr across a clip whose FIRST frame measured 1.00x is the
signature of a trimmed two-keyframe generation. Check the tail before blaming the
model.

## 4. Fitting a fixed-length generation into a shorter slot

Models emit fixed or minimum lengths that rarely match your slot: Kling 2.5 is 5s,
Seedance 2.x takes `duration` 4 to 30s but no lower than 4. Edit slots are often
2 to 4s. Something has to give.

**Do not trim.** In a two-keyframe generation the model converges on the approved
end frame only at the very end. Trimming discards that convergence and leaves you
parked in the middle of the arc, which is exactly where the model has drifted
furthest. Measured on real shots: trimmed tails sat at 1.12x and 1.23x zoom with
0.82 and 0.42 correlation; the same generations untrimmed ended at 1.00x with 0.95
and 0.85. Trimming turned a good generation into a bad clip.

Instead, remap the whole clip onto the slot so both keyframes survive by construction:

```bash
python3 scripts/fit_to_slot.py gen.mp4 out.mp4 --slot 3.586917
python3 scripts/fit_to_slot.py gen.mp4 out.mp4 --slot 2.377375 --mode eased --protect 0.3
```

Then pay the speed cost deliberately, in this order:

- **Ask for a duration close to the slot.** Seedance's 4s floor beats Kling's fixed
  5s. On a 2.38s slot that is 1.68x rather than 2.14x.
- **Prompt for a slower performance.** If you know the result will be sped up 1.4x,
  ask for slow and deliberate motion so the remapped clip lands natural. The speed
  factor is known before you generate, so bake it in.
- **Use `--mode eased` above roughly 1.5x.** It holds real speed for the first and
  last few tenths and absorbs the compression mid-shot. Cut points are where a
  wrong pace is most visible; the middle is where it hides.
- Above about 2x, stop and reconsider the slot. That much compression will read as
  fast no matter how it is distributed.

Order matters: stretch or compress time FIRST, then interpolate to the target frame
rate. Interpolating first only resamples frames you are about to retime again, which
produces duplicates instead of smooth motion.

## 5. Check the slot before you spend

If the edit was reconstructed rather than recovered from a project file, verify each
slot against the finished export before generating anything into it. Sample both at
the same timeline moment and compare. A slot matched to the wrong source clip cannot
be rescued by any prompt or model, and every keyframe derived from it is wrong too.
This is the cheapest check available and the most expensive one to skip.

## Model notes

- **Two keyframes beat one** for anything over ~3s. The end frame is what stops
  drift. Kling 2.5 (`tail_image_url`) and Seedance 2.x (`end_image_url`) both take
  one; Seedance 1.0 Pro does not.
- **Seedance 2.x generates audio by default and bills for it.** Pass
  `generateAudio: false` for silent clips destined for an existing edit.
- **Seedance 2.x bills by token**, so cost scales with resolution as well as
  duration: `(w * h * seconds * 24) / 1024` at $0.0214 per 1000 tokens. 1080p is
  2.25x the same clip at 720p. Generate at 720p while iterating on motion; move to
  1080p only once the motion is approved.
