"""Create pricing_results table.

Revision ID: 20260803_0001
Revises:
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pricing_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("bid_price", sa.Float(), nullable=False),
        sa.Column("recommended_dealer_bid", sa.Float(), nullable=False),
        sa.Column("estimated_turnover_days", sa.Integer(), nullable=False),
        sa.Column("target_margin_pct", sa.Float(), nullable=False),
        sa.Column("price_low", sa.Float(), nullable=False),
        sa.Column("price_high", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
        sa.Column(
            "model_version",
            sa.String(length=64),
            server_default="rules-v0",
            nullable=False,
        ),
        sa.Column("meta_json", sa.Text(), server_default="{}", nullable=False),
        sa.Column("priced_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pricing_results_external_id",
        "pricing_results",
        ["external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_pricing_results_external_id", table_name="pricing_results")
    op.drop_table("pricing_results")
