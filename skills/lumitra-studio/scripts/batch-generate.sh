#!/usr/bin/env bash
# Batch image generation against Lumitra Studio (https://studio.lumitra.co).
# Speaks only the public HTTP API; nothing runs locally.
#
# Contract:
#   submit: POST {base}/api/generate
#           body { brandSlug?, brandMode?, prompt, settings:{ aspectRatio, model? } }
#           -> { jobId }
#   poll:   GET  {base}/api/v1/jobs/{jobId}
#           -> { job:{ status, errorMessage, costUsd, model }, resultAsset:{ url } }
#   auth:   Authorization: Bearer $LUMITRA_STUDIO_API_KEY
#
# Strategy: submit ALL prompts first (fast enqueue), then poll all jobs on an
# interval until each reaches a terminal state. Wall-clock = slowest single job,
# not the sum.
#
# bash 3.2 compatible (macOS /bin/bash): indexed arrays only, no `declare -A`.
# State for the i-th job lives in STATUS[i]/URL[i]/COST[i]/ERR[i], parallel to
# JOBIDS/PROMPTS.
#
# Usage (prompts on stdin, one per line):
#   printf '%s\n' "a happy red dino" "a sleeping blue dino" \
#     | batch-generate.sh --brand my-brand --mode illustration --aspect 1:1 --out ./out
#
# Flags:
#   --brand <slug>     brand slug (optional; omit for an unbranded image)
#   --mode <mode>      brand mode (e.g. illustration); optional
#   --aspect <ratio>   aspect ratio (default 1:1)
#   --model <id>       model id (optional; Studio default is used if omitted)
#   --out <dir>        if set, download each succeeded image into <dir>
#   --budget <sec>     total poll budget in seconds (default 600 = 10 min)
#
# Env:
#   LUMITRA_STUDIO_API_KEY    required (Bearer key; never printed)
#   LUMITRA_STUDIO_BASE_URL   default https://studio.lumitra.co
set -euo pipefail

BASE="${LUMITRA_STUDIO_BASE_URL:-https://studio.lumitra.co}"
KEY="${LUMITRA_STUDIO_API_KEY:-}"
BRAND="" MODE="" ASPECT="1:1" MODEL="" OUT="" BUDGET="600"

while [ $# -gt 0 ]; do
  case "$1" in
    --brand)  BRAND="$2"; shift 2 ;;
    --mode)   MODE="$2"; shift 2 ;;
    --aspect) ASPECT="$2"; shift 2 ;;
    --model)  MODEL="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    -h|--help) sed -n '2,35p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

[ -z "$KEY" ] && { echo "ERROR: LUMITRA_STUDIO_API_KEY is not set. Create a key at https://auth.lumitra.co (sign in, open your organization, API Keys) and export it before running this script." >&2; exit 1; }
command -v jq >/dev/null || { echo "ERROR: jq is required (https://jqlang.github.io/jq/)" >&2; exit 1; }
command -v curl >/dev/null || { echo "ERROR: curl is required" >&2; exit 1; }

auth=(-H "authorization: Bearer ${KEY}")

# 1. Submit every prompt, collecting jobIds in order.
JOBIDS=() PROMPTS=()
while IFS= read -r line || [ -n "$line" ]; do
  [ -z "${line//[[:space:]]/}" ] && continue
  body=$(jq -n --arg b "$BRAND" --arg m "$MODE" --arg p "$line" --arg a "$ASPECT" --arg model "$MODEL" \
    '{prompt:$p, settings: ({aspectRatio:$a} + (if $model=="" then {} else {model:$model} end))}
     + (if $b=="" then {} else {brandSlug:$b} end)
     + (if $m=="" then {} else {brandMode:$m} end)')
  http=$(curl -sS -o /tmp/studio-submit.$$ -w '%{http_code}' -X POST "${BASE}/api/generate" "${auth[@]}" -H 'content-type: application/json' -d "$body" || echo 000)
  resp=$(cat /tmp/studio-submit.$$ 2>/dev/null || true); rm -f /tmp/studio-submit.$$
  case "$http" in
    401|403) echo "ERROR: Studio rejected the API key (HTTP $http). Check LUMITRA_STUDIO_API_KEY." >&2; exit 1 ;;
    000)     echo "ERROR: could not reach ${BASE}" >&2; exit 1 ;;
  esac
  jobid=$(printf '%s' "$resp" | jq -r '.jobId // empty' 2>/dev/null || true)
  if [ -z "$jobid" ]; then
    echo "submit FAILED (HTTP $http)  <- ${line}" >&2
    echo "  response: $(printf '%s' "$resp" | jq -c '.error // .' 2>/dev/null || printf '%s' "$resp")" >&2
    continue
  fi
  JOBIDS+=("$jobid"); PROMPTS+=("$line")
  echo "submitted ${jobid}  <-  ${line}"
done

[ "${#JOBIDS[@]}" -eq 0 ] && { echo "no jobs submitted" >&2; exit 1; }

# 2. Poll all jobs until each is terminal or the budget elapses.
n=${#JOBIDS[@]}
STATUS=() URL=() COST=() ERR=()
i=0
while [ "$i" -lt "$n" ]; do STATUS[i]=""; URL[i]=""; COST[i]="0"; ERR[i]=""; i=$((i+1)); done

deadline=$(( $(date +%s) + BUDGET ))
pending=$n
while [ "$pending" -gt 0 ] && [ "$(date +%s)" -lt "$deadline" ]; do
  sleep 5
  pending=0
  i=0
  while [ "$i" -lt "$n" ]; do
    case "${STATUS[$i]}" in succeeded|failed|canceled) i=$((i+1)); continue ;; esac
    resp=$(curl -sS "${BASE}/api/v1/jobs/${JOBIDS[$i]}" "${auth[@]}" || echo '{}')
    st=$(printf '%s' "$resp" | jq -r '.job.status // "unknown"' 2>/dev/null || echo unknown)
    case "$st" in
      succeeded)
        STATUS[i]="succeeded"
        URL[i]=$(printf '%s' "$resp" | jq -r '.resultAsset.url // empty')
        COST[i]=$(printf '%s' "$resp" | jq -r '.job.costUsd // 0')
        ;;
      failed|canceled)
        STATUS[i]="$st"
        COST[i]=$(printf '%s' "$resp" | jq -r '.job.costUsd // 0')
        ERR[i]=$(printf '%s' "$resp" | jq -r '.job.errorMessage // ""')
        ;;
      *) pending=$((pending+1)) ;;
    esac
    i=$((i+1))
  done
done

# 3. Report (+ optional download) and total the cost.
total=0 ok=0 bad=0
[ -n "$OUT" ] && mkdir -p "$OUT"
i=0
while [ "$i" -lt "$n" ]; do
  p="${PROMPTS[$i]}"; st="${STATUS[$i]}"; u="${URL[$i]}"; c="${COST[$i]}"
  [ -n "$st" ] || st="timeout"
  echo "----"
  echo "prompt : ${p}"
  echo "job    : ${JOBIDS[$i]}"
  echo "status : ${st}"
  [ "$st" = "succeeded" ] && echo "url    : ${u}"
  [ -n "${ERR[$i]}" ] && echo "error  : ${ERR[$i]}"
  [ "$st" = "timeout" ] && echo "note   : still running server-side; read it later via GET ${BASE}/api/v1/jobs/${JOBIDS[$i]}"
  echo "cost   : ${c}"
  total=$(awk "BEGIN{print ${total} + ${c}}")
  if [ "$st" = "succeeded" ]; then
    ok=$((ok+1))
    if [ -n "$OUT" ] && [ -n "$u" ]; then
      fn="${OUT}/$(printf '%03d' "$i").png"
      if curl -sS -f -o "$fn" "$u"; then echo "saved  : ${fn}"; else echo "save FAILED: ${fn}" >&2; fi
    fi
  else
    bad=$((bad+1))
  fi
  i=$((i+1))
done
echo "===="
echo "succeeded: ${ok}  failed/timeout: ${bad}  total cost USD: ${total}"
[ "$bad" -eq 0 ]
