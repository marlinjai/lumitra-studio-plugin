# Character replacement: reference

Load this when replacing a person in an image or a video clip, or when a
generation has to look like it was photographed. `SKILL.md` carries the steps;
this file carries the tables, the prompt templates and the review checks.

The goal: **a replacement should look as though the original camera recorded the
replacement character performing the original action.** Four visual pillars
decide that (lighting, depth, texture, colour), and footage adds four more
(identity continuity, temporal continuity, physical contact, and an untouched
surrounding scene). A convincing still does not prove any of them survive motion.

## 1. Modes

Route every request into exactly one mode before writing a prompt.

| Mode | Intended result | Default preservation rule |
|---|---|---|
| Source-matched replacement | Change the selected identity, head, or body | Preserve the source performance, optics, camera, timing and environment within the declared scope |
| Creative restyling | Deliberately change the look or the environment | Change only the requested visual properties, and name those choices |
| New scene generation | A shot with no existing performance to preserve | Design lighting, lens behaviour, texture, palette, camera and action together |

Identity-only, full-body, altered proportions, changed wardrobe and changed
performance are separate choices. When the request does not say which, show the
user the target and the inherited attributes and ask, before anything is spent.

## 2. Authority by attribute

In source-matched replacement each attribute has one authoritative source. Do not
give every reference equal weight.

| Attribute | Authoritative source |
|---|---|
| Requested changes and explicit overrides | The user's current instruction |
| Identity, facial structure, natural skin pigmentation, identifying features | The approved character references |
| Pose, expression, gaze, gesture, contact timing, dialogue performance | The original footage |
| Clothing, cap, glasses, held props | The original footage, unless explicitly assigned to a reference |
| Body proportions and silhouette | The declared replacement scope; the source when unspecified |
| Illumination, focus, motion blur, perspective, camera movement | The original footage |
| Background and other people | The original footage |
| Continuity across shots | The approved character and wardrobe, with each shot's own lighting and focus |

Two failure pairs to avoid: matching the scene's light must not turn the
character's skin into the original actor's skin colour, and matching identity
must not import the reference portrait's studio lighting, smile, clothes or
sharpness.

A **full-body** scope (the body comes from the character, not the footage)
changes the silhouette. That has consequences to state before spending: the
background the old body covered must be reconstructed, not kept; every contact
point and occlusion (a hand on a tool, a shoulder behind a door) must be
re-derived; and a composite needs a mask covering both silhouettes plus the
revealed background.

## 3. The analysis record

Analyze before generating. The record separates what is seen from what is
guessed, and leaves unknowns unknown.

```json
{
  "mode": "source_matched_replacement",
  "replacement_scope": "identity_only | head | full_body",
  "references": [{ "url": "...", "role": "identity | wardrobe | source_frame | performance | look" }],
  "inherit": { "identity": "reference", "wardrobe": "source", "performance": "source", "optics": "source", "scene": "source" },
  "constraints": [
    {
      "domain": "lighting | depth | texture | colour | motion | occlusion | contact",
      "region": "target_face",
      "evidence_frames": ["00:00:02.10", "00:00:03.40"],
      "observation": "Face edges are softer than the foreground worker's edges.",
      "inference": "Defocus likely contributes; motion blur is not excluded.",
      "confidence": "low | medium | high",
      "measured_value": null,
      "instruction": "Match the target face's original apparent softness.",
      "enforcement": ["prompt", "compositing", "review"],
      "check": "Compare corresponding edges at matched resolution."
    }
  ],
  "unresolved": ["Frame timestamps and colour interpretation not verified."]
}
```

Rules for the record:

- **Never invent camera numbers.** A single frame does not reveal aperture,
  focal length, focus distance or whether a blurred subject sits in front of or
  behind the focus plane. "1.2 stops out of focus" is not a unit of defocus.
  Use relative observations ("softer than the door frame") and say how sure.
- **A confidence label is not a probability.** "High" means the evidence looks
  strong, not "95 percent likely".
- **Sample the whole shot,** not just its first and last frame: add frames at
  head turns, occlusions, contact changes, lighting changes and focus pulls.
  Two end frames can agree while the middle loses the glasses.
- **Give every constraint an owner:** the prompt, a model control, compositing,
  or human review. A constraint no stage enforces is a wish.

## 4. Conditional vocabulary

Realism words help only when the source supports them. Never append a universal
suffix ("photorealistic, ultra-detailed, cinematic lighting, no artifacts"):
each of those can contradict the footage (tack-sharp on a defocused subject is
the classic failure).

| Phrase | Use only when | Source-matched form |
|---|---|---|
| Shadow-side lighting | The camera already sees mostly the face's shadow side | Preserve the original lit-to-shadow arrangement as the head turns |
| Motivated practical light | A visible or clearly implied fixture explains the light | Match the light from the existing lamp and its changes across the shot |
| Soft window light | Broad soft light is visible in the source | Match the broad light and its soft facial shadow edges |
| Shallow depth of field | The shot actually has selective focus | Match the target's original focus and the existing background separation |
| Foreground slightly out of focus | Those elements are visibly defocused | Preserve the foreground blur and its overlap with the character |
| Haze, atmospheric depth | Scattering is visible, or restyling was requested | Preserve the observed depth-dependent loss of contrast |
| Visible pores, skin texture | The face is large and sharp enough to resolve them | Render skin detail only at the sharpness the source supports |
| Film grain, filmic softness | The source has it | Match the source's noise and edge softness; never add a film look to clean digital footage |
| Mood palette (amber, teal, sage) | Creative restyling or new generation only | In replacement mode the photographed scene wins |

Colour phrases that belong in replacement prompts: match the source white balance
and tint; preserve the character's natural skin pigmentation under the source
lighting; match local saturation, contrast, black level and highlight response;
preserve existing mixed lighting (a warm lamp beside a cool window).

## 5. Prompt templates

Keep the planning instructions (long) separate from the prompt the image or
video model receives (short). Put masks, sizes, frame times and seeds in real
control fields; mentioning an unsupported control in prose does not make the
model obey it.

### Planning (the analysis step)

```text
You plan source-matched character replacements in real images and footage.
Read the allowed changes, source media, identity references, reference roles and
available model controls. Determine the target and the replacement scope, and
preserve source attributes by the inheritance rules.
Analyze lighting, depth and focus, texture, colour, identity visibility, motion,
occlusions, contacts, shadows, reflections and events over time. For each
material constraint give an observation, the evidence frame or region, an
inference only when useful, an uncertainty label, an instruction, an
enforcement owner and an acceptance check.
Use unknown for unsupported measurements. Do not infer focal length, aperture,
focus distance, shutter angle, light temperature or metric depth without
evidence. Do not add haze, pores, scars, bloom, grain, darker exposure or lens
effects by default. Flag conflicts between identity, silhouette, pose, contact
and edit region. Do not claim a prompt guarantees physics, pixel preservation
or temporal consistency.
```

### Composing the edit prompt

```text
Start with the requested change and the exact target. State each reference's
role. Add only the few preservation constraints most likely to fail in this
shot, as concrete relationships rather than adjectives. Keep replacement,
restyling and new generation distinct. No universal realism suffix. No camera
movement, emotion or action in a replacement unless requested. When revising
after a failure, change the relevant instruction without dropping the others.
```

### Reviewing a result

```text
Compare the candidate with the source, the approved references and the editing
contract. Judge source matching separately from attractiveness: a more
cinematic image can still be a failed replacement. Check identity, pose,
expression, gaze, wardrobe, props, camera, timing and untouched content; then
lighting, focus, texture, colour, occlusion order, contact, shadows and
continuity through motion. Mark obscured attributes not_assessable, never
passed or failed. Return pass, repair, rerender or review_required, with each
failure's time or region, evidence, severity and responsible stage. Never
certify coverage you did not inspect.
```

### Applied examples (illustrative, not tested claims)

Defocused mechanic, identity only:

> Replace the selected mechanic's identity with reference A. Preserve his cap,
> glasses, work clothes, original head angle, expression, hand placement and
> tool grip. Keep the open door in front of his body. Render his face with the
> same apparent softness as the original face, and keep the hands' directional
> motion blur. Match the source lighting and colour response.

Sharp daylight close-up:

> Replace the selected face with the identity in reference A, keeping the source
> expression and gaze. Match the existing hard daylight and facial shadow
> transitions. Resolve skin detail at the source's sharpness and scale, keeping
> reference A's identifying features and pigmentation under that light.

Targeted repair after review:

> The approved identity and pose are correct. The face is sharper than the
> source in frames 40 to 72. Preserve identity and performance; match the
> original face's edge softness across that interval.

A repair prompt is a regeneration only if generation caused the defect. A layer
that merely needs blur is fixed in finishing, not re-rendered.

## 6. Resolution, colour and timing

- **Resolution:** record source and output dimensions and any crop or scale.
  An edit returned at 1365 x 768 from a 1920 x 1080 frame keeps about half the
  pixels; upscaling restores the size, not the lost detail. Keep native source
  pixels outside the edit region.
- **Colour:** do not send log footage to an image editor without a deliberate
  viewing conversion, and do not claim an edited display image converts back to
  the original log capture.
- **Timing:** a provider returning 24 fps from a 25 fps source must not silently
  change duration, action timing or lip sync. Report any retime.

## 7. Review checks and retry budget

| Check | How | Limit |
|---|---|---|
| Untouched content | Difference outside the permitted edit region | Lossy encoding changes pixels everywhere; compare like with like |
| Identity | Reference comparison at assessable angles | Small, blurred or occluded faces may be unassessable; never sharpen to pass |
| Wardrobe and accessories | Per-shot, and after every occlusion or head turn | Not just first and last frames |
| Focus and blur | Corresponding edges at matched scale | No universal sharpness threshold |
| Lighting and colour | Shadows, highlights, mixed light over time | Different pigmentation must not be forced to the source colours |
| Physical contact | Grips, foot plants, overlap order | A full-body change cannot keep hands pixel-identical; keep the contact relationship |
| Temporal stability | Watch at normal speed, then the hard moments | A frozen subject is not stability |

Critical failures (wrong target, identity lost where assessable, broken contact,
damaged background outside scope, timing mismatch) are never averaged away by
other good scores.

Defect categories: `identity_drift`, `accessory_loss`, `focus_mismatch`,
`motion_blur_mismatch`, `lighting_mismatch`, `color_transform_error`,
`contact_failure`, `occlusion_failure`, `matte_failure`, `background_drift`,
`temporal_flicker`, `resolution_mismatch`, `timing_mismatch`.

Budget: one initial candidate plus two retries per shot, retrying from the
source or an approved checkpoint, never by re-editing an already degraded
output. Stop sooner when another prompt cannot supply the missing capability,
and switch route instead: a different reference, a shorter segment, another
model, compositing, or manual treatment.
