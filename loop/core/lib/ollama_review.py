#!/usr/bin/env python3
"""The `local` reviewer: sends the review prompt (stdin) to a model on Ollama and prints its JSON
verdict. Standard library only. review.sh runs it for the reviewer named `local`.

Settings, from the environment or else ~/.config/agent-loop/defaults.sh:
  LOOP_LOCAL_MODEL    the Ollama tag; review.sh sets it from the reviewer name (local/<name>)
  LOOP_OLLAMA_URL     default http://127.0.0.1:11434
  LOOP_LOCAL_CTX      context window to request, default 65536
  LOOP_LOCAL_TIMEOUT  seconds, default 900
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request


def setting(name, default):
    if os.environ.get(name):
        return os.environ[name]
    path = os.path.expanduser("~/.config/agent-loop/defaults.sh")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r'^%s="([^"$]*)"' % name, line.strip())
                if m and m.group(1):
                    return m.group(1)
    except OSError:
        pass
    return default


def main():
    model = setting("LOOP_LOCAL_MODEL", "qwen3.6:35b-a3b")
    url = setting("LOOP_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    prompt = sys.stdin.read() + (
        "\n\nNote for this review: you have no tools. Everything you can see is in this prompt, so grade "
        "from the spec, the triage log, the test results and the diff above.\n")
    body = {"model": model, "stream": False, "messages": [{"role": "user", "content": prompt}],
            "options": {"temperature": 0, "num_ctx": int(setting("LOOP_LOCAL_CTX", "65536"))}}
    schema = os.environ.get("LOOP_SCHEMA_FILE")
    if schema and os.path.exists(schema):
        with open(schema, encoding="utf-8") as fh:
            body["format"] = json.load(fh)   # Ollama constrains the output to this JSON schema
    req = urllib.request.Request(url + "/api/chat", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=int(setting("LOOP_LOCAL_TIMEOUT", "900"))) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        sys.exit("ollama: HTTP %s from %s: %s (is the model pulled? ollama pull %s)" % (exc.code, url, detail, model))
    except OSError as exc:
        sys.exit("ollama isn't answering at %s (%s): open the Ollama app, or run: ollama serve" % (url, exc))
    sys.stdout.write((data.get("message") or {}).get("content") or "")


if __name__ == "__main__":
    main()
