"""Live LLM smoke test for the AOC-4 judges.

Hits every reachable Ollama endpoint directly (no engine) with the same request
contract the judges use, and reports latency + whether a JSON verdict came back.

Run:  python test_runs/llm_smoke_test.py
"""

import json
import time

import requests

TARGETS = [
    ("shipped default (company server)", "http://192.168.112.2:11434", "qwen3.5:4b"),
    ("local Ollama", "http://localhost:11434", "llama3.2:latest"),
]

PROMPT = (
    "You are a strict statutory-audit judge for an Indian Companies Act AOC-4 "
    "annual-filing review. Adjudicate ONE compliance checkpoint using ONLY the "
    "extract below.\n\n"
    "CHECKPOINT:\nWhether Shareholding more than 5% is mentioned in Schedule.\n\n"
    'Reply with JSON ONLY in this exact shape:\n'
    '{"verdict": "Yes" | "No" | "Cannot determine", "reason": "<concise audit explanation>"}\n\n'
    "RELEVANT DOCUMENT EXTRACT:\n=====\n"
    "Shareholding of promoters: 5.01% of the total equity share capital held by Mr. A.\n"
    "=====\n"
)


def tags(base_url):
    try:
        resp = requests.get(base_url + "/api/tags", timeout=10)
        resp.raise_for_status()
        return [m.get("name") for m in resp.json().get("models", [])], None
    except Exception as exc:  # noqa: BLE001 - report any transport failure
        return [], exc


def ask(base_url, model):
    payload = {
        "model": model,
        "prompt": PROMPT,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_ctx": 8192},
    }
    started = time.time()
    try:
        resp = requests.post(base_url + "/api/generate", json=payload, timeout=180)
        latency = time.time() - started
        resp.raise_for_status()
        body = resp.json()
    except Exception as exc:  # noqa: BLE001 - report any transport failure
        return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc),
                "seconds": round(time.time() - started, 2)}

    raw = body.get("response") or ""
    parsed = None
    try:
        parsed = json.loads(raw)
    except Exception:  # noqa: BLE001 - model may wrap JSON in prose / thinking
        parsed = None

    return {
        "ok": bool(parsed and str(parsed.get("verdict", "")).strip()),
        "seconds": round(latency, 2),
        "raw_response": raw[:300],
        "thinking_present": bool(body.get("thinking")),
        "parsed": parsed,
    }


def main():
    for label, base_url, model in TARGETS:
        print("=" * 100)
        print("%s -> %s  (model %s)" % (label, base_url, model))
        print("=" * 100)
        models, error = tags(base_url)
        if error is not None:
            print("  /api/tags FAILED: %s: %s" % (type(error).__name__, error))
            continue
        print("  /api/tags OK - installed models: %s" % (models,))
        if model not in models:
            print("  !! requested model %r is NOT installed on this server" % model)
        result = ask(base_url, model)
        print("  /api/generate -> ok=%s  latency=%ss" % (result.get("ok"), result.get("seconds")))
        if result.get("error"):
            print("  error: %s" % result["error"])
        else:
            print("  thinking present : %s" % result.get("thinking_present"))
            print("  parsed verdict   : %s" % (result.get("parsed"),))
            print("  raw response     : %r" % result.get("raw_response"))
        print()


if __name__ == "__main__":
    main()
