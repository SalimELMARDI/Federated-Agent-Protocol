"""create coordinator runtime tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260323_2130"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "protocol_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("message_type", sa.String(), nullable=False),
        sa.Column("sender_id", sa.String(), nullable=False),
        sa.Column("recipient_id", sa.String(), nullable=False),
        sa.Column("domain_id", sa.String(), nullable=False),
        sa.Column("trace_id", sa.String(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_message_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_protocol_events_run_id", "protocol_events", ["run_id"])
    op.create_index("ix_protocol_events_task_id", "protocol_events", ["task_id"])
    op.create_index("ix_protocol_events_message_id", "protocol_events", ["message_id"], unique=True)
    op.create_index("ix_protocol_events_message_type", "protocol_events", ["message_type"])
    op.create_index("ix_protocol_events_trace_id", "protocol_events", ["trace_id"])

    op.create_table(
        "run_snapshots",
        sa.Column("run_id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("last_message_type", sa.String(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_run_snapshots_task_id", "run_snapshots", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_run_snapshots_task_id", table_name="run_snapshots")
    op.drop_table("run_snapshots")

    op.drop_index("ix_protocol_events_trace_id", table_name="protocol_events")
    op.drop_index("ix_protocol_events_message_type", table_name="protocol_events")
    op.drop_index("ix_protocol_events_message_id", table_name="protocol_events")
    op.drop_index("ix_protocol_events_task_id", table_name="protocol_events")
    op.drop_index("ix_protocol_events_run_id", table_name="protocol_events")
    op.drop_table("protocol_events")
