"""seed the canonical equation knowledge taxonomy

Revision ID: lp_0015_equation_knowledge_nodes
Revises: lp_0014_adaptive_generation
"""

from alembic import op


revision = "lp_0015_equation_knowledge_nodes"
down_revision = "lp_0014_adaptive_generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO subjects (code, name, icon, sort_order)
        VALUES ('SUBJ_MATH', '数学', 'calculator', 10)
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO age_groups (code, name, min_age, max_age, theme_config)
        VALUES ('AGE_12_14', '12-14岁(初中)', 12, 14, '{}'::jsonb)
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE knowledge_nodes AS node
        SET code = canonical.canonical_code
        FROM (
            VALUES
                ('00000000-0000-4000-8000-000000000101'::uuid, 'equation_equivalence'),
                ('00000000-0000-4000-8000-000000000102'::uuid, 'distributive_expansion'),
                ('00000000-0000-4000-8000-000000000103'::uuid, 'combine_like_terms'),
                ('00000000-0000-4000-8000-000000000104'::uuid, 'move_terms_sign'),
                ('00000000-0000-4000-8000-000000000105'::uuid, 'normalize_coefficient'),
                ('00000000-0000-4000-8000-000000000106'::uuid, 'equation_word_modeling')
        ) AS canonical(seed_id, canonical_code)
        WHERE node.id = canonical.seed_id
          AND node.code LIKE 'legacy-%'
        """
    )
    op.execute(
        """
        INSERT INTO knowledge_nodes (
            id, code, title, description, subject_code, age_group_code,
            difficulty_level, content_type, content_body, estimated_minutes,
            prerequisites, sort_order, is_active, created_at, updated_at
        ) VALUES
            ('00000000-0000-4000-8000-000000000101', 'equation_equivalence',
             '等式与等价变形', '理解等式两边进行相同运算时解集保持不变。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_EASY', 'TYPE_READ',
             '一元一次方程的等价变形基础。', 10, ARRAY[]::uuid[], 101, TRUE, NOW(), NOW()),
            ('00000000-0000-4000-8000-000000000102', 'distributive_expansion',
             '去括号与分配律', '正确使用分配律展开一元一次方程。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_MEDIUM', 'TYPE_READ',
             '使用分配律去括号。', 10,
             ARRAY['00000000-0000-4000-8000-000000000101'::uuid], 102, TRUE, NOW(), NOW()),
            ('00000000-0000-4000-8000-000000000103', 'combine_like_terms',
             '合并同类项', '识别并正确合并方程两边的同类项。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_MEDIUM', 'TYPE_READ',
             '合并同类项并保持等式等价。', 10,
             ARRAY['00000000-0000-4000-8000-000000000101'::uuid], 103, TRUE, NOW(), NOW()),
            ('00000000-0000-4000-8000-000000000104', 'move_terms_sign',
             '移项与符号变化', '理解移项是等式两边同运算并正确处理符号。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_MEDIUM', 'TYPE_READ',
             '移项时关注符号变化。', 10,
             ARRAY['00000000-0000-4000-8000-000000000101'::uuid], 104, TRUE, NOW(), NOW()),
            ('00000000-0000-4000-8000-000000000105', 'normalize_coefficient',
             '系数化一', '将未知数系数化为一并保持方程等价。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_MEDIUM', 'TYPE_READ',
             '等式两边同除以未知数系数。', 10,
             ARRAY['00000000-0000-4000-8000-000000000101'::uuid], 105, TRUE, NOW(), NOW()),
            ('00000000-0000-4000-8000-000000000106', 'equation_word_modeling',
             '一元一次方程建模', '从文字关系中确定未知数并建立一元一次方程。',
             'SUBJ_MATH', 'AGE_12_14', 'DIFF_HARD', 'TYPE_READ',
             '将实际问题中的等量关系表示为方程。', 15,
             ARRAY['00000000-0000-4000-8000-000000000101'::uuid], 106, TRUE, NOW(), NOW())
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    # The rows are backward-compatible with lp_0014. Preserve learning state and
    # let the idempotent upgrade reuse them instead of deleting runtime facts.
    pass
