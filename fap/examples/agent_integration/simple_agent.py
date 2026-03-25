"""Minimal external Python agent example built on top of the FAP client."""

from __future__ import annotations

import argparse

from fap_client import FAPClient, FAPClientError


def build_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the simple agent example."""
    parser = argparse.ArgumentParser(description="Minimal external Python agent using FAP")
    parser.add_argument(
        "question",
        nargs="?",
        default="privacy",
        help="Question to send through the coordinator /ask capability.",
    )
    parser.add_argument(
        "--coordinator-url",
        default="http://127.0.0.1:8011",
        help="Base URL for the running FAP coordinator.",
    )
    return parser


def main() -> int:
    """Run the simple external-agent example."""
    args = build_parser().parse_args()

    try:
        with FAPClient(args.coordinator_url) as client:
            ask_response = client.ask(args.question)
            run_snapshot = client.get_run(ask_response.run_id)
            events = client.get_events(ask_response.run_id)
    except FAPClientError as exc:
        print(f"FAP agent example failed: {exc}")
        return 1

    print("FAP external agent example")
    print(f"Question: {args.question}")
    print(f"Run ID: {ask_response.run_id}")
    print("Final answer:")
    print(f"  {ask_response.final_answer.replace(chr(10), chr(10) + '  ')}")
    print("Accepted participants:")
    if run_snapshot.accepted_participants:
        for participant in run_snapshot.accepted_participants:
            print(f"- {participant}")
    else:
        print("- none")
    print("Persisted event types:")
    for message_type in events.message_types():
        print(f"- {message_type}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
