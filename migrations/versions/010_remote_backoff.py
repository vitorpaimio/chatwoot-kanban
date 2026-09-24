"""Retentativa remota compartilhada por conta e retomada de importações antigas."""

from alembic import op

revision = "010"
down_revision = "009"


def upgrade():
    op.execute("""
    ALTER TABLE kb_accounts ADD COLUMN remote_next_attempt timestamptz
      NOT NULL DEFAULT now();
    UPDATE kb_accounts SET import_status='pending'
      WHERE import_requested AND import_status='idle';
    """)


def downgrade():
    op.execute("ALTER TABLE kb_accounts DROP COLUMN remote_next_attempt")
