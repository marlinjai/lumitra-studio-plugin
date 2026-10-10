---
name: lumitra-studio
description: Generate brand-consistent images and video through Lumitra Studio (studio.lumitra.co). Batch prompts to images, mint characters as 7-view identity sheets, create brands with reference images, replace a person in an image or video clip with a cast character (routed by mode, analyzed before any spend, honest about what the still-swap route cannot preserve), and run published recipes (a workflow plus automatic follow-up like character creation). Use when the user wants bulk image generation, a consistent recurring character, branded visuals, AI b-roll, a person replaced in a video clip, or to run a named recipe by slug. Works through the studio_* MCP tools or the HTTP API with LUMITRA_STUDIO_API_KEY.
license: MIT
compatibility: Needs LUMITRA_STUDIO_API_KEY in the environment. The MCP path needs Node 20+ (npx). The script path needs bash, curl and jq. All generation calls spend money on the key.
metadata:
  author: Lumitra
  version: "0.3.0"
  homepage: https://studio.lumitra.co
---

# Lumitra Studio

Lumitra Studio is a hosted generation service. You send prompts, brand slugs and character slugs; the Studio injects brand style and character references server-side, calls the image or video provider, stores the result and returns a signed URL plus the exact cost in USD. Nothing runs locally.

Two ways in, same contract:

- **MCP tools** (`studio_*`, listed below). Prefer these when the `lumitra-studio` MCP server is connected.
- **HTTP API** with `Authorization: Bearer $LUMITRA_STUDIO_API_KEY`. Use it from scripts, or when the MCP server is not available. `scripts/batch-generate.sh` is the ready-made batch client.

## Credentials

1. Get an API key. Keys are self-serve and tenant-scoped, issued by [auth-brain](https://auth.lumitra.co) (Studio's identity provider), not by the Studio app itself: sign in at auth.lumitra.co, open your organization, and create a key under API Keys. Your organization also needs the `studio` app grant, which the Lumitra team enables during onboarding.
2. Export it in the environment that launches your agent client:

```bash
export LUMITRA_STUDIO_API_KEY="..."          # required
export LUMITRA_STUDIO_BASE_URL="https://studio.lumitra.co"   # optional, this is the default
```

Never print the key, never paste it into a prompt, never commit it. Every generation is metered on it, against the tenant's plan: a monthly USD cap and an optional per-minute rate limit. An organization without a plan of its own is held to a default monthly cap of 20 USD; only a plan the Lumitra operator set can be unlimited. A `402` with `code: "monthly_cap_reached"` means the monthly cap is reached: its `error` is a sentence to relay to the user as is (it names the reset date and says to ask the Lumitra operator, hello@lumitra.co, to raise the limit), and the body also carries `capUsd`, `usedUsd` and `resetsAt`. Do not retry a `402` before `resetsAt`. A `429` means the rate limit is hit (retry after the `Retry-After` header). Call `studio_get_usage` to check remaining budget before a large batch, or after either error to see what tripped. A `401` or `403` means the key is missing, invalid or revoked; stop and tell the user rather than retrying.

## First five minutes

A new organization starts empty. These three steps take it to one finished image and a known cost. They are the same three the Home dashboard at studio.lumitra.co walks a person through, so an agent and a person arrive at the same place. Before the first step, call `studio_list_projects` once: it proves the key works and lists the organization's projects (for a new organization that is usually one, slug `default`).

1. **Set up a brand, or skip.** A brand (a style prefix plus reference images) is optional in the Studio, and creating one is free. Over HTTP you can skip it: `POST /api/generate` with only a `prompt` starts an unbranded image job. On the Model Context Protocol (MCP) path the `studio_generate_image` tool requires a `brandSlug`, so create a brand first with `studio_create_brand` (a `name` and a `slug` are enough; add a `stylePrefix` when the user has a style in mind).
2. **Make one image.** Call `studio_generate_image` with that `brandSlug` and a `prompt`. This is the first call that spends money. It waits by default and returns the signed image `url` and `costUsd`; with `wait: false` it returns a `jobId` to poll with `studio_get_job`. The HTTP call behaves like `wait: false`: it answers `{ "jobId", "kind" }` and the image arrives by polling `GET /api/v1/jobs/{jobId}`. If the job ends `failed`, report its `errorMessage` and retry at most once. A failed job normally adds nothing to the organization's spend; trust its `costUsd` over that rule, because a job that fails after an earlier attempt of it succeeded keeps that attempt's cost, and the spend ledger counts it.
3. **See what it cost.** Tell the user the job's `costUsd`, then call `studio_get_spend` and show the total: it is the same ledger a person sees in the wallet at the top of every Studio page. `studio_get_usage` shows how much of the monthly cap is left.

Where the first image lands: `studio_generate_image` sends the `brandSlug` and no `projectId`, and the Studio files such a job under the project whose slug equals the brand slug, creating that project on first use. So the image from step 2 is in a project named after the brand, not in `default`; call `studio_list_projects` again to see it. Over HTTP, a call with neither `brandSlug` nor `projectId` lands in `default`, and a `projectId` in the body always wins. Spend is counted for the whole organization whichever project a job is in.

Stop there and ask what to make next. Minting a character, a batch or any video costs more, and each of those has its own section below.

## Concepts

| Term | What it is |
|---|---|
| **Project** | Top-level container. Every asset, character and run belongs to one. `studio_list_projects` gives ids; most accounts have one "default" project. |
| **Job** | One provider call (one image, one video, one edit). Has `status` (`queued`, `running`, `succeeded`, `failed`, `canceled`), `costUsd`, `model`, and on success a `resultAsset.url` (signed, re-signed on every read, so it stays fetchable). |
| **Brand** | A slug plus a style prefix, context text and a library of reference images. Passing `brandSlug` makes the Studio prepend the style and attach the references to every generation. |
| **Character** | A slug plus a descriptor prompt and a set of frozen reference images by **category**. Passing a character makes the Studio pin identity to those references. |
| **Workflow** | A small graph of nodes (`generate-image`, `image-edit`, `image-to-video`, ...). Each node becomes a Job. Runs return per-node result URLs. This is how multi-step recipes (swap then animate) execute server-side. |
| **Published recipe** | A workflow frozen under a stable public slug, optionally with a declared list of post-run effects (create a character, attach a reference). Run it by slug with `studio_run_published`; the effects fire automatically only if every node succeeds. See "Published recipes" below. |
| **Spend** | A ledger of every Job's `costUsd`. `studio_get_spend` reads it. |
| **Plan / usage** | Your organization's monthly USD cap (20 USD by default; only an operator-set plan is unlimited) and per-minute rate limit (unset = none), and month-to-date spend against them; a generation call fails with `402`/`429` once either is hit (see "Credentials" above). `studio_get_usage` reads the current state. |

## MCP tools and when to use each

| Tool | Use it to |
|---|---|
| `studio_list_projects` | Resolve the `projectId` you need for characters, workflows and runs. Call once, cache the id. |
| `studio_generate_image` | One prompt to one image job. Args: `prompt`, optional `brandSlug`, `brandMode`, `aspectRatio`, `model`, `projectId`. Returns `jobId`. |
| `studio_generate_3d` | One prompt, or one image (`imageUrl`), to one 3D model (a textured GLB mesh) through 3D AI Studio. Optional `model` (text: Tripo 3.1, Hunyuan Rapid or Pro; image: TRELLIS.2, Tripo 3.1), `options` quality flags that each change the price, `projectId`. Waits by default (one to five minutes) and returns the GLB `url` and `costUsd` (typically $0.25 to $0.70 per model). |
| `studio_rig_3d` | Rig a humanoid Model3D and animate it (Meshy on fal): `projectId`, `meshAssetId` (the `assetId` `studio_generate_3d` returns), up to 10 `animations` as preset names or ids, optional `heightMeters`. Walk and run clips always come with the rig. Waits by default (one to three minutes) and returns `rigUrl`, `clips` (name and url each) and `costUsd`: $0.20 per rig plus $0.12 per preset. Humanoids only. |
| `studio_find_animations` | Search the 678 Meshy presets `studio_rig_3d` can apply by words ("sword slash", "dance"). Free and local. |
| `studio_get_job` | Poll a `jobId` until terminal. Returns status, `costUsd`, `errorMessage`, `resultAsset.url`. |
| `studio_list_characters` / `studio_get_character` | Find an existing character and its reference URLs (you need the `full-body` or `face` URL for video swaps). |
| `studio_create_character` | Register a character row: `name`, `slug`, `descriptorPrompt`, `likenessRightsConfirmed: true` (see "The likeness confirmation"), optional `negativePrompt`, `defaultModel`. Does not generate images. |
| `studio_mint_character` | Run the 7-view identity sheet for a description and freeze the views as references on the character. The one-call path for "make me a consistent character". Needs `likenessRightsConfirmed: true`, and refuses before spending anything without it. |
| `studio_create_brand` | Register a brand: `name`, `slug`, optional `stylePrefix`, `context`. |
| `studio_upload_brand_reference` | Attach a reference image (file or URL) with a `category` and `label` to a brand's library. |
| `studio_run_workflow` | Execute an inline workflow definition (`projectId`, `definition`, optional `params`). Returns `runId`. |
| `studio_get_run` | Poll a run: overall status plus per-node status and cost. A run parked on a person comes back with a `waiting` block instead of more polling (see below). |
| `studio_decide_judge` | Pass a PERSON'S approve/reject on to a parked judge node. Never your own judgement. |
| `studio_get_run_output` | Fresh signed URL for one node's result (`runId`, `nodeId`). |
| `studio_replace_character_in_video` | The packaged video route: scene frame plus character reference, swap in a still, animate it. Pass an explicit `swapPrompt` (see "Character replacement"). Returns a `runId` to poll with `studio_get_run`. |
| `studio_get_spend` | Report what a session or time window cost. Call it at the end of any batch and tell the user the number. |
| `studio_get_usage` | Check the organization's monthly cap, per-minute rate limit and month-to-date spend before a large batch, or after a `402`/`429` to see what tripped. `usedUsd` includes in-flight (not yet settled) job estimates and can go DOWN as well as up when one fails, this is not a bug. |
| `studio_workflow_describe` | Learn the node vocabulary before authoring: task types with ports and prompt policy, input types, op types, patch limits. Add `includeModels: true` to pick a model id. |
| `studio_workflow_get` | Read a saved workflow as a summary (nodes, wires, `revision`, `projection`); `full: true` for the whole document. |
| `studio_workflow_create` | Build a new saved workflow from ops. Returns `savedId` and `revision`. Free. |
| `studio_workflow_apply` | Change a saved workflow atomically on top of `baseRevision`. Every refusal is a `{ ok: false, code, hint }` result to act on, not an error. Free. |
| `studio_workflow_validate` | Dry-run a document or saved workflow with ops and run params before spending anything. |
| `studio_workflow_screenshot` | Render a saved workflow as a labelled-box-and-wire diagram, the Figma `get_screenshot` equivalent. A diagnostic (is this wired the way I meant), not a pixel-exact preview. `{ savedId }` -> `{ url, width, height }`. Free. |
| `studio_list_published` | List every published recipe (`slug`, `label`, `hasEffects`). Call this before `studio_run_published` if you don't already know the slug. Free. |
| `studio_describe_published` | Read one recipe's frozen definition by slug, so you know what params it needs before running it. Free. |
| `studio_run_published` | Run a published recipe by slug. `{ slug }` -> `{ runId }`, effects fire automatically on a fully successful run. |

Rule of thumb: anything that creates a job is asynchronous. Submit, then poll with `studio_get_job` or `studio_get_run` every 5 seconds until the status is terminal. Do not poll faster than that.

### A run can stop and wait for a person

A workflow may contain a **judge node**: a step whose job is a human decision, not a provider call. When a run reaches one it parks, and `studio_get_run` reports the run as `awaiting_decision` with that node `awaiting_decision` too. This status is NOT terminal and polling will never clear it: nothing is running, and nothing will change until somebody approves or rejects the candidates the node is holding. Money already spent is reported on the parked run, so the cost you see is spend so far, not a final figure.

When you see it: stop polling, tell the user which node is waiting and what it is holding (the run response carries the parked node's `candidates`, each with a signed url and the `generationId` that names it), and ask them to decide. Submit their answer with `studio_decide_judge` (`{ runId, nodeId, verdict: "approved", candidate: { generationId } }`, or `{ verdict: "rejected", reason }`); approving resumes the run from that node, rejecting fails it and stops the branch. Never decide on the user's behalf: a judge node exists precisely because a person is meant to look.

## Batch image generation

Submit everything first, then poll everything. Wall-clock is the slowest single job, not the sum.

With MCP: call `studio_generate_image` once per prompt, collect the `jobId`s, then loop `studio_get_job` until each is `succeeded`, `failed` or `canceled`. Report every URL and the summed `costUsd`.

With the script (prompts on stdin, one per line):

```bash
printf '%s\n' \
  "a happy red dinosaur waving" \
  "a sleeping blue dinosaur under a blanket" \
| scripts/batch-generate.sh --brand my-brand --mode illustration --aspect 1:1 --out ./studio-out
```

Flags: `--brand <slug>` (optional; without it you get an unbranded image), `--mode <mode>`, `--aspect <ratio>` (default `1:1`), `--model <id>`, `--out <dir>` (download PNGs), `--budget <sec>` (poll budget, default 600). Exit code is non-zero if any job failed or timed out, so a pipeline can gate on it.

HTTP contract behind both:

```
POST {base}/api/generate
{ "brandSlug": "my-brand", "brandMode": "illustration", "prompt": "a happy red dinosaur waving",
  "settings": { "aspectRatio": "1:1", "model": "kie/nano-banana-2" } }
-> 200/202 { "jobId": "<uuid>", "kind": "generate_image" }

GET {base}/api/v1/jobs/{jobId}
-> { "job": { "status": "succeeded", "costUsd": 0.04, "model": "kie/nano-banana-2", "errorMessage": null },
     "resultAsset": { "url": "https://...signed...png" } }
```

`settings` also accepts `imageSize`, `candidateCount`, `seed`, `temperature`. `model` is optional; the Studio picks its default text-to-image model when omitted.

## Character minting (7-view identity sheet)

A minted character is a `seed` face plus six edit views pinned to that seed: `three-quarter`, `profile`, `full-body`, `close-up`, `lighting-warm`, `lighting-cool`. Together with the seed `face` that is the 7-category reference set (use these exact category names; they drive reference ranking in try-on and casting). Once frozen, every generation that references the character reuses the same identity.

### The likeness confirmation (required on every mint path)

Creating a character requires `likenessRightsConfirmed: true`. It records, on the character, that the person you act for confirmed this sentence:

> This character is not based on a real person, or the person shown gave me the rights to generate and mint their likeness.

**Ask the human, every time, for each character, and pass `true` only after they said yes. Never assert it on your own**, not because the description sounds invented, and not because an earlier character was confirmed: the confirmation belongs to one character. Show them the sentence as written and the terms at https://studio.lumitra.co/terms (terms and acceptable use, currently a draft pending legal review). If they cannot confirm it, do not mint: a real person's likeness without that person's rights is not allowed on the Studio.

What happens without it: `studio_mint_character` and `studio_create_character` refuse before any request is sent, so nothing is spent; the HTTP route `POST /api/characters` answers `422` with `code: "likeness_rights_confirmation_required"` and creates nothing; `studio_run_published` on a recipe that creates a character answers the same `422` before the run starts. The Studio stores who confirmed (your API key's service account), when, and the terms version. If `studio_mint_character` does not list a `likenessRightsConfirmed` argument, the server is `@marlinjai/studio-mcp` 0.2.0 or older and cannot mint any more: the Studio refuses its character-sheet run with `client_update_required` before anything is spent. Update the server to 0.3.0 or newer (`npx -y @marlinjai/studio-mcp@latest`) first.

Preferred path: `studio_mint_character` with `{ projectId, name, slug, description, likenessRightsConfirmed: true, negativePrompt?, visibility?: "listed" | "unlisted", waitSeconds? (default 600) }`. It runs the sheet workflow, waits, creates the character and uploads each view under its category, then returns `{ slug, name, runId, referenceCount, references[{ nodeId, category, referenceId, url }], costUsd }`. Pass `visibility: "listed"` when the human should see the mint on the Studio's Workflows page.

Manual path (when you want to inspect views before freezing):

1. `studio_run_workflow` with the character-sheet definition (seed node: text-to-image on `fal/nano-banana-2`; six `image-edit` nodes on `fal/nano-banana-2-edit` whose `inputImages` reference the seed).
2. Review the seven URLs with the user. If the seed face is wrong, re-run; do not freeze views from a rejected seed. Ask for the likeness confirmation here at the latest (better before step 1, so nothing is generated for a character that cannot be minted).
3. `studio_create_character` `{ name, slug, descriptorPrompt, likenessRightsConfirmed: true, negativePrompt? }`. Over plain HTTP that is `POST /api/characters` with the same body; without the field it answers `422` and creates nothing.
4. Upload each approved view: `POST /api/characters/{slug}/references/upload` (multipart `file`, `category` in `face|three-quarter|profile|full-body|close-up|lighting-warm|lighting-cool`, `label`).

Wardrobe variants (workwear, evening wear): one ad-hoc `image-edit` node on the `full-body` reference with a prompt like "change ONLY the clothing to ..., keep face, body and pose identical". Upload the result as an extra `full-body` reference with a descriptive label.

Expect about $0.30 per mint (7 images).

## Brands and references

```
POST /api/brands                        { "name": "My Brand", "slug": "my-brand", "stylePrefix": "flat vector, warm palette", "context": "children's book publisher" }
POST /api/brands/{slug}/library/upload  multipart: file, category (mood|style|identity|...), label
```

Same via `studio_create_brand` and `studio_upload_brand_reference`. After that, pass `brandSlug` (and optionally `brandMode`) on any generation and the Studio applies the style and attaches the references. Keep a brand library small and on-style: five strong references beat thirty mixed ones.

## Character replacement (images and video)

Goal: the result should look as though the original camera recorded the replacement character doing the original action. Prompt prose cannot guarantee that; the steps below make the constraints explicit and route each one to the stage that can actually enforce it. Load `references/character-replacement.md` for the full tables, the analysis record shape, the prompt templates and the review checks.

1. **Pick the mode first.** Source-matched replacement (change the person, keep everything else), creative restyling (deliberately change the look), or new scene generation (nothing to preserve). Realism vocabulary like haze, grain, visible pores or a mood palette belongs to the last two, and only where it fits; it is not a default for a replacement.
2. **Declare the scope and who owns each attribute.** Identity comes from the character references. Pose, expression, gaze, timing, lighting, focus, motion blur, camera, background and other people come from the footage. Clothing and props come from the footage unless the user assigns them to a reference. Body proportions follow the declared scope: identity-only keeps the source body; full-body takes the character's, which changes the silhouette, so the background behind the old body must be reconstructed and every contact point re-derived. When the request does not say which, ask before spending anything.
3. **Analyze before generating.** Sample the whole shot, not just its first and last frame: add frames at head turns, occlusions, hand contacts, lighting changes and focus pulls. Record observations separately from guesses, leave unknowns unknown, and never invent camera numbers (a single frame does not reveal aperture or focus distance; "stops out of focus" is not a unit). Give each constraint an owner: prompt, model control, compositing, or human review.
4. **Say honestly what the route can do.** Studio has no source-video editor today (a model that edits the original clip and keeps its real motion). The route it has is a still swap then image-to-video, which REGENERATES the motion between the frames rather than preserving it. When the original performance must survive exactly, tell the user this route cannot guarantee it before spending.
   - Swap the person in a still: `image-edit` on `fal/nano-banana-2-edit`, `inputImages: [scene_frame_url, character_reference_url]`.
   - Animate: `image-to-video`. `fal/kling-v2-5-image-to-video` takes a start and an end frame (swap both for shots longer than about 3 seconds to limit drift); the FLUX.3 keyframes tier pins up to ten swapped frames, which constrains the regenerated motion more tightly but still does not preserve it.
   - Do NOT use video-to-video character swap through Wan 2.2 Animate Replace (and the products that wrap it) on dark, handheld, motion-blurred footage or footage with hand-tool contact: it warped faces and limbs on every such shot tested.
5. **Write a short, specific prompt.** The requested change and exact target first, each reference's role, then the few preservation constraints most likely to fail in this shot, as concrete relationships ("keep the open door in front of his body; match the face's original softness"). Never append a realism suffix ("photorealistic, ultra-detailed, no artifacts"), and never promise physics in prose ("keep every pixel identical"): the model cannot guarantee it, and "tack-sharp" is exactly how a deliberately defocused subject comes back wrong.
6. **Inspect the keyframe before paying for video.** Check identity, pose, accessories, focus, lighting and edges on the swapped still first. Budget one candidate plus two retries per shot, retrying from the source rather than re-editing a degraded output, and classify each failure before retrying: a blurred edge is a compositing fix, not a re-render.
7. **Finish outside Studio.** Studio does not composite. Keep untouched pixels by compositing the replacement onto the original frame through a mask, then match blur, grain and colour to the source. Conform the frame rate, keep generated cuts at 4 seconds or less, and do not add a film look to clean digital footage.

`studio_replace_character_in_video` packages steps 4 and 5 and waits by default: `{ projectId, sceneFrameUrl, characterSlug (or characterReferenceUrl), endFrameUrl?, scope?, preserve?, swapPrompt?, motionPrompt?, videoModel?, visibility?, waitSeconds? }` -> `{ runId, status, stillUrl, videoUrl, costUsd, videoModel }`. **Declare `scope` and pass `preserve`:** `scope` is `identity` (the default: face, head and hair from the character, the footage keeps its body) or `full_body` (the character's body proportions too, which changes the silhouette); `preserve` takes the two or three shot-specific constraints from step 3 that are most likely to fail, and the tool composes a short prompt from both with no realism suffix. A complete `swapPrompt` of your own replaces the composed one. (Before `@marlinjai/studio-mcp` 0.2.0 the built-in prompt carried a realism suffix and silently took the body too, so on an older server always pass `swapPrompt`.) Without `endFrameUrl` it animates the single swapped still with `fal/seedance-pro-image-to-video`; with `endFrameUrl` (a second approved keyframe) it switches to `fal/kling-v2-5-image-to-video` and interpolates between both frames: have the human approve both swapped frames (`stillNodeId: "edit"`), then run the video node. Fetch the clip with `studio_get_run_output` for node `video`.

Inline definition if you run it yourself with `studio_run_workflow` (the swap prompt is an example for a defocused, identity-only shot; compose your own from the analysis):

```json
{
  "nodes": [
    { "id": "edit", "task": "image-edit", "model": "fal/nano-banana-2-edit",
      "inputs": { "inputImages": { "kind": "literal", "value": ["<scene_frame_url>", "<character_reference_url>"] },
                  "prompt": { "kind": "literal", "value": "Replace the selected mechanic's identity with the person in the second image. Preserve his cap, glasses, work clothes, head angle, expression and tool grip. Keep the open door in front of his body. Match the original face's soft focus and the scene's lighting and colour." } } },
    { "id": "video", "task": "image-to-video", "model": "fal/kling-v2-5-image-to-video",
      "inputs": { "inputImageUrl": { "kind": "ref", "node": "edit", "path": "url" },
                  "prompt": { "kind": "literal", "value": "keep the original camera and the subject's original movement" } } }
  ]
}
```

Binding kinds: `literal` (value inline), `param` (from `params`), `ref` (another node's output; add `"wrap": "array"` when the target expects an array, as `inputImages` does). About $0.70 per shot per take.

## Authoring workflows (the command model)

A saved workflow is a revisioned document that the Studio canvas, the HTTP API and the `studio_workflow_*` tools all edit through the same op vocabulary, so you and a human can work on the same workflow without overwriting each other. Authoring is free; `studio_run_workflow` with the `savedId` is what spends money.

1. `studio_workflow_describe` once per session (filter with `tasks`, add `includeModels: true` when you need model ids).
2. `studio_workflow_create` with ops: `addNode` for each node (an `input` node is a declared run parameter; `task` nodes carry `task`, `model`, `prompt`), `connect` for each wire (`source`, `target`, `port`). Pick your own node ids. Check `summary.projection`: `ok: false` lists why it cannot run yet (`no_model`, `prompt_required`, ...).
3. `studio_workflow_apply` to change it: pass the `revision` you last saw as `baseRevision`. Every refusal comes back as `{ ok: false, code, hint }`, so read the `code` and do what it says: `stale_revision` (someone else changed it: read the returned `summary`, rebase your ops, apply again on the new revision), `invalid_patch` (`error.opIndex` names the offending op), `forbidden` (`missingScope` names what your key lacks), `not_editable` (this workflow cannot be patched at all: it is still runnable, build a new one instead), `lossy_import` (read `notes`, then resend the same ops with `acknowledgeLossy: true` and a NEW `idempotencyKey`), `idempotency_mismatch` (that key was used for different ops: send a fresh one). On `network_error` or `server_error`, retry with the SAME `idempotencyKey` the result carries, never with a fresh one; `replayed: true` in a success result means the earlier attempt had already landed.

   A workflow the canvas cannot represent is served read-only: `studio_workflow_get` returns `readOnly: true` with no nodes, and only `studio_run_workflow` works on it. One flagged `needsLossyAcknowledgement: true` needs the `acknowledgeLossy` confirmation on its first patch.
4. `studio_workflow_validate` with `savedId` and the run `params` before running: missing required inputs and unknown params surface here, at no cost.
5. `studio_run_workflow` with `projectId`, `savedId` and `params`.

Never rebuild a workflow from scratch to change one thing: read it, apply the ops that change that thing.

## Published recipes

A recipe is a workflow published under a stable public slug (done through the HTTP API or on the canvas, not yet an MCP tool): its document and an optional declared list of post-run effects (create a character, attach a reference, create a brand) are frozen together at publish time.

1. `studio_list_published` to see what exists (or ask the user for the slug directly).
2. `studio_describe_published` with the slug to see the frozen definition and its params.
3. `studio_run_published` with the slug, `projectId` and `params` to run it. A recipe that creates a character also needs `likenessRightsConfirmed: true` (the same confirmation, asked of the human the same way); without it the run is refused with `likeness_rights_confirmation_required` before anything is spent.

Running a recipe always executes the FROZEN definition, never the live authoring document, which may have moved on since publish. If every node in the run succeeds, the declared effects fire automatically and exactly once; a failed, partial or still-parked run never triggers them, so a broken run can never leave a half-created character, and a recipe whose graph contains a judge node creates nothing until the person has approved it. `studio_mint_character` and `studio_replace_character_in_video` are today still hand-written tools, not recipes, so both patterns currently coexist.

## Spend confirmation

A run whose estimated cost meets or exceeds $10 needs explicit confirmation: without it, `studio_run_workflow` / `studio_run_published` refuse with `confirmation_required` and no run is created, nothing is spent. Re-send the SAME request with `confirm: true` to proceed. This is a hard stop, not a warning: always tell the user the estimate and get a go-ahead before adding `confirm: true` yourself, the same rule the "Cost expectations" section below already asks for on any batch over 20 images.

## Cost expectations

| Operation | Typical cost |
|---|---|
| One image (`kie/nano-banana-2` default) | about $0.04, about 40 s |
| Character mint (7 views) | about $0.30 |
| Still swap (one edit) | about $0.05 |
| 5 s image-to-video | $0.35 (Kling base) to $0.62 (Seedance 1080p) |
| One video shot, one take (swap plus animate) | about $0.70 |

Every job reports its real `costUsd`. Sum it, and always tell the user the total at the end of a batch. Before a batch larger than 20 images or any video work, state the estimate and get a go-ahead.

## Failure handling

- Job `failed`: read `errorMessage`, report it, do not auto-retry more than once.
- Poll budget exhausted: report which jobs are still pending with their ids; they keep running server-side and can be read later with `studio_get_job`.
- `401`/`403`: key problem, stop.
- `429`: rate limit hit, see the response's `Retry-After` header (seconds) for when to resume polling; do not resubmit before then.
- A workflow run where one node fails leaves the others intact; read the successful nodes' outputs before deciding to re-run.

## Streamable HTTP instead of stdio

If your client prefers a network MCP endpoint, start the server yourself:

```bash
LUMITRA_STUDIO_API_KEY=... npx -y @marlinjai/studio-mcp --http --port 3939
```

and point the client at `http://127.0.0.1:3939/mcp` with transport `streamable-http`. Tool names and behaviour are identical.
