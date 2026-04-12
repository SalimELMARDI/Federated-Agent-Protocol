"""Execution routes for the participant_llm service."""

from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ConfigDict

from fap_core import message_to_dict, parse_inbound_message, to_protocol_http_exception
from fap_core.messages import TaskCreateMessage
from participant_llm.adapters.llm_client import LLMCallError
from participant_llm.service.executor import ParticipantExecutionResult, execute_task_create

router = APIRouter()


class ExecuteResponse(BaseModel):
    """Canonical execution response bundle for participant_llm."""

    model_config = ConfigDict(extra="forbid")

    task_complete: dict[str, object]
    policy_attest: dict[str, object]
    aggregate_submit: dict[str, object]


@router.post("/execute", response_model=ExecuteResponse)
async def execute_message(message: dict[str, object] = Body(...)) -> ExecuteResponse:
    """Execute inbound task-create messages and return governed result messages.

    Returns:
        ExecuteResponse: Governed execution result on success

    Raises:
        HTTPException(503): LLM execution failed (upstream provider error)
        HTTPException(400): Invalid message format or unsupported message type
    """
    try:
        parsed = parse_inbound_message(message)
    except Exception as exc:
        raise to_protocol_http_exception(exc) from exc

    if not isinstance(parsed, TaskCreateMessage):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unsupported_execution_message",
                "message": "participant_llm can only execute 'fap.task.create' messages",
            },
        )

    try:
        result = await execute_task_create(parsed)
    except LLMCallError as exc:
        # Return HTTP 503 for upstream LLM failures (protocol-visible failure)
        # Coordinator will see this as execution failure, not successful completion
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "llm_execution_failed",
                "message": f"LLM provider call failed: {type(exc).__name__}",
                "retryable": True,  # Network/auth errors may be transient
            },
        ) from exc

    return _build_execute_response(result)


def _build_execute_response(result: ParticipantExecutionResult) -> ExecuteResponse:
    """Convert the execution result bundle into canonical JSON-safe message data."""
    return ExecuteResponse(
        task_complete=message_to_dict(result.task_complete_message),
        policy_attest=message_to_dict(result.policy_attest_message),
        aggregate_submit=message_to_dict(result.aggregate_submit_message),
    )
