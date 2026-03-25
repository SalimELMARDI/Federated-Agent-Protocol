"""Evaluation routes for the participant docs service."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, status

from fap_core import message_to_dict, parse_inbound_message, to_protocol_http_exception
from fap_core.messages import TaskCreateMessage
from participant_docs.service.evaluator import evaluate_task_create

router = APIRouter()


@router.post("/evaluate")
async def evaluate_message(message: dict[str, object] = Body(...)) -> dict[str, object]:
    """Evaluate inbound task-create messages and return a canonical FAP decision message."""
    try:
        parsed = parse_inbound_message(message)
    except Exception as exc:
        raise to_protocol_http_exception(exc) from exc

    if not isinstance(parsed, TaskCreateMessage):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unsupported_evaluation_message",
                "message": "participant_docs can only evaluate 'fap.task.create' messages",
            },
        )

    decision = evaluate_task_create(parsed)
    return message_to_dict(decision)
