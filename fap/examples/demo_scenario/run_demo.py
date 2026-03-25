"""Run the FAP v0.1 alpha demo scenario against a local coordinator."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

DEFAULT_COORDINATOR_URL = "http://127.0.0.1:8011"
DEMO_TASK_PATH = Path(__file__).with_name("create_task.json")


class DemoError(RuntimeError):
    """Raised when the demo script cannot complete successfully."""


def load_demo_task(path: Path) -> dict[str, Any]:
    """Load the demo task JSON and refresh the envelope IDs for a new run."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise DemoError("Demo task JSON must be an object.")

    envelope = data.get("envelope")
    if not isinstance(envelope, dict):
        raise DemoError("Demo task JSON must include an object envelope.")

    envelope["task_id"] = f"task-{uuid4()}"
    envelope["run_id"] = f"run-{uuid4()}"
    envelope["message_id"] = f"msg-{uuid4()}"
    envelope["trace_id"] = f"trace-{uuid4()}"
    envelope["timestamp"] = datetime.now(timezone.utc).isoformat()
    return data


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    expected_status: int,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Send an HTTP request and return parsed JSON with clear error messages."""
    try:
        response = client.request(method, url, json=json_body)
    except httpx.HTTPError as exc:
        raise DemoError(f"{method} {url} failed: {exc}") from exc

    if response.status_code != expected_status:
        raise DemoError(
            f"{method} {url} returned {response.status_code}, expected {expected_status}: "
            f"{response.text}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise DemoError(f"{method} {url} returned invalid JSON.") from exc


def print_summary(
    *,
    run_id: str,
    orchestration: dict[str, Any],
    run_snapshot: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    """Print a compact deterministic summary of the demo result."""
    aggregate_result = orchestration["aggregate_result"]
    aggregate_payload = aggregate_result["payload"]

    print("FAP v0.1 alpha demo")
    print(f"Run ID: {run_id}")
    print()
    print("Evaluations:")
    for entry in orchestration["evaluations"]:
        print(
            f"- {entry['participant']}: {entry['message_type']} "
            f"accepted={entry['accepted']}"
        )

    print()
    print("Executions:")
    for entry in orchestration["executions"]:
        print(
            f"- {entry['participant']}: executed={entry['executed']} "
            f"message_type={entry['message_type']}"
        )

    print()
    print("Final aggregate result:")
    print(f"- message_type: {aggregate_result['envelope']['message_type']}")
    print(f"- participant_count: {aggregate_payload['participant_count']}")
    print("- final_answer:")
    for line in str(aggregate_payload["final_answer"]).splitlines():
        print(f"  {line}")

    print()
    print("Persisted event types:")
    for event in events:
        print(f"- {event['message_type']}")

    print()
    print("Run snapshot:")
    print(f"- status: {run_snapshot['status']}")
    print(f"- message_count: {run_snapshot['message_count']}")
    print(f"- aggregate_results: {len(run_snapshot['aggregate_results'])}")


def parse_args() -> argparse.Namespace:
    """Return CLI args for the local demo runner."""
    parser = argparse.ArgumentParser(description="Run the FAP v0.1 alpha demo scenario.")
    parser.add_argument(
        "--coordinator-url",
        default=DEFAULT_COORDINATOR_URL,
        help="Base URL for the locally running coordinator.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the end-to-end local demo against a configured coordinator."""
    args = parse_args()
    task = load_demo_task(DEMO_TASK_PATH)

    with httpx.Client(timeout=30.0) as client:
        create_response = request_json(
            client,
            "POST",
            f"{args.coordinator_url}/messages",
            expected_status=202,
            json_body=task,
        )
        if not isinstance(create_response, dict):
            raise DemoError("Coordinator create response must be an object.")

        run_id = str(create_response["run_id"])
        orchestration = request_json(
            client,
            "POST",
            f"{args.coordinator_url}/runs/{run_id}/orchestrate/summary-merge",
            expected_status=200,
        )
        run_snapshot = request_json(
            client,
            "GET",
            f"{args.coordinator_url}/runs/{run_id}",
            expected_status=200,
        )
        events_response = request_json(
            client,
            "GET",
            f"{args.coordinator_url}/runs/{run_id}/events",
            expected_status=200,
        )

    if not isinstance(orchestration, dict):
        raise DemoError("Orchestration response must be an object.")
    if not isinstance(run_snapshot, dict):
        raise DemoError("Run snapshot response must be an object.")
    if not isinstance(events_response, list):
        raise DemoError("Events response must be a list.")

    print_summary(
        run_id=run_id,
        orchestration=orchestration,
        run_snapshot=run_snapshot,
        events=events_response,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
