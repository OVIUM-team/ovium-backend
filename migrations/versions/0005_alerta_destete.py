"""Registra las alertas de destete generadas por el trabajo programado."""
from alembic import op
import sqlalchemy as sa

revision = "0005_alerta_destete"
down_revision = "0004_ajuste_modelo"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alerta_destete",
        sa.Column("parto_id", sa.Uuid(as_uuid=False), sa.ForeignKey("parto.id"), primary_key=True),
    )


def downgrade():
    op.drop_table("alerta_destete")
