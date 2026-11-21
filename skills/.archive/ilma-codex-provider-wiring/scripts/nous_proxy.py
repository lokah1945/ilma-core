#!/usr/bin/env python3
"""
nous_proxy.py — local Anthropic/OpenAI "responses" -> Nous "chat/completions" translator.

WHY: Codex v0.144.5 only speaks the OpenAI *Responses* wire API
(wire_api = "responses"). Nous Research inference portal only implements
OpenAI *Chat Completions* (/v1/chat/completions) and returns 404 on /v1/responses.

This proxy sits at http://127.0.0.1:9191, accepts Codex's Responses-API
calls, translates them to Chat Completions, forwards to Nous with a FRESH
OAuth bearer token (read live from Hermes auth.json each request, so expiry
is handled automatically), and maps the chat response back into a minimal
Responses-shaped payload Codex can parse.

Endpoints handled:
  POST /v1/responses            -> translate to /v1/chat/completions (SSE stream)
  POST /v1/chat/completions     -> pass-through
  GET  /v1/models               -> proxy to Nous models list
  GET  /healthz                 -> liveness
"""
import json
import os
import time
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AUTH = "/root/.hermes/profiles/ilma/auth.json"
NOUS_BASE = "https://inference-api.nousresearch.com"
LISTEN = ("127.0.0.1", 9191)


def get_token():
    with open(AUTH) as f:
        d = json.load(f)
    n = d.get("providers", {}).get("nous", {})
    tok = n.get("access_token") or n.get("agent_key")
    if not tok:
        raise RuntimeError("no Nous token in auth.json")
    return tok


def _post_nous(path, payload, token):
    url = NOUS_BASE + path
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode(errors="replace") or "{}")


def _get_nous(path, token):
    url = NOUS_BASE + path
    req = urllib.request.Request(url, method="GET",
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode(errors="replace") or "{}")


def responses_to_chat(body):
    model = body.get("model", "tencent/hy3:free")
    raw = body.get("input")
    messages = []
    if isinstance(raw, str):
        messages.append({"role": "user", "content": raw})
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
                if isinstance(content, list):
                    txt = " ".join(
                        p.get("text", "") for p in content
                        if isinstance(p, dict) and p.get("type") == "input_text"
                    )
                    content = txt
                messages.append({"role": role, "content": content})
            elif isinstance(item, str):
                messages.append({"role": "user", "content": item})
    out = {"model": model, "messages": messages, "stream": False}
    # hy3:free is a REASONING model: final answer in content, thought in reasoning.
    # Raise cap so final content is not truncated before it appears.
    if body.get("max_output_tokens"):
        out["max_tokens"] = max(int(body["max_output_tokens"]), 1024)
    else:
        out["max_tokens"] = 4096
    if body.get("temperature") is not None:
        out["temperature"] = body["temperature"]
    return out


def chat_to_responses(model, chat_resp):
    text = ""
    choices = chat_resp.get("choices") or []
    if choices:
        msg = choices[0].get("message", {})
        # reasoning models may put answer in content or only reasoning if truncated
        text = msg.get("content") or msg.get("reasoning") or ""
    return {
        "id": chat_resp.get("id", "resp-local"),
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "output": [
            {"id": "msg-local", "type": "message", "role": "assistant",
             "content": [{"type": "output_text", "text": text}]}
        ],
        "status": "completed",
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        payload = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_sse(self, events):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        for ev in events:
            etype = ev.get("type")
            data = json.dumps(ev.get("data", {}))
            chunk = f"event: {etype}\ndata: {data}\n\n"
            try:
                self.wfile.write(chunk.encode())
                self.wfile.flush()
            except Exception:
                break

    def do_GET(self):
        if self.path.rstrip("/") in ("/healthz", "/health"):
            self._send(200, {"ok": True})
            return
        if self.path.startswith("/v1/models"):
            try:
                code, data = _get_nous("/v1/models", get_token())
                self._send(code, data)
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode() or "{}")
        except Exception:
            body = {}
        if self.path.rstrip("/") in ("/v1/responses", "/responses"):
            try:
                token = get_token()
                chat_body = responses_to_chat(body)
                if body.get("stream"):
                    code, chat_resp = _post_nous(
                        "/v1/chat/completions", {**chat_body, "stream": False}, token)
                    if code != 200:
                        self._send(code, chat_resp)
                        return
                    resp = chat_to_responses(chat_body["model"], chat_resp)
                    rid = resp["id"]
                    item = resp["output"][0]
                    text = item["content"][0].get("text", "")
                    events = [
                        {"type": "response.created", "data": resp},
                        {"type": "response.in_progress",
                         "data": {"type": "response", "id": rid, "status": "in_progress"}},
                        {"type": "response.output_item.added",
                         "data": {"type": "response.output_item.added",
                                  "output_index": 0, "item": item}},
                        {"type": "response.content_part.added",
                         "data": {"type": "response.content_part.added",
                                  "item_id": "msg-local", "output_index": 0,
                                  "content_index": 0, "part": {"type": "output_text", "text": ""}}},
                        {"type": "response.output_text.delta",
                         "data": {"type": "response.output_text.delta",
                                  "item_id": "msg-local", "output_index": 0,
                                  "content_index": 0, "delta": text}},
                        {"type": "response.output_text.done",
                         "data": {"type": "response.output_text.done",
                                  "item_id": "msg-local", "output_index": 0,
                                  "content_index": 0, "text": text}},
                        {"type": "response.content_part.done",
                         "data": {"type": "response.content_part.done",
                                  "item_id": "msg-local", "output_index": 0,
                                  "content_index": 0,
                                  "part": {"type": "output_text", "text": text}}},
                        {"type": "response.output_item.done",
                         "data": {"type": "response.output_item.done",
                                  "output_index": 0, "item": item}},
                        {"type": "response.completed", "data": resp},
                    ]
                    self._send_sse(events)
                else:
                    code, chat_resp = _post_nous("/v1/chat/completions", chat_body, token)
                    if code != 200:
                        self._send(code, chat_resp)
                        return
                    self._send(200, chat_to_responses(chat_body["model"], chat_resp))
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        if self.path.rstrip("/") in ("/v1/chat/completions", "/chat/completions"):
            try:
                token = get_token()
                code, data = _post_nous("/v1/chat/completions", body, token)
                self._send(code, data)
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        self._send(404, {"error": "unsupported path " + self.path})


def main():
    srv = ThreadingHTTPServer(LISTEN, Handler)
    print(f"nous_proxy listening on http://{LISTEN[0]}:{LISTEN[1]}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
