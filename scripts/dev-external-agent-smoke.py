#!/usr/bin/env python3
"""Development smoke test for external Agent live session.

Simulates an external MCP client (like Claude Code) interacting with
the Moshu backend through the Agent run API.

Usage:
    python scripts/dev-external-agent-smoke.py --project-id YOUR_PROJECT_ID

This script requires a running Moshu backend.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import requests

BASE_URL = "http://127.0.0.1:8765/api/v1"


def main() -> None:
    parser = argparse.ArgumentParser(description="External Agent smoke test")
    parser.add_argument("--project-id", required=True, help="Project ID to use")
    parser.add_argument("--base-url", default=BASE_URL, help="Backend API base URL")
    args = parser.parse_args()

    project_id = args.project_id
    base_url = args.base_url.rstrip("/")

    print(f"[smoke] Testing against {base_url}")
    print(f"[smoke] Project ID: {project_id}")

    # Step 1: Create a run
    print("\n[1] Creating Agent run...")
    resp = requests.post(
        f"{base_url}/projects/{project_id}/agent-runs",
        json={"source": "mcp", "client_name": "smoke-test", "title": "Smoke Test Run"},
    )
    resp.raise_for_status()
    run_data = resp.json()["data"]
    run_id = run_data["id"]
    print(f"    Run created: {run_id} (status: {run_data['status']})")

    # Step 2: Report plan
    print("\n[2] Reporting plan...")
    resp = requests.post(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
        json={
            "event_type": "plan",
            "status": "ok",
            "message": "Plan: 3 steps",
            "payload_json": json.dumps({"plan": ["Read context", "Draft content", "Finish"]}),
        },
    )
    resp.raise_for_status()
    print(f"    Plan reported (sequence: {resp.json()['data']['sequence']})")

    # Step 3: Report progress
    print("\n[3] Reporting progress...")
    resp = requests.post(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
        json={
            "event_type": "progress",
            "status": "ok",
            "message": "Reading project context...",
        },
    )
    resp.raise_for_status()
    print(f"    Progress reported")

    # Step 4: Stream draft chunks
    print("\n[4] Streaming draft chunks...")
    for i in range(3):
        resp = requests.post(
            f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
            json={
                "event_type": "draft_chunk",
                "status": "ok",
                "message": f"Chunk {i}",
                "payload_json": json.dumps({
                    "content": f"This is draft chunk {i}. " * 10,
                    "chunk_index": i,
                }),
            },
        )
        resp.raise_for_status()
        print(f"    Chunk {i} streamed")
        time.sleep(0.5)

    # Step 5: Mark draft ready
    print("\n[5] Marking draft ready...")
    resp = requests.post(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
        json={
            "event_type": "draft_ready",
            "status": "ok",
            "message": "Draft ready: chapter",
            "payload_json": json.dumps({
                "content_type": "chapter",
                "summary": "Smoke test chapter, 3 chunks",
            }),
        },
    )
    resp.raise_for_status()
    print(f"    Draft marked ready")

    # Step 6: Finish run
    print("\n[6] Finishing run...")
    resp = requests.post(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
        json={
            "event_type": "run_finished",
            "status": "ok",
            "message": "Smoke test completed successfully",
        },
    )
    resp.raise_for_status()
    print(f"    Run finished")

    # Step 7: Verify events
    print("\n[7] Verifying events...")
    resp = requests.get(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}/events",
    )
    resp.raise_for_status()
    events = resp.json()["data"]["items"]
    event_types = [e["event_type"] for e in events]
    print(f"    Total events: {len(events)}")
    print(f"    Event types: {event_types}")

    # Verify all major milestones
    required = ["plan", "progress", "draft_chunk", "draft_ready", "run_finished"]
    missing = [t for t in required if t not in event_types]
    if missing:
        print(f"\n[FAIL] Missing events: {missing}")
        sys.exit(1)

    # Step 8: Check run status
    print("\n[8] Checking final run status...")
    resp = requests.get(
        f"{base_url}/projects/{project_id}/agent-runs/{run_id}",
    )
    resp.raise_for_status()
    final_status = resp.json()["data"]["status"]
    print(f"    Final status: {final_status}")

    if final_status != "completed":
        print(f"\n[FAIL] Expected status 'completed', got '{final_status}'")
        sys.exit(1)

    print("\n[PASS] All smoke test steps completed successfully!")


if __name__ == "__main__":
    main()
