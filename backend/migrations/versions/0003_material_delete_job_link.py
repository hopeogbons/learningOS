"""persist material deletion job link
Revision ID: 0003_material_delete
Revises: 0002_durable_guards
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003_material_delete"
down_revision: Union[str, None] = "0002_durable_guards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("materials", sa.Column("deletion_job_id", sa.String(length=36), nullable=True))


def downgrade() -> None:
    op.drop_column("materials", "deletion_job_id")
