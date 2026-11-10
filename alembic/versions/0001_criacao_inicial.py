"""Criação inicial das tabelas do Gestão de Eventos."""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_criacao_inicial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("perfil", sa.String(length=30), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.UniqueConstraint("nome"),
    )

    op.create_table(
        "eventos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(length=150), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("data_inicio", sa.DateTime(), nullable=False),
        sa.Column("data_fim", sa.DateTime(), nullable=False),
        sa.Column("capacidade", sa.Integer(), nullable=False),
        sa.Column("preco", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("organizador_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("categoria_id", sa.Integer(), sa.ForeignKey("categorias.id"), nullable=True),
    )

    op.create_table(
        "inscricoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("evento_id", sa.Integer(), sa.ForeignKey("eventos.id"), nullable=False),
        sa.Column("participante_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("data_inscricao", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
    )

    op.create_table(
        "certificados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("titulo", sa.String(length=180), nullable=False),
        sa.Column("carga_horaria", sa.Integer(), nullable=False),
        sa.Column("data_emissao", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("inscricao_id", sa.Integer(), sa.ForeignKey("inscricoes.id"), nullable=False),
        sa.UniqueConstraint("codigo"),
        sa.UniqueConstraint("inscricao_id"),
    )
    op.create_index("ix_certificados_codigo", "certificados", ["codigo"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_certificados_codigo", table_name="certificados")
    op.drop_table("certificados")
    op.drop_table("inscricoes")
    op.drop_table("eventos")
    op.drop_table("categorias")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
