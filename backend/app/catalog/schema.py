"""`ai_learn` 题库当前四表的 SQLAlchemy Core Schema。"""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB


catalog_metadata = MetaData()

questions = Table(
    "questions",
    catalog_metadata,
    Column("id", Integer, primary_key=True),
    Column("subject", String(50), nullable=False),
    Column("age_group", String(20), nullable=False),
    Column("difficulty", String(20), nullable=False),
    Column("grade", String(20)),
    Column("content", Text, nullable=False),
    Column("options", JSONB),
    Column("correct_answer", Text, nullable=False),
    Column("explanation", Text, nullable=False),
    Column("type", String(30), nullable=False),
    Column("tags", ARRAY(Text)),
    Column("source", String(50), server_default=text("'ai_generated'")),
    Column("batch_id", String(100)),
    Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
    Column("knowledge_fingerprint", JSONB),
    Column("template_id", String(50)),
    Column("variant_group_id", String(50)),
    Column("cognitive_level", String(20)),
    Column("estimated_difficulty", Numeric(3, 2)),
    Column("language", String(10), server_default=text("'zh'")),
    Column("generation_source", String(30), server_default=text("'ai_generated'")),
    Column("quality_score", Integer),
    Column("review_status", String(20), server_default=text("'approved'")),
)
Index("idx_subject_age", questions.c.subject, questions.c.age_group)
Index("idx_difficulty", questions.c.difficulty)
Index("idx_type", questions.c.type)
Index("idx_questions_knowledge_fp", questions.c.knowledge_fingerprint, postgresql_using="gin")
Index("idx_questions_language", questions.c.language)
Index("idx_questions_quality", questions.c.quality_score)
Index("idx_questions_review", questions.c.review_status)

knowledge_points = Table(
    "knowledge_points",
    catalog_metadata,
    Column("id", Integer, primary_key=True),
    Column("subject", String(20), nullable=False),
    Column("age_group", String(10), nullable=False),
    Column("name", String(100), nullable=False),
    Column("parent_id", Integer, ForeignKey("knowledge_points.id")),
    Column("difficulty_range", String(20)),
    Column("description", Text),
    UniqueConstraint("subject", "age_group", "name"),
)
Index("idx_kp_subject_age", knowledge_points.c.subject, knowledge_points.c.age_group)

question_knowledge = Table(
    "question_knowledge",
    catalog_metadata,
    Column(
        "question_id",
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "knowledge_point_id",
        Integer,
        ForeignKey("knowledge_points.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("is_primary", Boolean, server_default=text("false")),
)
Index(
    "idx_qk_primary",
    question_knowledge.c.question_id,
    postgresql_where=question_knowledge.c.is_primary.is_(True),
)

question_stats = Table(
    "question_stats",
    catalog_metadata,
    Column(
        "question_id",
        Integer,
        ForeignKey("questions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("total_attempts", Integer, server_default=text("0")),
    Column("correct_count", Integer, server_default=text("0")),
    Column("correct_rate", Numeric(5, 2)),
    Column("avg_time_seconds", Integer),
    Column("first_seen_at", DateTime),
    Column("last_attempt_at", DateTime),
    Column("calibrated_difficulty", String(20)),
)
