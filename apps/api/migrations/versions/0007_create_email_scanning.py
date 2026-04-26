"""create email_accounts and purchase_candidates tables

email_accounts — connected inboxes (Gmail, Outlook, IMAP) scanned for order
confirmation emails. Credentials stored encrypted in JSONB; only read access used.

purchase_candidates — potential purchases detected by email scanning and surfaced
to admin for review. Confirming a candidate creates a collection_item and resolves
the matching wanted_list entry.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_PROVIDER = ("gmail", "outlook", "icloud", "yahoo", "generic_imap")
_AUTH_TYPE = ("oauth", "app_password")
_SCAN_FREQ = ("daily", "hourly", "manual")
_PC_STATUS = ("pending_review", "confirmed", "dismissed")


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # email_accounts — one row per connected inbox; credentials encrypted at rest
    # -------------------------------------------------------------------------
    op.create_table(
        "email_accounts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            PGUUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("email_address", sa.String(255), nullable=False),
        sa.Column("auth_type", sa.String(30), nullable=False),
        # Encrypted OAuth tokens (Gmail, Outlook)
        sa.Column("oauth_tokens", JSONB()),
        # Encrypted IMAP credentials (iCloud, Yahoo, generic)
        sa.Column("imap_config", JSONB()),
        sa.Column(
            "scan_frequency",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'daily'"),
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("last_scan_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("last_scan_status", sa.String(50)),
        sa.Column(
            "added_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_check_constraint(
        "ck_email_accounts_provider",
        "email_accounts",
        f"provider IN {_PROVIDER}",
    )
    op.create_check_constraint(
        "ck_email_accounts_auth_type",
        "email_accounts",
        f"auth_type IN {_AUTH_TYPE}",
    )
    op.create_check_constraint(
        "ck_email_accounts_scan_frequency",
        "email_accounts",
        f"scan_frequency IN {_SCAN_FREQ}",
    )

    op.create_index("idx_email_accounts_user_id", "email_accounts", ["user_id"])
    op.create_index("idx_email_accounts_is_enabled", "email_accounts", ["is_enabled"])

    # -------------------------------------------------------------------------
    # purchase_candidates — email-detected purchases awaiting admin review
    # -------------------------------------------------------------------------
    op.create_table(
        "purchase_candidates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "wanted_id",
            sa.BigInteger(),
            sa.ForeignKey("wanted_list.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "email_account_id",
            sa.BigInteger(),
            sa.ForeignKey("email_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("retailer_name", sa.String(100)),
        sa.Column("detected_price", sa.Numeric(8, 2)),
        sa.Column("order_date", sa.Date()),
        # Provider-specific message ID for deduplication
        sa.Column("email_message_id", sa.String(255)),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'pending_review'"),
        ),
        sa.Column(
            "detected_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_check_constraint(
        "ck_purchase_candidates_status",
        "purchase_candidates",
        f"status IN {_PC_STATUS}",
    )
    op.create_check_constraint(
        "ck_purchase_candidates_price",
        "purchase_candidates",
        "detected_price IS NULL OR detected_price >= 0",
    )

    # Deduplicate on message ID per account
    op.create_unique_constraint(
        "uq_purchase_candidates_account_message",
        "purchase_candidates",
        ["email_account_id", "email_message_id"],
    )

    op.create_index("idx_purchase_candidates_wanted_id", "purchase_candidates", ["wanted_id"])
    op.create_index(
        "idx_purchase_candidates_email_account_id",
        "purchase_candidates",
        ["email_account_id"],
    )
    op.create_index("idx_purchase_candidates_status", "purchase_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("idx_purchase_candidates_status", table_name="purchase_candidates")
    op.drop_index("idx_purchase_candidates_email_account_id", table_name="purchase_candidates")
    op.drop_index("idx_purchase_candidates_wanted_id", table_name="purchase_candidates")
    op.drop_constraint(
        "uq_purchase_candidates_account_message", "purchase_candidates", type_="unique"
    )
    op.drop_constraint("ck_purchase_candidates_price", "purchase_candidates", type_="check")
    op.drop_constraint("ck_purchase_candidates_status", "purchase_candidates", type_="check")
    op.drop_table("purchase_candidates")

    op.drop_index("idx_email_accounts_is_enabled", table_name="email_accounts")
    op.drop_index("idx_email_accounts_user_id", table_name="email_accounts")
    op.drop_constraint("ck_email_accounts_scan_frequency", "email_accounts", type_="check")
    op.drop_constraint("ck_email_accounts_auth_type", "email_accounts", type_="check")
    op.drop_constraint("ck_email_accounts_provider", "email_accounts", type_="check")
    op.drop_table("email_accounts")
