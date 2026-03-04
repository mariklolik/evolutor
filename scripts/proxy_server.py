"""Minimal Anthropic /v1/messages → OpenAI /v1/chat/completions proxy.

No litellm needed. ~80 lines. Starts in seconds.
Translates the Anthropic SDK wire format to vLLM's OpenAI-compatible API.

Usage: python scripts/proxy_server.py --port 4000 --backend http://localhost:8000/v1
"""
from __future__ import annotations
import argparse, json, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import request as urlrequest

BACKEND = os.environ.get("VLLM_BACKEND", "http://localhost:8000/v1")
MODEL_NAME = os.environ.get("VLLM_MODEL_NAME", "qwen3-coder-30b")


def anthropic_to_openai(body: dict) -> dict:
    """Translate Anthropic messages format to OpenAI chat completions format."""
    messages = []
    system = body.get("system", "")
    if system:
        if isinstance(system, list):
            system = " ".join(s.get("text", "") if isinstance(s, dict) else s for s in system)
    # Qwen3: /no_think disables extended thinking, keeps output clean
    if system:
        messages.append({"role": "system", "content": system + " /no_think"})
    else:
        messages.append({"role": "system", "content": "/no_think"})

    for msg in body.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Anthropic content blocks
            text_parts = []
            tool_results = []
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_result":
                        tool_results.append(block.get("content", ""))
                    elif btype == "tool_use":
                        text_parts.append(f"[Tool call: {block.get('name')}({json.dumps(block.get('input', {}))})]")
            content = " ".join(text_parts + tool_results)
        messages.append({"role": role, "content": content})

    oai = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": body.get("max_tokens", 4096),
        "temperature": body.get("temperature", 0.6),
        "stream": False,
    }
    if "stop_sequences" in body:
        oai["stop"] = body["stop_sequences"]
    # Disable thinking for cleaner output
    oai["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return oai


def openai_to_anthropic(oai_resp: dict) -> dict:
    """Translate OpenAI response to Anthropic messages response format."""
    choice = oai_resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    content = msg.get("content", "")
    # Strip thinking tokens if present
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    usage = oai_resp.get("usage", {})
    return {
        "id": oai_resp.get("id", "msg_local"),
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": content}],
        "model": oai_resp.get("model", MODEL_NAME),
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

    def do_GET(self):
        if self.path in ("/health", "/v1/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))

        if self.path.startswith("/v1/messages"):
            oai_body = anthropic_to_openai(body)
            url = f"{BACKEND}/chat/completions"
        else:
            # Pass through other requests unchanged
            oai_body = body
            url = f"{BACKEND}{self.path}"

        try:
            req = urlrequest.Request(
                url,
                data=json.dumps(oai_body).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=180) as resp:
                oai_resp = json.loads(resp.read())

            if self.path.startswith("/v1/messages"):
                result = openai_to_anthropic(oai_resp)
            else:
                result = oai_resp

            out = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        except Exception as e:
            error = json.dumps({"error": {"message": str(e), "type": "proxy_error"}}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(error)
            print(f"[proxy] Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--backend", default=BACKEND)
    parser.add_argument("--model", default=MODEL_NAME)
    args = parser.parse_args()
    BACKEND = args.backend
    MODEL_NAME = args.model
    print(f"[proxy] Anthropic proxy on :{args.port} → {args.backend} (model={args.model})")
    server = HTTPServer(("0.0.0.0", args.port), ProxyHandler)
    server.serve_forever()
