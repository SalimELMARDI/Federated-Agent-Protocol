"""Coordinator app factory for Docker entrypoint.

This module is used as the uvicorn app entry point and reads configuration
from environment variables, allowing proper parametrization without complex
shell escaping.
"""

import os

from coordinator_api.main import create_app

# Read participant URLs from environment variables
participant_docs_evaluate_url = os.getenv(
    "PARTICIPANT_DOCS_EVALUATE_URL", "http://participant-docs:8000/evaluate"
)
participant_docs_execute_url = os.getenv(
    "PARTICIPANT_DOCS_EXECUTE_URL", "http://participant-docs:8000/execute"
)
participant_kb_evaluate_url = os.getenv(
    "PARTICIPANT_KB_EVALUATE_URL", "http://participant-kb:8000/evaluate"
)
participant_kb_execute_url = os.getenv(
    "PARTICIPANT_KB_EXECUTE_URL", "http://participant-kb:8000/execute"
)
participant_logs_evaluate_url = os.getenv(
    "PARTICIPANT_LOGS_EVALUATE_URL", "http://participant-logs:8000/evaluate"
)
participant_logs_execute_url = os.getenv(
    "PARTICIPANT_LOGS_EXECUTE_URL", "http://participant-logs:8000/execute"
)

# Create app with configured URLs
app = create_app(
    participant_docs_evaluate_url=participant_docs_evaluate_url,
    participant_docs_execute_url=participant_docs_execute_url,
    participant_kb_evaluate_url=participant_kb_evaluate_url,
    participant_kb_execute_url=participant_kb_execute_url,
    participant_logs_evaluate_url=participant_logs_evaluate_url,
    participant_logs_execute_url=participant_logs_execute_url,
)
