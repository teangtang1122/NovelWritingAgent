"""Tiny OpenAI-compatible streaming server for local E2E smoke tests."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


CATALOGING_JSONL = [
    {
        "type": "chapter_summary",
        "payload": {
            "summary_text": "林澈在雾港发现潮汐钟异常，决定调查港口旧塔。",
            "key_events": ["潮汐钟倒转", "林澈进入旧塔"],
        },
        "confidence": 0.98,
        "evidence": "潮汐钟倒着走；林澈推门进塔。",
    },
    {
        "type": "character_create",
        "target_name": "林澈",
        "payload": {
            "name": "林澈",
            "role_type": "protagonist",
            "personality": "谨慎、好奇，遇到异常会先记录再行动。",
            "current_location": "雾港旧塔",
            "physical_state": "健康",
            "mental_state": "警觉",
        },
        "confidence": 0.95,
        "evidence": "林澈记录潮汐钟异常并独自进入旧塔。",
    },
    {
        "type": "worldbuilding_create",
        "target_name": "雾港潮汐钟",
        "payload": {
            "dimension": "culture",
            "title": "雾港潮汐钟",
            "content": "雾港居民依靠潮汐钟判断海雾与潮汐，钟面倒转被视为灾兆。",
            "status": "active",
            "confidence": 0.94,
        },
        "confidence": 0.94,
        "evidence": "镇民说潮汐钟倒转是不祥征兆。",
    },
    {
        "type": "outline_create",
        "target_name": "第1章 潮汐钟倒转",
        "payload": {
            "title": "第1章 潮汐钟倒转",
            "summary": "林澈发现雾港潮汐钟倒转并进入旧塔调查。",
            "related_characters": ["林澈"],
        },
        "confidence": 0.93,
        "evidence": "本章围绕潮汐钟异常和旧塔调查展开。",
    },
    {
        "type": "chapter_link",
        "payload": {
            "character_names": ["林澈"],
            "worldbuilding_titles": ["雾港潮汐钟"],
            "outline_title": "第1章 潮汐钟倒转",
        },
        "confidence": 0.92,
        "evidence": "林澈、潮汐钟和旧塔调查均在本章出现。",
    },
]


def _stream_chunk(content: str) -> bytes:
    payload = {"choices": [{"delta": {"content": content}, "index": 0, "finish_reason": None}]}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length") or "0")
        if length:
            self.rfile.read(length)
        if not self.path.endswith("/chat/completions"):
            self.send_error(404)
            return

        body = "\n".join(json.dumps(item, ensure_ascii=False) for item in CATALOGING_JSONL) + "\n"
        chunks = [_stream_chunk(piece) for piece in [body[:80], body[80:220], body[220:]] if piece]
        chunks.append(b"data: [DONE]\n\n")
        response_body = b"".join(chunks)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        for chunk in chunks:
            self.wfile.write(chunk)
            self.wfile.flush()

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 18080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
