#!/usr/bin/env bash
# Live smoke against the DEPLOYED engine — verify the artifact, not the tests.
#
# Run after every merge to main (Railway auto-deploys). Uses the real deployed
# URL and a real API key from the environment; nothing here is committed.
#
#   FUFIRE_URL=https://api.fufire.space FUFIRE_KEY=ff_pro_... scripts/live_smoke.sh
#
# Dependencies: bash + curl + grep only (no python/jq) — runs anywhere.
# Exits non-zero on the first failed check.
set -euo pipefail
: "${FUFIRE_URL:?set FUFIRE_URL to the deployed base URL}"
: "${FUFIRE_KEY:?set FUFIRE_KEY to a real API key}"

BODY='{"date":"1990-06-15T14:30:00","tz":"Europe/Berlin","lon":13.405,"lat":52.52}'

echo "1) health"
curl -fsS "$FUFIRE_URL/health" | grep -q '"status"[[:space:]]*:[[:space:]]*"healthy"'

echo "2) auth is enforced (401 without a key)"
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$FUFIRE_URL/v1/calculate/bazi" \
  -H 'Content-Type: application/json' -d "$BODY")
test "$code" = "401" || { echo "   expected 401, got $code — auth NOT enforced!"; exit 1; }

echo "3) real calculation with a valid key"
curl -fsS -X POST "$FUFIRE_URL/v1/calculate/bazi" \
  -H "X-API-Key: $FUFIRE_KEY" -H 'Content-Type: application/json' -d "$BODY" \
  | grep -q '"pillars"'

echo "4) X-Request-ID contract (garbage in → UUID out, FUFIRE-009)"
rid=$(curl -fsS -D- -o /dev/null "$FUFIRE_URL/health" -H 'X-Request-ID: not-a-uuid' \
  | awk -F': ' 'tolower($1)=="x-request-id"{print $2}' | tr -d '\r')
if printf '%s' "$rid" | grep -qiE '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
  echo "   client garbage replaced with UUID: $rid"
else
  echo "   X-Request-ID is not a UUID ('$rid') — FUFIRE-009 fix not live"; exit 1
fi

echo "5) rate-limit headers present on a now-limited route (FUFIRE-004)"
curl -fsS -D- -o /dev/null -X POST "$FUFIRE_URL/v1/calculate/wuxing" \
  -H "X-API-Key: $FUFIRE_KEY" -H 'Content-Type: application/json' -d "$BODY" \
  | grep -qi '^x-ratelimit-limit:'

echo "6) contract no longer advertises daily quotas (FUFIRE-005, D2)"
if curl -fsS "$FUFIRE_URL/openapi.json" | grep -qi 'requests/day'; then
  echo "   spec STILL advertises daily quotas — deployed artifact is stale"; exit 1
else
  echo "   spec advertises only enforced per-minute limits"
fi

echo "SMOKE PASSED"
