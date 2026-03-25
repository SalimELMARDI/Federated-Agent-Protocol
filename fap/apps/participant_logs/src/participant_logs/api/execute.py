"""Execution routes for the participant logs service."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ConfigDict

from fap_core import message_to_dict, parse_inbound_message, to_protocol_http_exception
from fap_core.messages import TaskCreateMessage
from participant_logs.service.executor import ParticipantExecutionResult, execute_task_create

router = APIRouter()


class ExecuteResponse(BaseModel):
    """Canonical execution response bundle for participant_logs."""

    model_config = ConfigDict(extra="forbid")

    task_complete: dict[str, object]
    policy_attest: dict[str, object]
    aggregate_submit: dict[str, object]


@router.post("/execute", response_model=ExecuteResponse)
async def execute_message(message: dict[str, object] = Body(...)) -> ExecuteResponse:
    """Execute inbound task-create messages and return governed result messages."""
    try:
        parsed = parse_inbound_message(message)
    except Exception as exc:
        raise to_protocol_http_exception(exc) from exc

    if not isinstance(parsed, TaskCreateMessage):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unsupported_execution_message",
                "message": "participant_logs can only execute 'fap.task.create' messages",
            },
        )

    return _build_execute_response(execute_task_create(parsed))


def _build_execute_response(result: ParticipantExecutionResult) -> ExecuteResponse:
    """Convert the execution result bundle into canonical JSON-safe message data."""
    return ExecuteResponse(
        task_complete=message_to_dict(result.task_complete_message),
        policy_attest=message_to_dict(result.policy_attest_message),
        aggregate_submit=message_to_dict(result.aggregate_submit_message),
    )
