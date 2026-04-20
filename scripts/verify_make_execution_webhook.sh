#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEBHOOK_URL="${1:-${MAKE_EXECUTION_ANALYSIS_WEBHOOK:-}}"
PAYLOAD_FILE="${2:-$ROOT_DIR/docs/make_execution_analysis/sample_payload.json}"

if [[ -z "$WEBHOOK_URL" ]]; then
  echo "Usage: $0 <make-webhook-url> [payload-json]"
  exit 1
fi

if [[ ! -f "$PAYLOAD_FILE" ]]; then
  echo "Payload file not found: $PAYLOAD_FILE"
  exit 1
fi

BODY_FILE="$(mktemp)"
cleanup() {
  rm -f "$BODY_FILE"
}
trap cleanup EXIT

HTTP_CODE="$(
  curl -sS -o "$BODY_FILE" -w "%{http_code}" \
    -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    --data @"$PAYLOAD_FILE"
)"

python3 - "$HTTP_CODE" "$BODY_FILE" <<'PY'
import json
import pathlib
import sys

status = int(sys.argv[1])
body_path = pathlib.Path(sys.argv[2])
body = body_path.read_text(encoding="utf-8")


def normalize_json_text(text: str) -> str:
    trimmed = text.strip()
    if not trimmed.startswith("```"):
        return trimmed
    trimmed = trimmed.removeprefix("```json").removeprefix("```").strip()
    if trimmed.endswith("```"):
        trimmed = trimmed[:-3].strip()
    return trimmed


def try_parse_json_text(text: str):
    normalized = normalize_json_text(text)
    if not normalized:
        return None
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return None


def extract_structured_result(raw_value):
    queue = [raw_value]
    while queue:
        candidate = queue.pop(0)
        if candidate is None:
            continue
        if isinstance(candidate, str):
            parsed = try_parse_json_text(candidate)
            if parsed is not None:
                queue.append(parsed)
                continue
            normalized = normalize_json_text(candidate)
            if normalized:
                return {"summary": normalized}
            continue
        if not isinstance(candidate, dict):
            continue
        if any(key in candidate for key in ("summary", "highlights", "execution_plan", "trigger_points", "invalidation_points")):
            return candidate
        for key in ("data", "analysis", "result", "output"):
            value = candidate.get(key)
            if value:
                queue.append(value)
        gemini_parts = candidate.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        if gemini_parts:
            gemini_text = "\n".join(
                part.get("text", "") for part in gemini_parts if isinstance(part, dict) and part.get("text")
            ).strip()
            if gemini_text:
                queue.append(gemini_text)
        nested_parts = candidate.get("response", {}).get("candidates", [{}])[0].get("content", {}).get("parts", [])
        if nested_parts:
            nested_text = "\n".join(
                part.get("text", "") for part in nested_parts if isinstance(part, dict) and part.get("text")
            ).strip()
            if nested_text:
                queue.append(nested_text)
    return None


def is_placeholder_text(value: str) -> bool:
    normalized = normalize_json_text(value).strip().lower()
    return normalized in {"accepted", "ok", "success"}


if status >= 400:
    print(f"Webhook check failed with HTTP {status}")
    print(body.strip() or "<empty body>")
    sys.exit(1)

if is_placeholder_text(body):
    print("Webhook returned only a placeholder confirmation, not the final AI analysis payload.")
    print(body.strip() or "<empty body>")
    sys.exit(1)

parsed = try_parse_json_text(body) or body
structured = extract_structured_result(parsed)
if not structured:
    print("Webhook returned 2xx, but the body could not be parsed into an AI analysis payload.")
    print(body.strip() or "<empty body>")
    sys.exit(1)

summary = str(structured.get("summary", "")).strip()
if not summary:
    print("Webhook returned a parseable payload, but 'summary' is empty.")
    print(json.dumps(structured, ensure_ascii=False, indent=2))
    sys.exit(1)

if is_placeholder_text(summary) and len(structured.keys()) <= 2:
    print("Webhook returned only a placeholder confirmation, not a structured AI analysis result.")
    print(json.dumps(structured, ensure_ascii=False, indent=2))
    sys.exit(1)

print("Webhook check passed.")
print(f"Summary: {summary}")
print(f"Model: {structured.get('model', '<missing>')}")
print(f"Next step: {structured.get('next_step', '<missing>')}")
print(f"Source fields present: {sorted(structured.keys())}")
PY
