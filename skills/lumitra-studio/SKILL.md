---
name: lumitra-studio
description: Generate brand-consistent images and video through Lumitra Studio (studio.lumitra.co). Batch prompts to images, mint characters as 7-view identity sheets, create brands with reference images, replace a person in an image or video clip with a cast character (routed by mode, analyzed before any spend, honest about what the still-swap route cannot preserve), and run published recipes (a workflow plus automatic follow-up like character creation). Use when the user wants bulk image generation, a consistent recurring character, branded visuals, AI b-roll, a person replaced in a video clip, or to run a named recipe by slug. Works through the studio_* MCP tools or the HTTP API with LUMITRA_STUDIO_API_KEY.
license: MIT
compatibility: Needs LUMITRA_STUDIO_API_KEY in the environment. The MCP path needs Node 20+ (npx). The script path needs bash, curl and jq. All generation calls spend money on the key.
metadata:
  author: Lumitra
  version: "0.14.0"
  homepage: https://studio.lumitra.co
---

# Lumitra Studio

Lumitra Studio is a hosted generation service. You send prompts, and optionally a brand slug and a character slug; the Studio injects brand style and character references server-side, calls the image or video provider, stores the result and returns a signed URL plus what the job cost your organization, in USD. Nothing runs locally.

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

Never print the key, never paste it into a prompt, never commit it. A key belongs to one organization: everything it reads, creates and spends is that organization's, and no argument of any tool chooses another one. A `401` or `403` means the key is missing, invalid or revoked; stop and tell the user rather than retrying.

## What limits spending

Every generation is metered on the key's organization. Which limit applies depends on how the organization is set up, and `studio_get_usage` tells you which: its `credits` field is an object for an organization on prepaid credits and `null` for one held to a monthly cap.

- **Prepaid credits: every new organization** (and any the Lumitra operator moved onto credits). The organization has a credit balance and no monthly cap, unless the operator set one. A new organization can receive a one-time welcome credit of 15 USD. **An API key cannot collect it:** it is decided when an owner of the organization first opens Studio in a browser (https://studio.lumitra.co/app). Until then the balance is zero, every paid call is refused with `credits_exhausted`, and the refusal carries `welcomeCredit: "pending_owner_visit"` and says so: tell the user to have an owner of the organization open Studio once, then send the request again. At that visit the credit is granted once per person and while the operator's monthly budget for welcome credits lasts; an organization whose owner already received a welcome credit, or that is decided after the month's budget is used up, stays at a balance of zero, and the operator can grant credits by hand. Each finished generation is paid from the balance at Studio's price for it; an organization with a subscription pays lower prices on many models. The estimate before a run and the job's `costUsd` after it are that price. A daily limit applies on top: 10 USD a day to begin with, which an owner or admin of the organization can change on the Billing page (`/app/billing`), up to 50 USD a day. The welcome credit is larger than that first daily limit, so it cannot all be spent on one day unless the limit is raised: a `402` with the code `daily_cap_reached` while credits are still on the balance means the day is used up, not the credits. Only what was actually rendered is charged, and a failed job that produced no charge costs nothing.
- **A monthly cap: an organization the Studio already knew before prepaid credits became the start for new ones.** It keeps the cap it had: 20 USD a month when it never had a plan of its own, otherwise what the Lumitra operator set, which is the only way a cap can be unlimited. Using the Studio never moves such an organization onto credits.

What `studio_get_usage` returns: `usedUsd`, `realizedUsd`, `inFlightEstimatedUsd`, `jobs` and `byModel` for the calendar month, all in what the organization paid (for an organization on credits: what left and will leave its balance for the month's jobs); `capUsd` (the monthly cap of an organization that is not on credits, `null` for none and always `null` on credits) with `capSource` (`default` or `row`, an operator-set plan); `rpm` (a per-minute rate limit, `null` for none); and `credits`. For an organization on credits that is `{ balanceUsd, dailyLimitUsd, usedTodayUsd, dailyResetsAt, operatorMonthlyLimit }`: the prepaid balance, the daily limit (`null` when the operator removed it), what left the balance today with running jobs counted at their price, when the day's count starts again (midnight UTC), and whether the Lumitra operator set a monthly limit on top (its amount is not reported). Every amount this tool returns is in the same dollars as the balance. `balanceUsd` does not yet subtract what is reserved for requests that are still starting or running, so the room for a new request can be a little smaller than `balanceUsd`. `usedUsd` includes estimates of jobs still in flight and can go DOWN when one fails; that is not a bug.

A request that would go past a limit is refused before anything is charged, with a `402` whose `error` is a sentence written to be relayed to the user as is. The `studio_*` tools hand you that sentence unchanged, followed by the `code`:

| `code` | What happened | What helps |
|---|---|---|
| `credits_exhausted` | The balance does not cover this request. The body carries `balanceUsd`, `availableUsd`, `neededUsd`, `heldUsd` and `topUpPath`, and `welcomeCredit: "pending_owner_visit"` while the organization's welcome credit is not decided yet. | With `welcomeCredit: "pending_owner_visit"`: an owner of the organization has to open Studio in a browser once (https://studio.lumitra.co/app); the welcome credit is decided at that visit and an API key cannot collect it. Otherwise the sentence says to add credits on the Billing page. If buying credits is not open to the organization there yet, the Lumitra operator (hello@lumitra.co) grants them. When the sentence says part of the balance is only reserved for requests that are still starting, wait a few seconds and send the same request again. |
| `daily_cap_reached` | The daily limit is reached. The body carries `capUsd`, `usedUsd` and `resetsAt` (midnight UTC). | On credits, an owner or admin raises the limit on the Billing page, up to the ceiling the sentence names; otherwise wait for `resetsAt`. |
| `monthly_cap_reached` | The monthly cap is reached. The body carries `resetsAt`, and for an organization that is not on credits also `capUsd` and `usedUsd`. | Only the Lumitra operator (hello@lumitra.co) can raise it. Do not retry before `resetsAt`. |

A `429` means too many requests in a short time: either `code: "velocity_limit_reached"` (too many paid requests from one key within a minute; the sentence and `retryAfterSeconds` say how long to wait) or the organization's own per-minute rate limit. Both carry a `Retry-After` header; do not resubmit before it has passed.

## First five minutes

A new organization starts empty. These three steps take it to one finished image and a known cost. They are the same three the Home dashboard at studio.lumitra.co walks a person through, so an agent and a person arrive at the same place. Before the first step, call `studio_list_projects` once: it proves the key works and lists the organization's projects (for a new organization that is usually one, slug `default`).

1. **Set up a brand, or skip.** A brand (a style prefix plus reference images) is optional, and creating one is free. To skip it, go straight to step 2 and leave `brandSlug` out: `studio_generate_image` with only a `prompt` makes an image without a brand, and so does `POST /api/generate` over HTTP. To use one, create it first with `studio_create_brand` (a `name` and a `slug` are enough; add a `stylePrefix` when the user has a style in mind). Never invent a brand slug to fill the field: a `brandSlug` that names no brand of the organization is refused with `404` and `code: "input_not_found"`, and the refusal's text says to create the brand or leave `brandSlug` out.
2. **Make one image.** Call `studio_generate_image` with a `prompt`, plus the `brandSlug` from step 1 if you created a brand. This is the first call that spends money. It waits by default and returns the signed image `url` and `costUsd`; with `wait: false` it returns a `jobId` to poll with `studio_get_job`. The HTTP call behaves like `wait: false`: it answers `{ "jobId", "kind", "candidates" }` and the image arrives by polling `GET /api/v1/jobs/{jobId}`. If the job ends `failed`, report its `errorMessage` and retry at most once. A failed job normally adds nothing to the organization's spend; trust its `costUsd` over that rule, because a job that fails after an earlier attempt of it succeeded keeps that attempt's cost, and the spend ledger counts it.
3. **See what it cost.** Tell the user the job's `costUsd`: that is what the job cost the organization. Then call `studio_get_usage`. For an organization on prepaid credits, `credits.balanceUsd` is what is left of the balance and `credits.usedTodayUsd` what left it today; the balance fell by the job's `costUsd`. For an organization on a monthly cap, `capUsd` minus `usedUsd` is the room left this month. `studio_get_spend` shows the totals of what was paid: the same ledger a person sees in the wallet at the top of every Studio page.

Where the first image lands, in this order: in the project you named with `projectId`, when you passed one (it must be a project of the organization, from `studio_list_projects`; any other id is a `404`); otherwise, when you passed a `brandSlug`, in the project whose slug equals the brand slug, which the Studio creates on first use; otherwise in the project `default`. So an image made without a brand and without a `projectId` is in `default`, and one made with a brand is in a project named after the brand: call `studio_list_projects` again to see it. Spend is counted for the whole organization whichever project a job is in.

Stop there and ask what to make next. Minting a character, a batch or any video costs more, and each of those has its own section below.

## Concepts

| Term | What it is |
|---|---|
| **Project** | Top-level container. Every asset, character and run belongs to one. `studio_list_projects` gives ids; most accounts have one "default" project. |
| **Job** | One provider call (one image, one video, one edit). Has `status` (`queued`, `running`, `succeeded`, `failed`, `canceled`), `costUsd`, `model`, and on success a `resultAsset.url` (signed, re-signed on every read, so it stays fetchable). |
| **Brand** | A slug plus a style prefix, context text and a library of reference images. Optional: passing `brandSlug` makes the Studio prepend the style and attach the references to that generation, and leaving it out generates without a brand. A slug is unique within one organization, and one that names no brand of yours is refused (`404`, `input_not_found`), never silently ignored. |
| **Character** | A slug plus a descriptor prompt and a set of frozen reference images by **category**. Passing a character makes the Studio pin identity to those references. You can use the characters your organization owns and the ones another organization shared with everyone (`owned: false`): a shared character can be read and cast in generations but not edited, and its reference images come as Studio addresses, not permanent image URLs (see the tool table). A `characterSlug` you cannot use is refused the same way as an unknown brand. |
| **Workflow** | A small graph of nodes (`generate-image`, `image-edit`, `image-to-video`, ...). Each node becomes a Job. Runs return per-node result URLs. This is how multi-step recipes (swap then animate) execute server-side. |
| **Published recipe** | A workflow frozen under a stable public slug, optionally with a declared list of post-run effects (create a character, attach a reference). Run it by slug with `studio_run_published`; the effects fire automatically only if every node succeeds. See "Published recipes" below. |
| **Spend** | A ledger of every Job's `costUsd`, which is what the job cost the organization. `studio_get_spend` reads it; for an organization on prepaid credits its totals are what left the balance. |
| **Credits / plan / usage** | What limits the organization: a prepaid credit balance with a daily limit (every new organization, with a 15 USD welcome credit once an owner has opened Studio and one is granted, see "What limits spending", and paying Studio's price for each generation), or a monthly USD cap (an organization from before prepaid credits: 20 USD unless the Lumitra operator set a plan), plus an optional per-minute rate limit. A generation call is refused with `402` or `429` when one is hit (see "What limits spending" above). `studio_get_usage` reads the current state. |

## MCP tools and when to use each

| Tool | Use it to |
|---|---|
| `studio_list_projects` | Resolve the `projectId` you need for characters, workflows and runs. Call once, cache the id. |
| `studio_generate_image` | One prompt to one image job. Args: `prompt` (the only required one), optional `brandSlug` (a brand of the organization, or leave it out for an image without a brand), `brandMode`, `characterSlug`, `mentions` (several characters, products and locations of the organization in one image, see below), `projectId` (where the image is filed), `aspectRatio`, `model`, `imageSize`, `seed`, `candidateCount`, `wait`. Waits by default and returns `jobId`, `url`, `urls`, `costUsd` and `candidates: { requested, rendered, mayRender? }`; with `wait: false` it returns the `jobId` at once. Some models render one image whatever `candidateCount` asks for: the result then also carries a `notice` saying how many will be made and why, which you pass on to the user. Only rendered images are charged. |
| `studio_generate_3d` | One prompt, or one image (`imageUrl`), to one 3D model (a textured GLB mesh) through 3D AI Studio. Optional `model` (text: Tripo 3.1, Hunyuan Rapid or Pro; image: TRELLIS.2, Tripo 3.1), `options` quality flags that each change the price, `projectId`. Waits by default (one to five minutes) and returns the GLB `url` and `costUsd` (what the model cost the organization; the quality flags decide it). |
| `studio_rig_3d` | Rig a humanoid Model3D and animate it (Meshy on fal): `projectId`, `meshAssetId` (the `assetId` `studio_generate_3d` returns), up to 10 `animations` as preset names or ids, optional `heightMeters`. Walk and run clips always come with the rig. Waits by default (one to three minutes) and returns `rigUrl`, `clips` (name and url each) and `costUsd` (a price per rig plus a price per preset you ask for). Humanoids only. |
| `studio_find_animations` | Search the 678 Meshy presets `studio_rig_3d` can apply by words ("sword slash", "dance"). Free and local. |
| `studio_get_job` | Poll a `jobId` until terminal. Returns status, `costUsd`, `errorMessage`, `resultAsset.url`. |
| `studio_list_characters` / `studio_get_character` | Find a character you can use and its reference images (you need the `full-body` or `face` one for video swaps). The list holds the organization's own characters and the ones another organization shared with everyone, marked `owned: false`; when both use the same slug, yours is the one listed and used. A shared character is readable and castable, never editable (an upload, edit or delete answers `403`). For a character you own, a reference `url` is a direct image URL. For a shared one it is a Studio address: pass it unchanged as an image input to any Studio tool and the Studio resolves it when the job runs, but it is not a public image URL, and it stops working the moment the owner stops sharing. |
| `studio_prompt_enhance` | Rewrite a short prompt into a richer one before you generate: subject, setting, light, lens and composition (for `target: "video"` also the camera movement and the action over the shot), in the prompt's own language, without changing what it asks for. Args: `prompt`, `target` (`image`, the default, or `video`), optional `mentions`, `model` (the image or video model you will render with), `brandSlug`, `brandMode`. A character, product or location goes into the prompt as a token, `@[character:<slug>]`, `@[product:<slug>]` or `@[location:<slug>]`, and every token must also be listed in `mentions` as `{ kind, id: <slug> }`; the answer `{ prompt, mentions }` keeps each token exactly once, so pass both on unchanged. Free: nothing is charged and no job is created. Limited per API key over a few minutes and per organization per day; past either it answers `429` with a sentence saying when to try again: wait that long, never loop. It generates nothing; call `studio_generate_image` with the result. |
| `studio_create_character` | Register a character row: `name`, `slug`, `descriptorPrompt`, `likenessRightsConfirmed: true` (see "The likeness confirmation"), optional `negativePrompt`, `defaultModel`. Does not generate images. |
| `studio_mint_character` | Run the 7-view identity sheet for a description and freeze the views as references on the character. The one-call path for "make me a consistent character". Needs `likenessRightsConfirmed: true`, and refuses before spending anything without it. |
| `studio_create_brand` | Register a brand: `name`, `slug`, optional `stylePrefix`, `context`. |
| `studio_upload_brand_reference` | Attach a reference image (file or URL) with a `category` and `label` to a brand's library. |
| `studio_run_workflow` | Execute an inline workflow definition (`projectId`, `definition`, optional `params`). Returns `runId`. |
| `studio_get_run` | Poll a run: overall status plus per-node status and cost. A run parked on a person comes back with a `waiting` block instead of more polling (see below). |
| `studio_decide_judge` | Pass a PERSON'S approve/reject on to a parked judge node. Never your own judgement. |
| `studio_get_run_output` | Fresh signed URL for one node's result (`runId`, `nodeId`). |
| `studio_replace_character_in_video` | The packaged video route: scene frame plus character reference, swap in a still, animate it. Pass an explicit `swapPrompt` (see "Character replacement"). Returns a `runId` to poll with `studio_get_run`. |
| `studio_get_spend` | Report what a session or time window cost the organization. Call it at the end of any batch and tell the user the number. |
| `studio_get_usage` | Check what limits the organization before a large batch, or after a `402`/`429` to see what tripped: the credit balance and daily limit (`credits`) for an organization on prepaid credits, the monthly cap (`capUsd`) otherwise, plus the per-minute rate limit and month-to-date spend. See "What limits spending" for every field. `usedUsd` includes in-flight (not yet settled) job estimates and can go DOWN as well as up when one fails, this is not a bug. |
| `studio_workflow_describe` | Learn the node vocabulary before authoring: task types with ports and prompt policy, input types, op types, patch limits. Add `includeModels: true` to pick a model id. |
| `studio_workflow_get` | Read a saved workflow as a summary (nodes, wires, `revision`, `projection`); `full: true` for the whole document. |
| `studio_workflow_create` | Build a new saved workflow from ops. Returns `savedId`, `revision` and the `idempotencyKey` to retry with (a retry with it returns the first workflow, never a second). Free. |
| `studio_workflow_apply` | Change a saved workflow atomically on top of `baseRevision`. Every refusal is a `{ ok: false, code, hint }` result to act on, not an error. Free. |
| `studio_workflow_validate` | Dry-run a document or saved workflow with ops and run params before spending anything. |
| `studio_workflow_screenshot` | Render a saved workflow as a labelled-box-and-wire diagram, the Figma `get_screenshot` equivalent. A diagnostic (is this wired the way I meant), not a pixel-exact preview. `{ savedId }` -> `{ url, width, height }`. Free. |
| `studio_list_published` | List every published recipe (`slug`, `label`, `hasEffects`). Call this before `studio_run_published` if you don't already know the slug. Free. |
| `studio_describe_published` | Read one recipe's frozen definition by slug, so you know what params it needs before running it. Free. |
| `studio_run_published` | Run a published recipe by slug. `{ slug }` -> `{ runId }`, effects fire automatically on a fully successful run. |
| `studio_create_project` | Create a project (`name` only; the slug is derived). A project keeps saved workflows, runs, assets and chats together; characters, products, locations, brands and campaigns are shared by every project. |
| `studio_rename_project` | Rename a project (`projectId`, `name`). The default project keeps its slug `default`. |
| `studio_delete_project` | Delete a project for everyone with its workflows, runs, assets and chats (needs a key with the admin role). The person confirms it in the chat, see "Deleting needs the person's yes". Refused for the default project and while work is running in the project. |
| `studio_delete_asset` | Delete one asset (image, video, rendered slide or reel) for everyone with its stored file (needs a key with the admin role). The person confirms it in the chat, see "Deleting needs the person's yes". Refused while a post, a saved workflow, a published recipe or work in flight still uses it: it then returns `usedIn` with each place (label, where, link) and deletes nothing; tell the person, and delete again once it is removed there. Campaign shots, sent posts and past runs keep their record without it. |
| `studio_list_workflows` | List the saved workflows of a project (`savedId`, `label`, `version`); omit `projectId` for the default project. |
| `studio_move_workflow` | Move a saved workflow to another project of the organization with its runs and results (`savedId`, `toProjectId`, `projectId` when it is not in the default project). Nothing is regenerated; move it back to undo. |
| `studio_list_campaigns` | List the organization's campaigns (`id`, `name`, shot count). |
| `studio_brand_kit_get` | A brand's kit: the only colours (by id), sizes (headline, body), fonts (primary, secondary, with their weights and styles) and logos (light, dark) a post may use. `{ brandSlug }`. Free. |
| `studio_composition_describe` | The post vocabulary: op types, slide, clip and overlay shapes, aspects and Instagram's limits. No request. Free. |
| `studio_composition_list` | A project's carousels and reels, newest first (`projectId` optional). Free. |
| `studio_composition_create` | Start a carousel or reel for a brand, optionally with its first ops (one call can build a whole carousel). `{ kind, brandSlug, projectId?, aspect?, label?, ops? }` -> `{ ok: true, composition }`. Free. |
| `studio_composition_get` | Read a post: items, overlays and the `revision` to build the next patch on. Free. |
| `studio_composition_apply` | Change a post atomically on `baseRevision`; refusals are `{ ok: false, code, hint }` results (`stale_revision`, `invalid_patch` with `not_in_kit` or `invalid_asset`, `idempotency_mismatch`, `network_error`). Free. |
| `studio_composition_render` | Render it: a carousel to JPEG slides, a reel to an H.264 MP4. Waits and returns the asset URLs, or `not_ready` with every reason to fix first. Free (Studio's own server). |
| `studio_social_list_projects` | The company's Lumitra Social projects (one Instagram account each) and the one this brand went to last. Free. |
| `studio_composition_send_to_social` | Send the rendered post to Lumitra Social as a draft or scheduled post. Creates a post the planner will publish: confirm project, caption and time with the user first. |
| `studio_delete_campaign` | Delete a campaign with its shot list and decisions; its images stay in the asset library. The person confirms it in the chat, see "Deleting needs the person's yes". Refused while a shot is still rendering. |

### Deleting needs the person's yes

`studio_delete_project`, `studio_delete_asset` and `studio_delete_campaign` never delete on your word alone. The tool reads what would be removed and asks the person through your client's confirmation dialog; on a yes it deletes, on a no it returns `declined: true` and nothing happens. If your client has no such dialog, the tool returns `confirmationRequired: true` with a `summary` and a `confirmationToken` and deletes nothing. Then show the `summary` to the person exactly as written, ask them to confirm in the chat, and only after they explicitly say yes call the same tool again with the `confirmationToken`. Never confirm on their behalf, never ask for a yes before you have shown the summary, and never reuse a token: it works once, expires after ten minutes, and stops working if the project or campaign changed since it was issued (you then get a fresh summary to show).

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

Flags: `--brand <slug>` (optional; without it you get an unbranded image; a slug that names no brand of the organization fails every submit with the Studio's refusal printed), `--mode <mode>`, `--aspect <ratio>` (default `1:1`), `--model <id>`, `--out <dir>` (download PNGs), `--budget <sec>` (poll budget, default 600). Exit code is non-zero if any job failed or timed out, so a pipeline can gate on it.

HTTP contract behind both:

```
POST {base}/api/generate
{ "brandSlug": "my-brand", "brandMode": "illustration", "prompt": "a happy red dinosaur waving",
  "settings": { "aspectRatio": "1:1", "model": "kie/nano-banana-2" } }
-> 200 { "jobId": "<uuid>", "kind": "generate_image", "candidates": { "requested": 1, "rendered": 1 } }
-> 404 { "error": "Brand 'my-brand' not found. Create the brand first (...), or leave brandSlug out to generate without a brand.",
         "code": "input_not_found", "input": "brandSlug" }

GET {base}/api/v1/jobs/{jobId}
-> { "job": { "status": "succeeded", "costUsd": 0.064, "model": "kie/nano-banana-2", "errorMessage": null },
     "resultAsset": { "url": "https://...signed...png" } }
```

`brandSlug`, `brandMode`, `characterSlug` and `projectId` are all optional in the body; only `prompt` is needed. `settings` also accepts `imageSize`, `candidateCount`, `seed`, `temperature`. `model` is optional; the Studio picks its default text-to-image model when omitted.

`candidateCount` (1 to 4) asks for several candidates of one prompt, but not every model takes a count: most KIE image models render one image whatever is asked, a `route/...` model runs on KIE first and so usually renders one too (its fal fallback may render up to four), and fal models render at most four. The submit answer always says what will happen in `candidates: { requested, rendered, mayRender? }`, and adds a `notice` sentence when fewer images will be made than were asked for. Relay that notice instead of promising the count you sent, and for more candidates send the request again or pick a model that takes a count. Only rendered images are charged.

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

Expect about $0.84 per mint (7 images at about $0.12 each) for an organization on prepaid credits without a subscription; a run's estimate says the exact figure before anything is spent.

## Brands and references

```
POST /api/brands                        { "name": "My Brand", "slug": "my-brand", "stylePrefix": "flat vector, warm palette", "context": "children's book publisher" }
POST /api/brands/{slug}/library/upload  multipart: file, category (mood|style|identity|...), label
```

Same via `studio_create_brand` and `studio_upload_brand_reference`. After that, pass `brandSlug` (and optionally `brandMode`) on any generation and the Studio applies the style and attaches the references. A brand belongs to the organization that created it: its slug only resolves for that organization's keys, and another organization may use the same slug for a brand of its own. Keep a brand library small and on-style: five strong references beat thirty mixed ones.

## Several characters, products and locations in one image (mentions)

`studio_generate_image` (and `POST /api/generate`) takes `mentions`: the organization's characters, products and locations to put in the image, in the order the prompt names them, each by its slug.

```json
{ "prompt": "Ana wearing the Charcoal Coat at Chalet Alpine, golden hour",
  "mentions": [ { "kind": "character", "id": "ana" }, { "kind": "product", "id": "coat" }, { "kind": "location", "id": "chalet" } ],
  "model": "fal/nano-banana-2-edit" }
```

- The Studio sends each mention's reference images in that order (a character's face and full body, a product's main photo and spare detail views, a location's photos), tells the model in the prompt which image is which, and puts each character's locked description in. Write the names in the prompt the way they are listed; the composer's tokens (`@[character:ana]`) work too and are replaced by the names.
- Every mention needs at least one reference slot, and attached images keep theirs. Nano Banana 2 Edit and the default (no `model` named) take 8, Seedream Edit 10; a text-only model takes none. With mentions and a `candidateCount` above 1 and no `model`, the Studio uses `fal/nano-banana-2-edit`, which takes 8 and renders up to 4. Too many is refused before anything is spent (`400`, `code: "too_many_references"`): remove a mention or pick a model that takes more. A model that cannot take references at all (the Vertex entries) is `400` `model_takes_no_references`. A mention without any reference image is `422` `mention_without_reference`; a slug the organization cannot use is `404` `input_not_found`.
- References change no price: the image costs what it costs without them.
- `characterSlug` still works alone and as before; sent together with `mentions`, that character comes first.
- Each image keeps its recipe: `metadata.recipe` on the asset holds the prompt as sent, the mentions and the settings, so the same image can be made again. Over HTTP, `GET /api/v1/jobs/{jobId}` and `GET /api/v1/projects/{projectId}/assets` return it with the asset.

## Character replacement (images and video)

Goal: the result should look as though the original camera recorded the replacement character doing the original action. Prompt prose cannot guarantee that; the steps below make the constraints explicit and route each one to the stage that can actually enforce it. Load `references/character-replacement.md` for the full tables, the analysis record shape, the prompt templates and the review checks.

1. **Pick the mode first.** Source-matched replacement (change the person, keep everything else), creative restyling (deliberately change the look), or new scene generation (nothing to preserve). Realism vocabulary like haze, grain, visible pores or a mood palette belongs to the last two, and only where it fits; it is not a default for a replacement.
2. **Declare the scope and who owns each attribute.** Identity comes from the character references. Pose, expression, gaze, timing, lighting, focus, motion blur, camera, background and other people come from the footage. Clothing and props come from the footage unless the user assigns them to a reference. Body proportions follow the declared scope: identity-only keeps the source body; full-body takes the character's, which changes the silhouette, so the background behind the old body must be reconstructed and every contact point re-derived. When the request does not say which, ask before spending anything.
3. **Analyze before generating.** Sample the whole shot, not just its first and last frame: add frames at head turns, occlusions, hand contacts, lighting changes and focus pulls. Record observations separately from guesses, leave unknowns unknown, and never invent camera numbers (a single frame does not reveal aperture or focus distance; "stops out of focus" is not a unit). Give each constraint an owner: prompt, model control, a follow-up edit, or human review.
4. **Say honestly what the route can do.** Studio has no source-video editor today (a model that edits the original clip and keeps its real motion). The route it has is a still swap then image-to-video, which REGENERATES the motion between the frames rather than preserving it. When the original performance must survive exactly, tell the user this route cannot guarantee it before spending.
   - Swap the person in a still: `image-edit` on `fal/nano-banana-2-edit`, `inputImages: [scene_frame_url, character_reference_url]`.
   - Animate: `image-to-video`. `fal/kling-v2-5-image-to-video` takes a start and an end frame (swap both for shots longer than about 3 seconds to limit drift); the FLUX.3 keyframes tier pins up to ten swapped frames, which constrains the regenerated motion more tightly but still does not preserve it.
   - Do NOT use video-to-video character swap through Wan 2.2 Animate Replace (and the products that wrap it) on dark, handheld, motion-blurred footage or footage with hand-tool contact: it warped faces and limbs on every such shot tested.
5. **Write a short, specific prompt.** The requested change and exact target first, each reference's role, then the few preservation constraints most likely to fail in this shot, as concrete relationships ("keep the open door in front of his body; match the face's original softness"). Never append a realism suffix ("photorealistic, ultra-detailed, no artifacts"), and never promise physics in prose ("keep every pixel identical"): the model cannot guarantee it, and "tack-sharp" is exactly how a deliberately defocused subject comes back wrong.
6. **Inspect each keyframe and the pair before paying for video.** Check identity, pose, accessories, focus, lighting and edges on the swapped still first. Budget one candidate plus two retries per shot, retrying from the source rather than re-editing a degraded output, and classify each failure before retrying (identity, pose, focus, edge), and fix it with a better prompt or another run of the edit. Then check the pair: a start and an end frame must show the same people and the same objects in their hands, and nothing the camera move cannot bring in: a person or tool in one frame and not the other is invented or erased by the video model mid-clip. Before the edits, list for each frame who is in it and what each person holds; name the held objects in the edit prompt, because a whole-person edit redraws the hands and drops or swaps what they hold. After the edits, compare the two frames with crops of the hands and faces at full resolution, and fix a mismatch with a follow-up edit before any video runs.
7. **Keep every keyframe a Studio edit, never a local composite.** The keyframe is the output of an edit node on the canvas, wired to the frame and references it came from, so anyone can see what made it. Never cut a person out, scale, mirror or paste them onto the original frame with a local script: it clipped heads above its cutout box, mis-scaled people and left keyframes nobody could trace, and was dropped for good on 2026-10-20. Two people in one frame: a second edit takes the first edit's output as its input and replaces the other person. A wrong walking direction or size is a reason to re-run the edit, not to paste. In the edit afterwards, conform the frame rate, keep generated cuts at 4 seconds or less, and do not add a film look to clean digital footage.

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
2. `studio_workflow_create` with ops: `addNode` for each node (an `input` node is a declared run parameter; `task` nodes carry `task`, `model`, `prompt`), `connect` for each wire (`source`, `target`, `port`). Pick your own node ids. Check `summary.projection`: `ok: false` lists why it cannot run yet (`no_model`, `prompt_required`, ...). If the create comes back as `network_error` or `server_error`, retry it with the `idempotencyKey` that result returned and the same label and ops: the first workflow comes back (`replayed: true`, at its current `revision`) instead of a second one. `idempotency_mismatch` means that key already made a different workflow: send a new one.
3. `studio_workflow_apply` to change it: pass the `revision` you last saw as `baseRevision`. Every refusal comes back as `{ ok: false, code, hint }`, so read the `code` and do what it says: `stale_revision` (someone else changed it: read the returned `summary`, rebase your ops, apply again on the new revision), `invalid_patch` (`error.opIndex` names the offending op), `forbidden` (`missingScope` names what your key lacks), `not_editable` (this workflow cannot be patched at all: it is still runnable, build a new one instead), `lossy_import` (read `notes`, then resend the same ops with `acknowledgeLossy: true` and a NEW `idempotencyKey`), `idempotency_mismatch` (that key was used for different ops: send a fresh one). On `network_error` or `server_error`, retry with the SAME `idempotencyKey` the result carries, never with a fresh one; `replayed: true` in a success result means the earlier attempt had already landed.

   A workflow the canvas cannot represent is served read-only: `studio_workflow_get` returns `readOnly: true` with no nodes, and only `studio_run_workflow` works on it. One flagged `needsLossyAcknowledgement: true` needs the `acknowledgeLossy` confirmation on its first patch.
4. `studio_workflow_validate` with `savedId` and the run `params` before running: missing required inputs and unknown params surface here, at no cost.
5. `studio_run_workflow` with `projectId`, `savedId` and `params`.

Never rebuild a workflow from scratch to change one thing: read it, apply the ops that change that thing.

## Carousels and reels (Posts)

A post is a carousel (up to 10 slides of the project's images) or a reel (the project's clips, 3 to 90 s) with text, logo and shape overlays that can only use the brand's kit. The Posts editor in Studio and these tools edit the same document. Editing and rendering are free.

1. `studio_brand_kit_get` for the brand: overlays name its colour ids, `headline`/`body`, `primary`/`secondary` and the weights each font has. There is no field for a hex colour, a font name or a pixel size.
2. `studio_composition_describe` once for the shapes and limits (up to 10 slides; a reel of up to 30 clips and 40 overlays in all), then `studio_list_assets` with the `projectId` (`subtype: Image` for slide backgrounds, `Video` for clips) for the asset ids, then `studio_composition_create` with `kind`, `brandSlug`, `projectId` and the ops: `addItem` per slide (`background.assetId` is an image asset of the project) or per clip (a video asset, `trimIn`/`trimOut` in seconds), `addOverlay` per text, logo or shape (`target` is the item id, or `"reel"` across a whole reel). Boxes are fractions of the frame; keep text inside the safe area (on a reel, out of the top 14% and bottom 20%).
3. `studio_composition_apply` to change it, on the `revision` you last saw, with the same refusal codes as workflows.
4. `studio_composition_render`: on `not_ready`, fix every listed reason and render again. An identical render is reused. One reel renders at a time per company: on `render_busy`, wait for the job it names, then render again.
5. To schedule it: `studio_social_list_projects`, then `studio_composition_send_to_social` with the `projectSlug`, caption, hashtags and `scheduledAt` (or none for a draft the user schedules in the planner). Confirm all of it with the user first: the planner publishes to Instagram at that time. A reel goes as a reel, a single slide as a feed image, and 2 to 10 slides as an Instagram carousel. On `not_connected` or `link_broken`, a company owner or admin has to connect Lumitra Social once in Studio (Posts editor, Send to Social) with a company API key; you cannot do that for them. On `social_unavailable`, retry with the same `idempotencyKey`.

If a create comes back as `network_error` or `server_error`, retry it with the `idempotencyKey` that result returned: the first post comes back instead of a second one.

## Published recipes

A recipe is a workflow published under a stable public slug (done through the HTTP API or on the canvas, not yet an MCP tool): its document and an optional declared list of post-run effects (create a character, attach a reference, create a brand) are frozen together at publish time.

1. `studio_list_published` to see what exists (or ask the user for the slug directly).
2. `studio_describe_published` with the slug to see the frozen definition and its params.
3. `studio_run_published` with the slug, `projectId` and `params` to run it. A recipe that creates a character also needs `likenessRightsConfirmed: true` (the same confirmation, asked of the human the same way); without it the run is refused with `likeness_rights_confirmation_required` before anything is spent.

Running a recipe always executes the FROZEN definition, never the live authoring document, which may have moved on since publish. If every node in the run succeeds, the declared effects fire automatically and exactly once; a failed, partial or still-parked run never triggers them, so a broken run can never leave a half-created character, and a recipe whose graph contains a judge node creates nothing until the person has approved it. `studio_mint_character` and `studio_replace_character_in_video` are today still hand-written tools, not recipes, so both patterns currently coexist.

## Spend confirmation

A run whose estimated cost meets or exceeds $10 needs explicit confirmation: without it, `studio_run_workflow` / `studio_run_published` refuse with `confirmation_required` and no run is created, nothing is spent. Re-send the SAME request with `confirm: true` to proceed. This is a hard stop, not a warning: always tell the user the estimate and get a go-ahead before adding `confirm: true` yourself, the same rule the "Cost expectations" section below already asks for on any batch over 20 images.

## Character references on a clip (holding identity)

A clip made from one start keyframe drifts: the video model sees only the first frame, so a face and hair slowly change over four seconds. Kling O3 (`route/kling-o3`, or pinned `kie/kling-o3-image-to-video`; the fal fallback is `fal/kling-o3-pro-reference-to-video`) also takes **character references**: several photos of each person in the shot, which it holds the identity to for the whole clip. A minted character's frozen views (front, three-quarter, back, full body) are exactly that.

- On a workflow, wire each photo into the image-to-video node's `reference` port (op `{ type: "connect", source, target, port: "reference" }`), in order, each character's **frontal view first**. References never count as the start or end frame: those stay on the `image` port.
- 2 to 4 photos per character, up to 3 characters (fal: 7 photos in all). With more than one character, say which one each photo shows: `{ type: "setNodeSetting", id, key: "referenceElements", value: { "<sourceNodeId>": 2 } }` (a photo not named is character 1).
- A model without the capability refuses reference wires; the run refuses a character with one photo or too many, before anything is spent. References do not change the clip's price; the run's estimate shows it as usual.
- The prompt names the references as `@Element1`, `@Element2`; a prompt that does not gets one sentence in front tying them to the people in the start frame.
- To compare, `kie/gemini-omni-flash-1-1-reference-to-video` (Gemini Omni 1.1 Flash in its reference mode) takes the same wiring with 1 to 6 character photos in all and no end frame. KIE does not lock the first frame in this mode: the start frame goes in as reference image 1 and the prompt names it the exact scene and first frame, so the clip follows it closely but may not start on it pixel for pixel. Use Kling O3 when the first frame must be exact.
- Inline definitions (studio_run_workflow with a DAG) take `referenceImageUrls` plus `referenceElementIndexes` (the 0-based character of each photo, ascending, e.g. `[0, 0, 0, 1, 1]`).

## Continuity check before a clip with a start and an end frame

An image-to-video model given a start frame and an end frame that disagree invents or erases the difference in the middle of the clip (a bystander vanishes, a tool appears from nothing). So before a run executes an image-to-video node with BOTH `inputImageUrl` (start frame) and `endImageUrl` (end frame), the Studio compares the two frames with a vision model: one small paid check per new pair of frames, remembered for your organization, so an unchanged pair is never charged twice. It comes after the spend confirmation above.

- Frames that disagree: `studio_run_workflow` / `studio_run_published` refuse with `continuity_mismatch` and `nodes: [{ nodeId, differences }]`. No run is created and nothing is spent on the clip. Show the person the differences as written. The fix is in the frames (a corrected edit of the start or end keyframe, so both show the same people and the same objects in their hands), not in the clip's prompt.
- The check could not run (a frame that is not stored in Studio, a provider error, a timeout): they refuse with `continuity_unchecked` and `nodes: [{ nodeId, reason }]`.
- Either way, re-send the SAME request with `acknowledgeContinuity: true` to run anyway, and only when the person decided to. A pair that was run anyway is not asked about again.
- A frame made by a node of the same run (a keyframe and its clip in one run) cannot be compared before the run starts: the clip is checked when it becomes ready, and if the frames disagree the clip node fails with `continuity_mismatch` in its error, before anything is spent on it. Run the clip again on its own to see the differences and decide. `studio_replace_character_in_video` with an `endFrameUrl` is such a run (the swapped still is the start frame): when its video node fails with `continuity_mismatch`, show the differences, and call it again with `acknowledgeContinuity: true` only when the person decides to run anyway.

## Cost expectations

| Operation | Typical cost |
|---|---|
| Enhance a prompt (`studio_prompt_enhance`) | free |
| One image (the default model) | about $0.06, and up to $0.18 when the default route falls back to its second provider; about 40 s |
| Character mint (7 views) | about $0.84 |
| Still swap (one edit) | about $0.12 |
| 5 s image-to-video | about $0.53 (Kling 2.5) to $0.93 (Seedance) |
| One video shot, one take (swap plus animate) | about $1.05 |

These are Studio's prices for an organization on prepaid credits without a subscription, as of October 2026; a subscription lowers many of them, and an organization on a monthly cap arranged with the Lumitra operator has its own amounts. Never quote a figure from this table as what something cost: every job reports its real `costUsd`, which is what the job cost the organization, and for an organization on prepaid credits exactly what left its balance. Sum the `costUsd` values, and always tell the user the total at the end of a batch. Before a batch larger than 20 images or any video work, state the estimate and get a go-ahead.

## Failure handling

- Job `failed`: read `errorMessage`, report it, do not auto-retry more than once.
- Poll budget exhausted: report which jobs are still pending with their ids; they keep running server-side and can be read later with `studio_get_job`.
- `401`/`403`: key problem, stop.
- `404` with `code: "input_not_found"`: a `brandSlug` or `characterSlug` named something the organization cannot use. Nothing was spent. Do what the text says (create it, pick one from `studio_list_characters`, or leave `brandSlug` out); do not retry the same request unchanged.
- `402`: a spending limit refused the request before anything was charged. Relay the sentence and see "What limits spending" for the three codes.
- `429`: rate limit hit, see the response's `Retry-After` header (seconds) for when to resume polling; do not resubmit before then.
- A workflow run where one node fails leaves the others intact; read the successful nodes' outputs before deciding to re-run.

## Streamable HTTP instead of stdio

If your client prefers a network MCP endpoint, start the server yourself:

```bash
LUMITRA_STUDIO_API_KEY=... npx -y @marlinjai/studio-mcp --http --port 3939
```

and point the client at `http://127.0.0.1:3939/mcp` with transport `streamable-http`. Tool names and behaviour are identical.
