"""Minimal Ollama client: one non-streaming /api/chat call with a JSON-schema reply format.

Host: $OLLAMA_HOST (scheme optional), else http://localhost:11434. Temperature 0. num_ctx is
never sent, so the server's own context setting applies. A reply that is not valid JSON or does
not fit the schema's top level (object, required keys, property types, enums) is retried once,
with the bad reply and a correction appended to the conversation.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:11434"
TIMEOUT = 600  # seconds; the first call of a run may also load the model


class LLMError(RuntimeError):
    """The call failed: Ollama unreachable, HTTP error, or an unusable reply."""


class InvalidResponse(LLMError):
    """The model replied twice with JSON that does not fit the schema."""


RETRY_PROMPT = ("Your reply was not valid JSON matching the required schema. "
                "Reply again with only the JSON object.")

_TYPES = {"string": str, "array": list, "object": dict, "boolean": bool,
          "integer": int, "number": (int, float)}


def host() -> str:
    h = (os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).strip().rstrip("/")
    return h if "://" in h else "http://" + h


def _post(url: str, payload: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", detail)
        except (ValueError, AttributeError):
            pass
        raise LLMError(f"Ollama at {url} returned HTTP {e.code}: {detail}") from None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise LLMError(f"cannot reach Ollama at {url}: {reason}") from None
    except ValueError as e:
        raise LLMError(f"Ollama at {url} sent a non-JSON body: {e}") from None


def _fits(obj, schema: dict) -> bool:
    """Shallow check: an object with the required keys, typed properties, enum values."""
    if not isinstance(obj, dict):
        return False
    if any(k not in obj for k in schema.get("required", [])):
        return False
    for name, prop in schema.get("properties", {}).items():
        if name not in obj:
            continue
        want = _TYPES.get(prop.get("type"))
        value = obj[name]
        if want and (not isinstance(value, want) or isinstance(value, bool) and want is not bool):
            return False
        if "enum" in prop and value not in prop["enum"]:
            return False
    return True


def chat(model: str, messages: list[dict], schema: dict) -> dict:
    """Ask `model`; return the reply parsed as a dict that fits `schema`."""
    url = host() + "/api/chat"
    convo = list(messages)
    for attempt in range(2):
        payload = {"model": model, "messages": convo, "stream": False, "format": schema,
                   "options": {"temperature": 0}}
        body = _post(url, payload, TIMEOUT)
        content = (body.get("message") or {}).get("content", "")
        try:
            obj = json.loads(content)
        except ValueError:
            obj = None
        if _fits(obj, schema):
            return obj
        convo = [*messages, {"role": "assistant", "content": content},
                 {"role": "user", "content": RETRY_PROMPT}]
    raise InvalidResponse(f"{model} gave no valid JSON reply after a retry: {content[:200]!r}")
