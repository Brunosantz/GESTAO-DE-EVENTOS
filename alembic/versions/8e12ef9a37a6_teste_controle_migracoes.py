"""teste_controle_migracoes

Revision ID: 8e12ef9a37a6
Revises: 628022ca30a4
Create Date: 2026-11-09 21:59:09.393208
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8e12ef9a37a6'
down_revision: Union[str, Sequence[str], None] = '628022ca30a4'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        "eventos",
        sa.Column("observacoes", sa.Text(), nullable=True)
    )

def downgrade() -> None:
    op.drop_column("eventos", "observacoes")