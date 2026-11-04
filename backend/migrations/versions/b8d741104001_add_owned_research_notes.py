"""Add dormant source-pinned notes; preserve existing ownership tables and data."""
from alembic import op
import sqlalchemy as sa

revision = "b8d741104001"
down_revision = "a7c730103001"
branch_labels = depends_on = None


def upgrade():
    op.create_table("research_notes",
        sa.Column("artifact_id", sa.String(36, collation="C"), sa.ForeignKey("research_artifacts.id"), primary_key=True),
        sa.Column("owner_id", sa.String(36, collation="C"), sa.ForeignKey("research_accounts.id"), nullable=False),
        sa.Column("session_id", sa.String(36, collation="C"), nullable=False),
        sa.Column("session_revision", sa.BigInteger(), nullable=False),
        sa.Column("artifact_revision", sa.BigInteger(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_pin", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id", "session_id"], ["research_sessions.owner_id", "research_sessions.id"],
                                name="fk_research_note_owned_session"),
        sa.CheckConstraint("session_revision > 0 AND artifact_revision > 0", name="ck_research_note_revisions"),
        sa.CheckConstraint("octet_length(body) BETWEEN 1 AND 16384 AND octet_length(source_pin) BETWEEN 1 AND 16384",
                           name="ck_research_note_size"))


def downgrade():
    raise RuntimeError("Note schema is forward-only; removal requires separately approved recovery.")
