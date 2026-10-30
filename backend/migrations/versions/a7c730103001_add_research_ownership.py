"""Add dormant research ownership metadata; no existing table/data changes."""
from alembic import op
import sqlalchemy as sa

revision = "a7c730103001"
down_revision = "f94c6f41e0cb"
branch_labels = depends_on = None


def upgrade():
    op.create_table("research_accounts",
        sa.Column("id", sa.String(36, collation="C"), primary_key=True),
        sa.Column("issuer", sa.String(2048, collation="C"), nullable=False),
        sa.Column("subject", sa.String(255, collation="C"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("token_cutoff", sa.BigInteger(), nullable=False, server_default=sa.text("-1")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("issuer", "subject", name="uq_research_account_identity"),
        sa.CheckConstraint("token_cutoff >= -1 AND revision > 0", name="ck_research_account_lifecycle"))
    op.create_table("research_sessions",
        sa.Column("id", sa.String(36, collation="C"), primary_key=True),
        sa.Column("owner_id", sa.String(36, collation="C"), sa.ForeignKey("research_accounts.id"), nullable=False),
        sa.Column("request_key", sa.String(128, collation="C"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.UniqueConstraint("owner_id", "id", name="uq_research_session_owner"),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_research_session_request"),
        sa.CheckConstraint("state IN ('active', 'revoked') AND revision > 0", name="ck_research_session_lifecycle"))
    op.create_table("research_artifacts",
        sa.Column("id", sa.String(36, collation="C"), primary_key=True),
        sa.Column("owner_id", sa.String(36, collation="C"), sa.ForeignKey("research_accounts.id"), nullable=False),
        sa.Column("session_id", sa.String(36, collation="C"), nullable=False),
        sa.Column("request_key", sa.String(128, collation="C"), nullable=False),
        sa.Column("session_revision", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default=sa.text("'reserved'")),
        sa.Column("revision", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
        sa.ForeignKeyConstraint(["owner_id", "session_id"], ["research_sessions.owner_id", "research_sessions.id"],
                                name="fk_research_artifact_owned_session"),
        sa.UniqueConstraint("owner_id", "request_key", name="uq_research_artifact_request"),
        sa.CheckConstraint("state IN ('reserved', 'revoked') AND revision > 0 AND session_revision > 0",
                           name="ck_research_artifact_lifecycle"))


def downgrade():
    raise RuntimeError("Ownership schema is forward-only; removal requires separately approved recovery.")
