---
name: lumitra-studio
description: Generate brand-consistent images and video through Lumitra Studio (studio.lumitra.co). Batch prompts to images, mint characters as 7-view identity sheets, create brands with reference images, put a cast character into video with the still-swap plus image-to-video recipe, and run published recipes (a workflow plus automatic follow-up like character creation). Use when the user wants bulk image generation, a consistent recurring character, branded visuals, AI b-roll, a person replaced in a video clip, or to run a named recipe by slug. Works through the studio_* MCP tools or the HTTP API with LUMITRA_STUDIO_API_KEY.
license: UNLICENSED
compatibility: Needs LUMITRA_STUDIO_API_KEY in the environment. The MCP path needs Node 18+ (npx). The script path needs bash, curl and jq. All generation calls spend money on the key.
metadata:
  author: Lumitra
  version: "0.1.0"
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

Never print the key, never paste it into a prompt, never commit it. Every generation is metered on it, against the tenant's plan (a monthly USD cap and a per-minute rate limit, both optional): a `402` means the monthly cap is reached (the body carries `capUsd`, `usedUsd`, `resetsAt`), a `429` means the rate limit is hit (retry after the `Retry-After` header). Call `studio_get_usage` to check remaining budget before a large batch, or after either error to see what tripped. A `401` or `403` means the key is missing, invalid or revoked; stop and tell the user rather than retrying.

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
| **Plan / usage** | Your organization's monthly USD cap and per-minute rate limit (either may be unset = unlimited), and month-to-date spend against them; a generation call fails with `402`/`429` once either is hit (see "Credentials" above). `studio_get_usage` reads the current state. |

## MCP tools and when to use each

| Tool | Use it to |
|---|---|
| `studio_list_projects` | Resolve the `projectId` you need for characters, workflows and runs. Call once, cache the id. |
| `studio_generate_image` | One prompt to one image job. Args: `prompt`, optional `brandSlug`, `brandMode`, `aspectRatio`, `model`, `projectId`. Returns `jobId`. |
| `studio_get_job` | Poll a `jobId` until terminal. Returns status, `costUsd`, `errorMessage`, `resultAsset.url`. |
| `studio_list_characters` / `studio_get_character` | Find an existing character and its reference URLs (you need the `full-body` or `face` URL for video swaps). |
| `studio_create_character` | Register a character row: `name`, `slug`, `descriptorPrompt`, optional `negativePrompt`, `defaultModel`. Does not generate images. |
| `studio_mint_character` | Run the 7-view identity sheet for a description and freeze the views as references on the character. The one-call path for "make me a consistent character". |
| `studio_create_brand` | Register a brand: `name`, `slug`, optional `stylePrefix`, `context`. |
| `studio_upload_brand_reference` | Attach a reference image (file or URL) with a `category` and `label` to a brand's library. |
| `studio_run_workflow` | Execute an inline workflow definition (`projectId`, `definition`, optional `params`). Returns `runId`. |
| `studio_get_run` | Poll a run: overall status plus per-node status and cost. A run parked on a person comes back with a `waiting` block instead of more polling (see below). |
| `studio_decide_judge` | Pass a PERSON'S approve/reject on to a parked judge node. Never your own judgement. |
| `studio_get_run_output` | Fresh signed URL for one node's result (`runId`, `nodeId`). |
| `studio_replace_character_in_video` | The packaged video recipe: scene frame plus character reference, swap in a still, animate it. Returns a `runId` to poll with `studio_get_run`. |
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

Preferred path: `studio_mint_character` with `{ projectId, name, slug, description, negativePrompt?, visibility?: "listed" | "unlisted", waitSeconds? (default 600) }`. It runs the sheet workflow, waits, creates the character and uploads each view under its category, then returns `{ slug, name, runId, referenceCount, references[{ nodeId, category, referenceId, url }], costUsd }`. Pass `visibility: "listed"` when the human should see the mint on the Studio's Workflows page.

Manual path (when you want to inspect views before freezing):

1. `studio_run_workflow` with the character-sheet definition (seed node: text-to-image on `fal/nano-banana-2`; six `image-edit` nodes on `fal/nano-banana-2-edit` whose `inputImages` reference the seed).
2. Review the seven URLs with the user. If the seed face is wrong, re-run; do not freeze views from a rejected seed.
3. `studio_create_character` `{ name, slug, descriptorPrompt, negativePrompt? }`.
4. Upload each approved view: `POST /api/characters/{slug}/references/upload` (multipart `file`, `category` in `face|three-quarter|profile|full-body|close-up|lighting-warm|lighting-cool`, `label`).

Wardrobe variants (workwear, evening wear): one ad-hoc `image-edit` node on the `full-body` reference with a prompt like "change ONLY the clothing to ..., keep face, body and pose identical". Upload the result as an extra `full-body` reference with a descriptive label.

Expect about $0.30 per mint (7 images).

## Brands and references

```
POST /api/brands                        { "name": "My Brand", "slug": "my-brand", "stylePrefix": "flat vector, warm palette", "context": "children's book publisher" }
POST /api/brands/{slug}/library/upload  multipart: file, category (mood|style|identity|...), label
```

Same via `studio_create_brand` and `studio_upload_brand_reference`. After that, pass `brandSlug` (and optionally `brandMode`) on any generation and the Studio applies the style and attaches the references. Keep a brand library small and on-style: five strong references beat thirty mixed ones.

## Video with a cast character: the recipe that works

Do NOT use video-to-video character swap (Wan-2.2 Animate Replace and the products that wrap it) on real footage that is dark, handheld, motion-blurred, or has hand-tool interaction. It warps faces and limbs; in testing every such shot was unusable. Use the still-first recipe instead:

1. **Swap the person in a STILL.** `image-edit` node on `fal/nano-banana-2-edit`, `inputImages: [scene_frame_url, character_reference_url]`, prompt: "replace the person with the person from the second image, keep everything else identical: framing, lighting, clothing fit, background".
2. **Animate the still.** `image-to-video` node with `inputImageUrl` bound to the edit node's output. `fal/seedance-pro-image-to-video` (about $0.62 per 5 s at 1080p) or `fal/kling-v2-5-image-to-video` ($0.35 base; supports start AND end keyframes, so swap first and last frame for longer shots to kill drift).
3. **Finish outside the Studio.** Conform fps, upscale 2x if needed, re-grain and grade (dark grading hides artifacts). Keep generated cuts at 4 s or less. Budget 2 to 3 takes per shot.

`studio_replace_character_in_video` wraps steps 1 and 2 and waits by default: `{ projectId, sceneFrameUrl, characterSlug (or characterReferenceUrl), endFrameUrl?, swapPrompt?, motionPrompt?, videoModel?, visibility?, waitSeconds? }` -> `{ runId, status, stillUrl, videoUrl, costUsd, videoModel }`. Without `endFrameUrl` it animates from the single swapped still with `fal/seedance-pro-image-to-video`; with `endFrameUrl` (a second, approved keyframe) it switches to `fal/kling-v2-5-image-to-video` and interpolates between both frames, which is the recommended path for shots longer than ~3 seconds: have the human approve the first and last swapped frames (`stillNodeId: "edit"`), then run the video node. Fetch the clip later with `studio_get_run_output` for node `video`.

Inline definition if you run it yourself with `studio_run_workflow`:

```json
{
  "nodes": [
    { "id": "edit", "task": "image-edit", "model": "fal/nano-banana-2-edit",
      "inputs": { "inputImages": { "kind": "literal", "value": ["<scene_frame_url>", "<character_full_body_url>"] },
                  "prompt": { "kind": "literal", "value": "replace the person with the person from the second image, keep everything else identical" } } },
    { "id": "video", "task": "image-to-video", "model": "fal/seedance-pro-image-to-video",
      "inputs": { "inputImageUrl": { "kind": "ref", "node": "edit", "path": "url" },
                  "prompt": { "kind": "literal", "value": "subtle natural motion, camera static" } } }
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
3. `studio_run_published` with the slug, `projectId` and `params` to run it.

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
