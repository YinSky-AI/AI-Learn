# -*- coding: utf-8 -*-
"""
题库迁移脚本

将 sql/ 目录下的 batch_*.json 和 pipeline_*.json 题目数据迁移到 learning_platform 数据库，
自动按 (学科, 年龄段, 难度) 聚类生成 KnowledgeNode 知识点节点，并将题目关联到对应节点。

特性：
- 幂等执行：KnowledgeNode 使用 UUID5 生成固定 ID；题目按内容+答案去重
- 分批写入：每 200 题 flush 一次，控制内存和事务大小
- 数据清洗：自动处理缺失字段（从文件名推断）、中文字段映射、选项格式转换
- 复用受 Alembic 版本管理的 canonical ORM Table，只执行数据导入

用法：
    cd backend
    python migrate_questions.py

连接配置：
    复用 app.core.config.settings，支持 DATABASE_URL_FILE secret 注入。
"""

import asyncio
import glob
import json
import os
import re
import uuid
import sys
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.content import KnowledgeNode, Question
from app.core.config import settings
from app.core.schema_version import SchemaVersionError, verify_schema_target

# ---------------------------------------------------------------------------
# 数据库连接
# ---------------------------------------------------------------------------
DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ---------------------------------------------------------------------------
# 表契约（由 Alembic revision 与 canonical ORM 共同管理）
# ---------------------------------------------------------------------------
knowledge_nodes_table = KnowledgeNode.__table__
questions_table = Question.__table__


def describe_database_target(database_url: str) -> str:
    """仅返回脱敏 host/database，不输出用户、密码或完整 DSN。"""

    parsed = make_url(database_url)
    return f"host={parsed.host or ''} database={parsed.database or ''}"


async def ensure_schema_ready() -> None:
    """在读取或写入题目数据前要求主业务库已处于批准 head。"""

    await verify_schema_target(engine, "primary", policy="strict")

# ---------------------------------------------------------------------------
# 映射字典
# ---------------------------------------------------------------------------
SUBJECT_MAP = {
    "math": "SUBJ_MATH",
    "science": "SUBJ_SCIENCE",
    "chinese": "SUBJ_CHINESE",
    "english": "SUBJ_ENGLISH",
    "physics": "SUBJ_PHYSICS",
    "chemistry": "SUBJ_CHEMISTRY",
    "biology": "SUBJ_BIOLOGY",
    "history": "SUBJ_HISTORY",
    "geography": "SUBJ_GEOGRAPHY",
    "politics": "SUBJ_POLITICS",
    "art": "SUBJ_ART",
    "programming": "SUBJ_PROGRAMMING",
}

SUBJECT_NAME_MAP = {
    "math": "数学",
    "science": "科学",
    "chinese": "语文",
    "english": "英语",
    "physics": "物理",
    "chemistry": "化学",
    "biology": "生物",
    "history": "历史",
    "geography": "地理",
    "politics": "政治",
    "art": "美术",
    "programming": "编程",
}

# 中文 subject 映射（用于数据清洗）
SUBJECT_CN_MAP = {
    "数学": "math",
    "科学": "science",
    "语文": "chinese",
    "英语": "english",
    "物理": "physics",
    "化学": "chemistry",
    "生物": "biology",
    "历史": "history",
    "地理": "geography",
    "政治": "politics",
    "美术": "art",
    "编程": "programming",
}

AGE_GROUP_MAP = {
    "6-8": "AGE_06_08",
    "9-12": "AGE_09_11",
    "13-15": "AGE_12_14",
    "16-18": "AGE_15_18",
}

DIFFICULTY_MAP = {
    "beginner": "DIFF_EASY",
    "intermediate": "DIFF_MEDIUM",
    "advanced": "DIFF_HARD",
}

DIFFICULTY_NAME_MAP = {
    "beginner": "简单",
    "intermediate": "中等",
    "advanced": "困难",
}

# 中文 difficulty 映射（用于数据清洗）
DIFFICULTY_CN_MAP = {
    "简单": "beginner",
    "中等": "intermediate",
    "困难": "advanced",
}

QUESTION_TYPE_MAP = {
    "single_choice": "CHOICE",
    "multiple_choice": "MULTIPLE_CHOICE",
    "fill_blank": "FILL_BLANK",
    "true_false": "CHOICE",
    "short_answer": "FILL_BLANK",
}

# 中文题型映射（用于数据清洗）
QUESTION_TYPE_CN_MAP = {
    "单选题": "single_choice",
    "多选题": "multiple_choice",
    "填空题": "fill_blank",
    "判断题": "true_false",
    "简答题": "short_answer",
}

# 文件名正则：提取 subject 和 age_group
# 匹配 batch_{subject}_{age_group}.json / batch_{subject}_{age_group}_supplement.json 等
FILENAME_RE = re.compile(r"^(?:batch|batch_final|batch_fix)_(\w+?)_(\d+-\d+)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def parse_filename(filename):
    """
    从文件名中提取 subject 和 age_group。

    支持格式：
    - batch_math_6-8.json
    - batch_math_6-8_supplement.json
    - batch_final_math_6-8.json
    - batch_fix_math_6-8.json

    返回 (subject, age_group) 或 (None, None)。
    """
    name = os.path.splitext(filename)[0]
    m = FILENAME_RE.match(name)
    if m:
        return m.group(1).lower(), m.group(2)
    return None, None


def clean_subject(val):
    """
    清洗 subject 字段，统一转换为英文小写编码。
    兼容原始值（如 english）和编码值（如 SUBJ_ENGLISH）。
    """
    if not val:
        return None
    val = str(val).strip().lower()
    # 原始值直接匹配
    if val in SUBJECT_MAP:
        return val
    # 编码值反向映射（如 SUBJ_MATH -> math）
    for raw, code in SUBJECT_MAP.items():
        if val == code.lower():
            return raw
    # 尝试中文映射
    if val in SUBJECT_CN_MAP:
        return SUBJECT_CN_MAP[val]
    return None


def clean_age_group(val):
    """
    清洗 age_group 字段，去除"岁"后缀等。
    兼容原始值（如 6-8）和编码值（如 AGE_06_08）。
    """
    if not val:
        return None
    val = str(val).strip()
    # 去除末尾的"岁"字
    if val.endswith("岁"):
        val = val[:-1]
    # 原始值直接匹配
    if val in AGE_GROUP_MAP:
        return val
    # 编码值反向映射（如 AGE_06_08 -> 6-8）
    for raw, code in AGE_GROUP_MAP.items():
        if val == code.lower():
            return raw
    return None


def clean_difficulty(val):
    """
    清洗 difficulty 字段，统一转换为英文编码。
    兼容原始值（如 beginner）和编码值（如 DIFF_EASY）。
    """
    if not val:
        return None
    val = str(val).strip().lower()
    # 原始值直接匹配
    if val in DIFFICULTY_MAP:
        return val
    # 编码值反向映射（如 DIFF_EASY -> beginner）
    for raw, code in DIFFICULTY_MAP.items():
        if val == code.lower():
            return raw
    # 尝试中文映射
    if val in DIFFICULTY_CN_MAP:
        return DIFFICULTY_CN_MAP[val]
    return None


def clean_type(val):
    """
    清洗 type 字段，统一转换为英文编码。
    兼容原始值（如 single_choice）和编码值（如 CHOICE）。
    """
    if not val:
        return "single_choice"
    val = str(val).strip().lower()
    if val in QUESTION_TYPE_MAP:
        return val
    if val in QUESTION_TYPE_CN_MAP:
        return QUESTION_TYPE_CN_MAP[val]
    # 编码值反向映射
    reverse_map = {v.lower(): k for k, v in QUESTION_TYPE_MAP.items()}
    if val in reverse_map:
        return reverse_map[val]
    return "single_choice"


def normalize_options(raw_options):
    """
    将选项统一转换为 [{"key": ..., "value": ...}] 格式。

    支持三种输入：
    - 对象列表: [{"label": "A", "text": "选项A"}, ...]
    - 纯字符串列表: ["选项A", "选项B", ...]
    - 带前缀字符串列表: ["A. 选项A", "B. 选项B", ...]
    """
    if not raw_options:
        return None

    result = []
    if isinstance(raw_options, list) and len(raw_options) > 0 and isinstance(raw_options[0], str):
        # 检测是否已包含 A./B./C./D. 前缀
        first = raw_options[0].strip()
        if len(first) >= 2 and first[0] in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" and first[1] in (".", ")", " "):
            # 已带前缀，提取 key 和 value
            prefix_pattern = re.compile(r"^([A-Z])[\.\)\s]\s*(.*)$")
            for opt_text in raw_options:
                m = prefix_pattern.match(opt_text.strip())
                if m:
                    result.append({"key": m.group(1), "value": m.group(2)})
                else:
                    # 不匹配则整体作为 value，按顺序分配 key
                    result.append({"key": chr(ord("A") + len(result)), "value": opt_text.strip()})
        else:
            # 纯字符串列表，自动分配 A/B/C/D...
            for idx, opt_text in enumerate(raw_options):
                key = chr(ord("A") + idx)
                result.append({"key": key, "value": opt_text})
    elif isinstance(raw_options, list) and len(raw_options) > 0 and isinstance(raw_options[0], dict):
        # 对象列表，映射 label/key -> key, text/value -> value
        for opt in raw_options:
            key = opt.get("label") or opt.get("key", "")
            value = opt.get("text") or opt.get("value", "")
            result.append({
                "key": key,
                "value": value,
            })
    else:
        return None
    return result if result else None


def get_question_content(q):
    """
    兼容获取题干内容（支持 content / question / question_body 等字段名）。
    """
    return q.get("content") or q.get("question") or q.get("question_body", "")


def get_correct_answer(q):
    """
    兼容获取正确答案（支持 correct_answer / answer 两种字段名）。
    """
    return q.get("correct_answer") or q.get("answer", "")


def get_tags(q):
    """
    兼容获取标签列表（支持 tags / knowledge_tags / knowledge_point 等字段名）。
    """
    tags = q.get("tags") or q.get("knowledge_tags")
    if isinstance(tags, list):
        return tags
    if isinstance(tags, str):
        return [tags]
    kp = q.get("knowledge_point")
    if isinstance(kp, str) and kp.strip():
        return [kp.strip()]
    return []


def load_json_files(sql_dir):
    """
    加载 sql/ 目录下所有 batch_*.json 和 pipeline_*.json 文件。

    返回去重后的题目列表，按 content + correct_answer 去重，保留首次出现的记录。
    同时会尝试从文件名推断缺失的 subject / age_group 字段。
    """
    seen = set()
    questions = []
    pattern = os.path.join(sql_dir, "batch_*.json")
    pattern2 = os.path.join(sql_dir, "pipeline_*.json")
    files = sorted(glob.glob(pattern) + glob.glob(pattern2))

    print(f"发现 {len(files)} 个 JSON 数据文件")

    for filepath in files:
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"  [警告] 跳过无法解析的文件 {filename}: {e}")
            continue

        # 兼容三种顶层结构：
        # 1. {"questions": [...]}
        # 2. {"batch_id": ..., "questions": [...]}
        # 3. 直接数组 [...]
        if isinstance(data, list):
            raw_questions = data
        elif isinstance(data, dict):
            raw_questions = data.get("questions", [])
        else:
            raw_questions = []

        if not isinstance(raw_questions, list):
            print(f"  [警告] 文件 {filename} 中 questions 字段不是列表，跳过")
            continue

        # 尝试从文件名推断缺失字段
        file_subject, file_age_group = parse_filename(filename)

        file_count = 0
        for q in raw_questions:
            if not isinstance(q, dict):
                continue

            # 字段清洗与兜底（兼容多种字段名）
            subject = clean_subject(q.get("subject") or q.get("subject_code"))
            age_group = clean_age_group(q.get("age_group") or q.get("age_group_code"))
            difficulty = clean_difficulty(q.get("difficulty") or q.get("difficulty_level"))

            # 文件名兜底
            if subject is None and file_subject is not None:
                subject = file_subject
            if age_group is None and file_age_group is not None:
                age_group = file_age_group

            # 若仍缺失关键字段，则跳过
            if subject is None or age_group is None or difficulty is None:
                continue

            # 将清洗后的字段写回字典，供后续使用
            q["_subject"] = subject
            q["_age_group"] = age_group
            q["_difficulty"] = difficulty
            q["_type"] = clean_type(q.get("type") or q.get("question_type"))

            content = get_question_content(q)
            correct = get_correct_answer(q)
            # 按 (学科, 年龄段, 内容, 答案) 四元组去重，允许不同学科/年龄段有相同内容
            dedup_key = (subject, age_group, content.strip(), str(correct).strip())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            questions.append(q)
            file_count += 1

        print(f"  [读取] {filename}: {file_count} 道有效题目")

    print(f"去重后共 {len(questions)} 道唯一题目\n")
    return questions


def build_knowledge_node(subject, age_group, difficulty, all_tags):
    """
    根据 (subject, age_group, difficulty) 组合构建 KnowledgeNode 数据字典。
    """
    subject_code = SUBJECT_MAP[subject]
    age_group_code = AGE_GROUP_MAP[age_group]
    diff_code = DIFFICULTY_MAP[difficulty]
    subject_cn = SUBJECT_NAME_MAP[subject]
    diff_cn = DIFFICULTY_NAME_MAP[difficulty]

    title = f"{subject_cn} - {age_group}岁 - {diff_cn}"
    unique_tags = sorted(set(tag.strip() for tag in all_tags if tag.strip()))
    description = "、".join(unique_tags) if unique_tags else ""

    content_body = (
        f"# {title}\n\n"
        f"涵盖知识点：{', '.join(unique_tags)}\n\n"
        f"适合年龄段：{age_group}\n\n"
        f"难度：{difficulty}"
    )

    # 使用 UUID5 保证同一组合始终生成相同 ID（幂等）
    node_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"kn:{subject}:{age_group}:{difficulty}")

    return {
        "id": node_id,
        "title": title,
        "description": description,
        "subject_code": subject_code,
        "age_group_code": age_group_code,
        "difficulty_level": diff_code,
        "content_type": "TYPE_QUIZ",
        "content_body": content_body,
        "estimated_minutes": 5,
        "prerequisites": None,
        "sort_order": 0,
        "is_active": True,
    }


def build_question(q_data, knowledge_node_id):
    """
    将原始题目字典转换为 Question 表数据字典。
    使用清洗后的字段（_subject, _age_group, _difficulty, _type）。
    """
    q_type_raw = q_data.get("_type", "single_choice")
    q_type = QUESTION_TYPE_MAP.get(q_type_raw, "CHOICE")

    difficulty_raw = q_data.get("_difficulty", "beginner")
    diff_code = DIFFICULTY_MAP.get(difficulty_raw, "DIFF_EASY")

    options = normalize_options(q_data.get("options"))

    return {
        "id": uuid.uuid4(),
        "knowledge_node_id": knowledge_node_id,
        "difficulty_level": diff_code,
        "question_type": q_type,
        "question_body": get_question_content(q_data),
        "options": options,
        "correct_answer": str(get_correct_answer(q_data)),
        "explanation": q_data.get("explanation", ""),
        "standard_time_seconds": 30,
        "sort_order": 0,
    }


async def fetch_existing_nodes(session):
    """
    查询数据库中已存在的 KnowledgeNode ID 集合。
    """
    stmt = select(knowledge_nodes_table.c.id)
    result = await session.execute(stmt)
    return {row[0] for row in result}


async def fetch_existing_question_keys(session):
    """
    查询数据库中已存在的题目唯一键集合（subject_code, age_group_code, question_body, correct_answer）。
    通过 JOIN knowledge_nodes 获取学科和年龄段信息。
    """
    stmt = select(
        knowledge_nodes_table.c.subject_code,
        knowledge_nodes_table.c.age_group_code,
        questions_table.c.question_body,
        questions_table.c.correct_answer,
    ).join(
        knowledge_nodes_table,
        questions_table.c.knowledge_node_id == knowledge_nodes_table.c.id,
    )
    result = await session.execute(stmt)
    # 反向映射回原始值（如 SUBJ_MATH -> math）用于与 JSON 中的值比较
    reverse_subject = {v: k for k, v in SUBJECT_MAP.items()}
    reverse_age = {v: k for k, v in AGE_GROUP_MAP.items()}
    keys = set()
    for row in result:
        subj = reverse_subject.get(row[0], row[0])
        age = reverse_age.get(row[1], row[1])
        keys.add((subj, age, row[2], row[3]))
    return keys


async def insert_knowledge_nodes(session, nodes):
    """
    批量插入 KnowledgeNode，跳过已存在的记录。
    """
    if not nodes:
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(knowledge_nodes_table).values(nodes)
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
    result = await session.execute(stmt)
    return result.rowcount if hasattr(result, "rowcount") else len(nodes)


async def insert_questions(session, questions):
    """
    批量插入 Question。
    调用前已在外层完成去重检查。
    """
    if not questions:
        return 0

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(questions_table).values(questions)
    stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
    result = await session.execute(stmt)
    return result.rowcount if hasattr(result, "rowcount") else len(questions)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

async def main():
    print("=" * 60)
    print("题库迁移脚本启动")
    print(f"目标数据库: {describe_database_target(DATABASE_URL)}")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60 + "\n")

    await ensure_schema_ready()

    # 1. 确定 sql/ 目录路径（相对于本脚本位于 backend/ 目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sql_dir = os.path.join(script_dir, "..", "sql")
    sql_dir = os.path.normpath(sql_dir)

    if not os.path.isdir(sql_dir):
        print(f"[错误] 找不到 sql/ 目录: {sql_dir}")
        return

    # 2. 加载并去重题目
    all_questions = load_json_files(sql_dir)
    if not all_questions:
        print("[错误] 没有加载到任何题目，退出")
        return

    # 3. 按 (subject, age_group, difficulty) 聚类，同时收集每组 tags
    cluster_map = defaultdict(lambda: {"questions": [], "tags": set()})
    skipped_invalid = 0

    for q in all_questions:
        subject = q.get("_subject")
        age_group = q.get("_age_group")
        difficulty = q.get("_difficulty")

        # 清洗后的字段理论上不会为空，再做一次防御性检查
        if subject not in SUBJECT_MAP or age_group not in AGE_GROUP_MAP or difficulty not in DIFFICULTY_MAP:
            skipped_invalid += 1
            continue

        key = (subject, age_group, difficulty)
        cluster_map[key]["questions"].append(q)
        for tag in get_tags(q):
            cluster_map[key]["tags"].add(tag)

    if skipped_invalid:
        print(f"[注意] 跳过 {skipped_invalid} 道字段映射不匹配的无效题目\n")

    print(f"共聚类为 {len(cluster_map)} 个 KnowledgeNode 分组\n")

    # 4. 连接数据库并执行迁移
    async with SessionLocal() as session:
        print("正在连接数据库并检查已有数据...")
        existing_node_ids = await fetch_existing_nodes(session)
        existing_q_keys = await fetch_existing_question_keys(session)
        print(f"  已有 KnowledgeNode: {len(existing_node_ids)} 个")
        print(f"  已有 Question: {len(existing_q_keys)} 道\n")

        # 预构建所有 KnowledgeNode
        nodes_to_insert = []
        node_id_map = {}  # key -> node_id
        for key, data in cluster_map.items():
            subject, age_group, difficulty = key
            node = build_knowledge_node(subject, age_group, difficulty, list(data["tags"]))
            node_id_map[key] = node["id"]
            if node["id"] not in existing_node_ids:
                nodes_to_insert.append(node)

        # 插入 KnowledgeNode
        if nodes_to_insert:
            print(f"准备插入 {len(nodes_to_insert)} 个新 KnowledgeNode...")
            inserted_nodes = await insert_knowledge_nodes(session, nodes_to_insert)
            await session.commit()
            print(f"  成功插入 {inserted_nodes} 个 KnowledgeNode\n")
        else:
            print("所有 KnowledgeNode 均已存在，无需插入\n")

        # 5. 处理题目，分批写入
        BATCH_SIZE = 200
        skipped_duplicates = 0
        inserted_total = 0

        all_q_data = []
        for key, data in cluster_map.items():
            node_id = node_id_map[key]
            subject, age_group, _difficulty = key
            for q in data["questions"]:
                q_body = get_question_content(q)
                q_answer = str(get_correct_answer(q))
                # 使用四元组 (subject, age_group, body, answer) 去重
                if (subject, age_group, q_body, q_answer) in existing_q_keys:
                    skipped_duplicates += 1
                    continue
                all_q_data.append(build_question(q, node_id))

        total_to_insert = len(all_q_data)
        print(f"准备写入题目: 总计 {total_to_insert} 道（跳过已有 {skipped_duplicates} 道）")

        for i in range(0, total_to_insert, BATCH_SIZE):
            batch = all_q_data[i : i + BATCH_SIZE]
            inserted = await insert_questions(session, batch)
            await session.commit()
            inserted_total += inserted
            print(f"  批次 {i // BATCH_SIZE + 1}: 写入 {inserted} / {len(batch)} 道")

        print()

    # 6. 输出统计报告
    print("=" * 60)
    print("迁移完成统计报告")
    print("=" * 60)
    print(f"  读取 JSON 文件数: {len(glob.glob(os.path.join(sql_dir, 'batch_*.json')) + glob.glob(os.path.join(sql_dir, 'pipeline_*.json')))}")
    print(f"  原始题目总数（去重后）: {len(all_questions)}")
    print(f"  无效题目（映射失败）: {skipped_invalid}")
    print(f"  KnowledgeNode 分组数: {len(cluster_map)}")
    print(f"  新增 KnowledgeNode: {len(nodes_to_insert)}")
    print(f"  已存在 KnowledgeNode: {len(existing_node_ids)}")
    print(f"  待插入题目数: {total_to_insert}")
    print(f"  跳过已有题目: {skipped_duplicates}")
    print(f"  实际插入题目: {inserted_total}")
    print("=" * 60)


def run() -> int:
    """运行导入并把 Schema 拒绝转为不含堆栈和凭据的纯文本诊断。"""

    try:
        asyncio.run(main())
        return 0
    except SchemaVersionError as exc:
        print(f"题库导入已拒绝：{exc}", file=sys.stderr)
        return 2
    except Exception:
        print("题库导入失败，已停止；请查看脱敏运维日志。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
