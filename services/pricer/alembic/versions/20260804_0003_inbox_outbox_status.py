"""Add inbox/outbox claim statuses.

Revision ID: 20260804_0003
Revises: 20260803_0002
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0003"
down_revision: str | None = "20260803_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "processed_events",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="completed",
        ),
    )
    op.add_column(
        "processed_events",
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "processed_events",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE processed_events "
            "SET status='completed', completed_at=processed_at, claimed_at=NULL"
        )
    )
    op.create_index(
        "ix_processed_events_status_claimed",
        "processed_events",
        ["status", "claimed_at"],
    )
    op.drop_column("processed_events", "processed_at")

    op.add_column(
        "outbox_messages",
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "outbox_messages",
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE outbox_messages SET status='published' "
            "WHERE published_at IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE outbox_messages SET status='pending' " "WHERE published_at IS NULL"
        )
    )
    op.create_index(
        "ix_outbox_messages_status_created",
        "outbox_messages",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_outbox_messages_status_created",
        table_name="outbox_messages",
    )
    op.drop_column("outbox_messages", "claimed_at")
    op.drop_column("outbox_messages", "status")

    op.add_column(
        "processed_events",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE processed_events "
            "SET processed_at=COALESCE(completed_at, claimed_at, UTC_TIMESTAMP())"
        )
    )
    op.alter_column("processed_events", "processed_at", nullable=False)
    op.drop_index(
        "ix_processed_events_status_claimed",
        table_name="processed_events",
    )
    op.drop_column("processed_events", "completed_at")
    op.drop_column("processed_events", "claimed_at")
    op.drop_column("processed_events", "status")
