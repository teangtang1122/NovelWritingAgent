"""Helpers for forgiving JSONL parsing."""
from __future__ import annotations

import json
from typing import Any


def clean_jsonl_text(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    return value


def parse_json_line(line: str) -> dict[str, Any] | None:
    text = line.strip().lstrip("\ufeff")
    if not text or text.startswith("//") or text.startswith("#"):
        return None
    if text.startswith("```") or text == "[DONE]":
        return None
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("JSONL line must be an object")
    return parsed


def normalize_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    item_type = str(raw.get("type") or raw.get("item_type") or "").strip()
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        payload = {k: v for k, v in raw.items() if k not in {"type", "item_type"}}
    return {
        "item_type": item_type,
        "operation": str(raw.get("operation") or payload.get("operation") or "upsert").strip() or "upsert",
        "target_type": raw.get("target_type") or payload.get("target_type"),
        "target_id": raw.get("target_id") or payload.get("target_id"),
        "target_name": raw.get("target_name") or payload.get("target_name") or payload.get("name") or payload.get("title"),
        "confidence": raw.get("confidence") or payload.get("confidence"),
        "evidence": raw.get("evidence") or payload.get("evidence"),
        "source_task": raw.get("source_task") or "chapter_cataloging",
        "payload": payload,
    }
