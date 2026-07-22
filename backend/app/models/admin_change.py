"""管理变更审计表契约。"""

from sqlalchemy import Column, DateTime, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.models import Base


class AdminChangeAudit(Base):
    __tablename__ = "admin_change_audits"
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(30), nullable=False)
    entity_type = Column(String(30), nullable=False)
    entity_id = Column(String(64), nullable=False)
    reason = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False)
    request_id = Column(String(100), nullable=False)
    before_summary = Column(JSONB, nullable=False)
    after_summary = Column(JSONB, nullable=False)
    impact_scope = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    __table_args__ = (Index("ix_admin_change_entity", "entity_type", "entity_id", "created_at"),)
