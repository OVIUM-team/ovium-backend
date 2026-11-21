"""Mediciones de evaluacion y dias de lactancia por rancho."""
from alembic import op
import sqlalchemy as sa

revision = "0004_ajuste_modelo"
down_revision = "0003_auditoria"
branch_labels = None
depends_on = None


def upgrade():
    # Valores previos distintos de 60/75/90 requieren una decision del equipo;
    # el CHECK falla sin convertir ni perder silenciosamente esos datos.
    with op.batch_alter_table("rancho") as batch:
        batch.alter_column("dias_lactancia", existing_type=sa.Integer(), existing_nullable=False, server_default="75")
        batch.create_check_constraint("ck_rancho_dias_lactancia", "dias_lactancia IN (60,75,90)")
    with op.batch_alter_table("pesaje") as batch:
        batch.add_column(sa.Column("circunferencia_testicular", sa.Numeric(8, 2)))
        batch.add_column(sa.Column("peso_evaluacion", sa.Numeric(8, 2)))
        batch.create_check_constraint("ck_pesaje_circunferencia", "circunferencia_testicular IS NULL OR circunferencia_testicular > 0")
        batch.create_check_constraint("ck_pesaje_evaluacion", "peso_evaluacion IS NULL OR peso_evaluacion > 0")


def downgrade():
    with op.batch_alter_table("pesaje") as batch:
        batch.drop_constraint("ck_pesaje_evaluacion", type_="check")
        batch.drop_constraint("ck_pesaje_circunferencia", type_="check")
        batch.drop_column("peso_evaluacion")
        batch.drop_column("circunferencia_testicular")
    with op.batch_alter_table("rancho") as batch:
        batch.drop_constraint("ck_rancho_dias_lactancia", type_="check")
        batch.alter_column("dias_lactancia", existing_type=sa.Integer(), existing_nullable=False, server_default=None)
