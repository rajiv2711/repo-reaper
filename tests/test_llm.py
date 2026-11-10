"""Phase 6: reaper/llm.py, the Ollama /api/chat client. No real Ollama: _post is mocked,
or a throwaway local HTTP server stands in for it."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from reaper import llm

SCHEMA = {"type": "object",
          "properties": {"summary": {"type": "string"},
                         "role": {"type": "string", "enum": ["service", "utility"]}},
          "required": ["summary", "role"]}
MESSAGES = [{"role": "system", "content": "sys"}, {"role": "user", "content": "file text"}]
GOOD = '{"summary": "Does things.", "role": "utility"}'


def fake_post(replies):
    """A _post stand-in returning Ollama-shaped bodies with the given contents, in order."""
    calls = []

    def post(url, payload, timeout):
        calls.append((url, json.loads(json.dumps(payload))))  # deep copy
        return {"message": {"role": "assistant", "content": replies[len(calls) - 1]}}
    return post, calls


def test_payload_and_default_host(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    post, calls = fake_post([GOOD])
    monkeypatch.setattr(llm, "_post", post)
    assert llm.chat("m:1b", MESSAGES, SCHEMA) == {"summary": "Does things.", "role": "utility"}
    assert len(calls) == 1
    url, payload = calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert payload == {"model": "m:1b", "messages": MESSAGES, "stream": False,
                       "format": SCHEMA, "options": {"temperature": 0}}
    assert "num_ctx" not in json.dumps(payload)


@pytest.mark.parametrize("env, url", [
    ("http://gpu-box:11434/", "http://gpu-box:11434/api/chat"),
    ("gpu-box:11434", "http://gpu-box:11434/api/chat"),
    ("https://ollama.example", "https://ollama.example/api/chat"),
])
def test_ollama_host_env(monkeypatch, env, url):
    monkeypatch.setenv("OLLAMA_HOST", env)
    post, calls = fake_post([GOOD])
    monkeypatch.setattr(llm, "_post", post)
    llm.chat("m", MESSAGES, SCHEMA)
    assert calls[0][0] == url


@pytest.mark.parametrize("bad", [
    "not json at all",
    '{"summary": "x"}',                                # required key missing
    '{"summary": "x", "role": "wizard"}',              # not in enum
    '{"summary": 3, "role": "utility"}',               # wrong type
    '["summary", "role"]',                             # not an object
])
def test_retry_once_on_invalid_reply(monkeypatch, bad):
    post, calls = fake_post([bad, GOOD])
    monkeypatch.setattr(llm, "_post", post)
    assert llm.chat("m", MESSAGES, SCHEMA)["role"] == "utility"
    assert len(calls) == 2
    retry = calls[1][1]["messages"]
    assert retry[:2] == MESSAGES                       # original request unchanged
    assert retry[2] == {"role": "assistant", "content": bad}
    assert retry[3]["role"] == "user" and "JSON" in retry[3]["content"]
    assert len(retry) == 4


def test_invalid_twice_raises(monkeypatch):
    post, calls = fake_post(["nope", "still nope"])
    monkeypatch.setattr(llm, "_post", post)
    with pytest.raises(llm.InvalidResponse):
        llm.chat("m", MESSAGES, SCHEMA)
    assert len(calls) == 2
    assert issubclass(llm.InvalidResponse, llm.LLMError)


# ---------------------------------------------------------------- real HTTP, fake server

class FakeOllama(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.seen.append((self.path, self.headers["Content-Type"], body))
        if body["model"] == "missing":
            self.send_response(404)
            out = {"error": "model 'missing' not found"}
        else:
            self.send_response(200)
            out = {"model": body["model"], "message": {"role": "assistant", "content": GOOD},
                   "done": True}
        data = json.dumps(out).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_server(monkeypatch):
    FakeOllama.seen = []
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OLLAMA_HOST", f"127.0.0.1:{server.server_port}")
    yield FakeOllama.seen
    server.shutdown()
    server.server_close()


def test_http_roundtrip(fake_server):
    assert llm.chat("m", MESSAGES, SCHEMA)["summary"] == "Does things."
    [(path, ctype, body)] = fake_server
    assert path == "/api/chat"
    assert ctype == "application/json"
    assert body["stream"] is False and body["format"] == SCHEMA


def test_http_error_raises_with_server_message(fake_server):
    with pytest.raises(llm.LLMError, match="not found"):
        llm.chat("missing", MESSAGES, SCHEMA)


def test_unreachable_host_raises(monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()  # nothing listens on this port now
    monkeypatch.setenv("OLLAMA_HOST", f"127.0.0.1:{port}")
    with pytest.raises(llm.LLMError, match="Ollama") as exc:
        llm.chat("m", MESSAGES, SCHEMA)
    assert not isinstance(exc.value, llm.InvalidResponse)
