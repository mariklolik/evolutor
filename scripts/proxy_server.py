"""Minimal Anthropic /v1/messages → OpenAI /v1/chat/completions proxy.

No litellm needed. ~80 lines. Starts in seconds.
Translates the Anthropic SDK wire format to vLLM's OpenAI-compatible API.

Usage: python scripts/proxy_server.py --port 4000 --backend http://localhost:8000/v1
"""
from __future__ import annotations
import argparse, json, os, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import request as urlrequest

# Bypass system HTTP_PROXY for localhost backend calls
_no_proxy_opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))

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
            text_parts = []
            tool_result_msgs = []  # becomes separate tool-role messages

            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    # assistant tool_use block → becomes tool_calls on assistant message
                    # handled below when role == assistant
                    pass
                elif btype == "tool_result":
                    tool_result_msgs.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", "call_0"),
                        "content": _flatten_content(block.get("content", "")),
                    })

            if role == "assistant":
                # Convert tool_use blocks to tool_calls
                tool_uses = [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]
                texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
                oai_msg: dict = {"role": "assistant", "content": " ".join(texts) or ""}
                if tool_uses:
                    oai_msg["tool_calls"] = [
                        {
                            "id": tu.get("id", f"call_{i}"),
                            "type": "function",
                            "function": {
                                "name": tu["name"],
                                "arguments": json.dumps(tu.get("input", {})),
                            },
                        }
                        for i, tu in enumerate(tool_uses)
                    ]
                messages.append(oai_msg)
            elif tool_result_msgs:
                # user message with tool_results → text first, then tool role msgs
                if text_parts:
                    messages.append({"role": "user", "content": " ".join(text_parts)})
                messages.extend(tool_result_msgs)
            else:
                content = " ".join(text_parts)
                messages.append({"role": role, "content": content})
        else:
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
    # Convert Anthropic tool definitions to OpenAI tools format
    if "tools" in body:
        oai["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            for t in body["tools"]
        ]
        oai["tool_choice"] = "auto"
    # Disable thinking for cleaner output
    oai["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return oai


def _flatten_content(content) -> str:
    """Flatten Anthropic content (string or list of blocks) to plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", block.get("content", "")))
            else:
                parts.append(str(block))
        return " ".join(parts)
    return str(content)


def openai_to_anthropic(oai_resp: dict) -> dict:
    """Translate OpenAI response to Anthropic messages response format."""
    choice = oai_resp.get("choices", [{}])[0]
    msg = choice.get("message", {})
    text = msg.get("content", "") or ""
    # Strip thinking tokens if present
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    content_blocks = []
    stop_reason = "end_turn"

    # Convert tool_calls → Anthropic tool_use blocks
    tool_calls = msg.get("tool_calls") or []
    if tool_calls:
        if text:
            content_blocks.append({"type": "text", "text": text})
        for tc in tool_calls:
            fn = tc.get("function", {})
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                args = {}
            content_blocks.append({
                "type": "tool_use",
                "id": tc.get("id", "call_0"),
                "name": fn.get("name", ""),
                "input": args,
            })
        stop_reason = "tool_use"
    else:
        content_blocks.append({"type": "text", "text": text})

    finish = choice.get("finish_reason", "stop")
    if finish == "tool_calls":
        stop_reason = "tool_use"

    usage = oai_resp.get("usage", {})
    return {
        "id": oai_resp.get("id", "msg_local"),
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": oai_resp.get("model", MODEL_NAME),
        "stop_reason": stop_reason,
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
            with _no_proxy_opener.open(req, timeout=180) as resp:
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
