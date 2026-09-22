# Lumitra Studio Agent Plugin

An [Agent Plugin](https://agent-plugins.org/) (v1.0.0) that gives any compatible AI agent client access to [Lumitra Studio](https://studio.lumitra.co): brand-consistent image generation, character minting (7-view identity sheets), brand reference libraries, the still-swap plus image-to-video recipe for putting a cast character into footage, authoring workflows through the command model, and running published recipes (a workflow plus automatic follow-up like character creation).

It ships three components, discovered at the fixed locations the spec defines:

| Component | Path | What it does |
|---|---|---|
| Skill `lumitra-studio` | `skills/lumitra-studio/SKILL.md` | Teaches the agent the Studio concepts, the API contract, the minting and video recipes, cost expectations, and when to use each MCP tool. Includes `scripts/batch-generate.sh`. |
| Skill `video-motion-analysis` | `skills/video-motion-analysis/SKILL.md` | Reads the real motion of reference footage and verifies a generated clip against it, so a swap lands with the right framing and movement rather than by eye. |
| MCP server `lumitra-studio` | `mcp.json`, `.mcp.json` | Runs `@marlinjai/studio-mcp` over stdio and exposes the 25 `studio_*` tools (projects, generate, jobs, characters, brands, workflow authoring and runs, judge decisions, published recipes, spend and usage). |

## Pricing

The plugin is free. Generations are metered on your own Studio API key at provider cost (roughly $0.04 per image, $0.30 per character mint, $0.35 to $0.62 per 5 s video clip; the exact `costUsd` comes back on every job). Nothing in the plugin spends money until a tool or script is actually invoked.

## Prerequisites

- A Lumitra Studio account and an API key. Keys are self-serve and tenant-scoped, issued by [auth-brain](https://auth.lumitra.co) (Studio's identity provider), not by Studio itself: sign in at auth.lumitra.co, open your organization, and create a key under API Keys. Your organization also needs the `studio` app grant, which the Lumitra team enables during onboarding.
- Node.js 20+ (the MCP server is started with `npx -y @marlinjai/studio-mcp`).
- For the batch script only: `bash`, `curl`, `jq`.

Export the key in the environment that launches your agent client:

```bash
export LUMITRA_STUDIO_API_KEY="..."                        # required
export LUMITRA_STUDIO_BASE_URL="https://studio.lumitra.co"  # optional, default
```

`mcp.json` forwards these as `${LUMITRA_STUDIO_API_KEY}` and `${LUMITRA_STUDIO_BASE_URL}`. The Agent Plugins spec only guarantees expansion of `${PLUGIN_ROOT}` and `${PLUGIN_DATA}`, so some clients pass other `${...}` references through verbatim; `studio-mcp` treats an unexpanded value as unset and reads the variable from its process environment instead, which is why exporting it before launching the client always works.

## Install

### Claude Code

This repository is a plugin marketplace of one. Two commands:

```
/plugin marketplace add marlinjai/lumitra-studio-plugin
/plugin install lumitra-studio@lumitra
```

That installs the MCP server (started with `npx -y @marlinjai/studio-mcp`) and both skills. Export
`LUMITRA_STUDIO_API_KEY` before launching Claude Code, or add it to the server entry yourself.

If you would rather add only the tools, without the skills:

```bash
claude mcp add lumitra-studio -e LUMITRA_STUDIO_API_KEY="$LUMITRA_STUDIO_API_KEY" -- npx -y @marlinjai/studio-mcp
```

### Cursor

Add the MCP server to `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global):

```json
{
  "mcpServers": {
    "lumitra-studio": {
      "command": "npx",
      "args": ["-y", "@marlinjai/studio-mcp"],
      "env": { "LUMITRA_STUDIO_API_KEY": "${env:LUMITRA_STUDIO_API_KEY}" }
    }
  }
}
```

and copy `skills/lumitra-studio` (and, if you work with video, `skills/video-motion-analysis`) to
where Cursor looks for Agent Skills.

### Any other Agent Plugins client

Clone this repository and follow the client's "add plugin from directory" flow, pointing it at the
repository root, which is the plugin root: `plugin.json` and `mcp.json` are the
[agent-plugins.org](https://agent-plugins.org/) 1.0.0 manifests, and `.claude-plugin/` plus
`.mcp.json` are the Claude Code equivalents of the same thing. If the client supports Agent Skills
and MCP but not the plugin container, use the skill directories and the server entry separately;
both are plain spec-conformant files.

## Streamable HTTP instead of stdio

The shipped `mcp.json` uses stdio, which every client supports and which needs no running process. If you prefer a network endpoint (shared server, remote sandbox), start it yourself:

```bash
LUMITRA_STUDIO_API_KEY=... npx -y @marlinjai/studio-mcp --http --port 3939
```

and replace the server entry with the spec's Streamable HTTP form:

```json
{
  "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
  "mcpServers": {
    "lumitra-studio": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:3939/mcp"
    }
  }
}
```

Tool names and behaviour are identical in both transports.

## Tools exposed by the MCP server

`studio_list_projects`, `studio_generate_image`, `studio_get_job`, `studio_list_characters`, `studio_get_character`, `studio_create_character`, `studio_mint_character`, `studio_create_brand`, `studio_upload_brand_reference`, `studio_run_workflow`, `studio_get_run`, `studio_decide_judge`, `studio_get_run_output`, `studio_replace_character_in_video`, `studio_get_spend`, `studio_get_usage`, `studio_list_published`, `studio_describe_published`, `studio_run_published`, `studio_workflow_describe`, `studio_workflow_get`, `studio_workflow_create`, `studio_workflow_apply`, `studio_workflow_validate`, `studio_workflow_screenshot`.

The skill explains when to reach for which one.

## Where this comes from

This repository is the published mirror of the plugin. It is generated from the Lumitra Studio
source repository, which is private, and the payload here is checked against it on every sync, so
the two cannot drift. The Studio itself (the API these tools call) is a hosted service at
[studio.lumitra.co](https://studio.lumitra.co); nothing in this repository runs it.

Issues and questions about the plugin are welcome here.

## Links

- Studio: https://studio.lumitra.co
- Agent Plugins spec: https://agent-plugins.org/specification
- Agent Skills spec: https://agentskills.io/specification
- MCP server package: [`@marlinjai/studio-mcp`](https://www.npmjs.com/package/@marlinjai/studio-mcp) (source lives in the private Lumitra Studio repository, not this mirror)
