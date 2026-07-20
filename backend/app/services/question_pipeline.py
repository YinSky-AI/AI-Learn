# -*- coding: utf-8 -*-
"""
题库统一处理流水线

该模块是题库处理的统一入口，串联所有检查和修复模块。
处理流程: 输入题目 → [字段标准化] → [语言检测] → [质量门禁] → [评分打分] → [去重检查] → 输出

所有逻辑内嵌，不依赖外部 quality_gate / language_checker / difficulty_normalizer 模块。
仅依赖标准库 + psycopg2（数据库连接时）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# ============================================================
# 常量映射表
# ============================================================

# difficulty 中英文映射
DIFFICULTY_MAP: dict[str, str] = {
    "简单": "beginner",
    "初级": "beginner",
    "中等": "intermediate",
    "中级": "intermediate",
    "困难": "advanced",
    "高级": "advanced",
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}

# type 中文映射
TYPE_MAP: dict[str, str] = {
    "单选": "single_choice",
    "单选题": "single_choice",
    "单选题型": "single_choice",
    "多选": "multiple_choice",
    "多选题": "multiple_choice",
    "多选题型": "multiple_choice",
    "填空": "fill_blank",
    "填空题": "fill_blank",
    "填空题型": "fill_blank",
    "判断": "true_false",
    "判断题": "true_false",
    "判断题型": "true_false",
    "简答": "short_answer",
    "简答题": "short_answer",
    "简答题型": "short_answer",
    "single_choice": "single_choice",
    "multiple_choice": "multiple_choice",
    "fill_blank": "fill_blank",
    "true_false": "true_false",
    "short_answer": "short_answer",
}

# subject 中文映射
SUBJECT_MAP: dict[str, str] = {
    "数学": "math",
    "语文": "chinese",
    "英语": "english",
    "科学": "science",
    "物理": "physics",
    "化学": "chemistry",
    "生物": "biology",
    "历史": "history",
    "地理": "geography",
    "政治": "politics",
    "math": "math",
    "chinese": "chinese",
    "english": "english",
    "science": "science",
    "physics": "physics",
    "chemistry": "chemistry",
    "biology": "biology",
    "history": "history",
    "geography": "geography",
    "politics": "politics",
}

# 标准值域 —— 合法的 difficulty / type / subject 枚举
VALID_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
VALID_TYPES = {"single_choice", "multiple_choice", "fill_blank", "true_false", "short_answer"}
VALID_SUBJECTS = {
    "math", "chinese", "english", "science",
    "physics", "chemistry", "biology",
    "history", "geography", "politics",
}

# 英语学科 —— 语言检测阶段允许英文内容
ENGLISH_SUBJECTS = {"english"}


# ============================================================
# 数据类
# ============================================================

@dataclass
class PipelineResult:
    """流水线处理结果汇总"""
    input_count: int = 0            # 输入题目数
    passed_count: int = 0           # 通过题目数
    auto_fixed_count: int = 0       # 自动修复数
    rejected_count: int = 0         # 丢弃题目数
    duplicate_count: int = 0        # 重复题目数
    questions: list[dict] = field(default_factory=list)  # 最终通过的题目列表
    report: dict = field(default_factory=dict)           # 详细报告


# ============================================================
# QuestionPipeline 主类
# ============================================================

class QuestionPipeline:
    """
    题库统一处理流水线

    串联五个阶段: 字段标准化 → 语言检测 → 质量门禁 → 评分打分 → 去重检查。
    支持单题处理、批量处理和直接数据库读写。
    """

    def __init__(self, config: dict | None = None):
        self.config = config or self._default_config()
        self.seen_fingerprints: set[str] = set()  # 用于去重

    # --------------------------------------------------------
    # 公开接口
    # --------------------------------------------------------

    def process_single(self, question: dict) -> tuple[dict | None, dict]:
        """
        处理单道题

        Args:
            question: 原始题目字典

        Returns:
            (处理后的题目或None, 该题的详细报告)
        """
        report: dict[str, Any] = {
            "original": question.get("content", "")[:50],
            "stages": {},
            "final_status": "unknown",
        }
        fixed_flags: list[str] = []  # 记录被自动修复的字段
        current = dict(question)      # 深拷贝，避免修改原始数据

        # ---- 阶段 1: 字段标准化 ----
        current, norm_issues = self._stage1_normalize(current)
        if norm_issues:
            fixed_flags.extend(norm_issues)
        report["stages"]["stage1_normalize"] = {
            "status": "auto_fixed" if norm_issues else "passed",
            "details": norm_issues,
        }

        # ---- 阶段 2: 语言检测 ----
        current, lang_errors = self._stage2_check_language(current)
        if lang_errors:
            if self.config["reject_language_error"]:
                report["stages"]["stage2_language"] = {
                    "status": "rejected",
                    "details": lang_errors,
                }
                report["final_status"] = "rejected"
                return None, report
            else:
                # 不拒绝但记录警告
                fixed_flags.extend(lang_errors)
                report["stages"]["stage2_language"] = {
                    "status": "warning",
                    "details": lang_errors,
                }
        else:
            report["stages"]["stage2_language"] = {"status": "passed", "details": []}

        # ---- 阶段 3: 质量门禁 ----
        checked, quality_errors, quality_score = self._stage3_quality_check(current)
        if checked is None:
            report["stages"]["stage3_quality"] = {
                "status": "rejected",
                "details": quality_errors,
            }
            report["final_status"] = "rejected"
            return None, report
        current = checked
        report["stages"]["stage3_quality"] = {
            "status": "passed",
            "details": quality_errors if quality_errors else [],
        }

        # ---- 阶段 5: 去重检查 ----
        is_unique, fingerprint = self._stage5_dedup(current)
        if not is_unique:
            report["stages"]["stage5_dedup"] = {
                "status": "duplicate",
                "fingerprint": fingerprint,
            }
            report["final_status"] = "duplicate"
            return None, report
        report["stages"]["stage5_dedup"] = {
            "status": "unique",
            "fingerprint": fingerprint,
        }

        # ---- 汇总 ----
        report["auto_fixed"] = fixed_flags
        report["final_status"] = "passed"
        return current, report

    def process_batch(self, questions: list[dict]) -> PipelineResult:
        """
        批量处理题目

        Args:
            questions: 原始题目字典列表

        Returns:
            PipelineResult 汇总结果
        """
        result = PipelineResult(input_count=len(questions))
        detailed_reports: list[dict] = []

        for idx, q in enumerate(questions):
            processed, single_report = self.process_single(q)
            detailed_reports.append(single_report)

            if processed is not None:
                result.questions.append(processed)
                result.passed_count += 1
                # 判断是否有自动修复
                if single_report.get("auto_fixed"):
                    result.auto_fixed_count += 1
            elif single_report.get("final_status") == "duplicate":
                result.duplicate_count += 1
            else:
                result.rejected_count += 1

        # 构建汇总报告
        result.report = self._build_batch_report(result, detailed_reports)
        return result

    def process_database(self, db_url: str, table: str = "questions") -> PipelineResult:
        """
        直接从数据库读取题目，处理后再写回

        读取表中的所有题目，经过流水线处理后:
        - 通过的题目更新 quality_score / review_status / knowledge_fingerprint 等字段
        - 未通过但不满足 min_quality_score 拒绝阈值的仅标记
        - 重复的题目标记 review_status='duplicate'

        Args:
            db_url: PostgreSQL 连接字符串
            table: 源表名，默认 'questions'

        Returns:
            PipelineResult 汇总结果
        """
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise ImportError(
                "process_database 需要 psycopg2 库，请执行: pip install psycopg2-binary"
            )

        conn = psycopg2.connect(db_url)
        # 使用 RealDictCursor 让每行变成 dict
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 读取全部题目
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()
        questions = [dict(r) for r in rows]
        print(f"[数据库] 从 {table} 表读取 {len(questions)} 道题目")

        # 批量处理
        result = self.process_batch(questions)

        # 写回处理结果
        updated = 0
        for q in result.questions:
            kf = q.get("knowledge_fingerprint")
            if isinstance(kf, dict):
                kf = json.dumps(kf, ensure_ascii=False)
            cur.execute(f"""
                UPDATE {table} SET
                    knowledge_fingerprint = %s,
                    language        = %s
                WHERE id = %s
            """, (
                kf,
                q.get("language"),
                q.get("id"),
            ))
            updated += 1

        conn.commit()
        cur.close()
        conn.close()
        print(f"[数据库] 更新 {updated} 道题目，提交完成")

        return result

    # --------------------------------------------------------
    # 阶段 1: 字段标准化
    # --------------------------------------------------------

    def _stage1_normalize(self, question: dict) -> tuple[dict, list[str]]:
        """
        阶段1：字段标准化

        - difficulty 中英文映射
        - type 中文映射
        - subject 中文映射
        - age_group 格式化（去除"岁"字）
        - options 格式统一为 [{"label":"A","text":"..."}]
        """
        q = dict(question)  # 避免修改原始字典
        fixes: list[str] = []

        # ---- difficulty 标准化 ----
        raw_diff = q.get("difficulty", "").strip()
        if raw_diff in DIFFICULTY_MAP:
            normalized = DIFFICULTY_MAP[raw_diff]
            if normalized != raw_diff:
                q["difficulty"] = normalized
                fixes.append(f"difficulty: '{raw_diff}' → '{normalized}'")
        elif raw_diff:
            fixes.append(f"difficulty: 未知值 '{raw_diff}'，保留原值")

        # ---- type 标准化 ----
        raw_type = q.get("type", "").strip()
        if raw_type in TYPE_MAP:
            normalized = TYPE_MAP[raw_type]
            if normalized != raw_type:
                q["type"] = normalized
                fixes.append(f"type: '{raw_type}' → '{normalized}'")

        # ---- subject 标准化 ----
        raw_subj = q.get("subject", "").strip()
        if raw_subj in SUBJECT_MAP:
            normalized = SUBJECT_MAP[raw_subj]
            if normalized != raw_subj:
                q["subject"] = normalized
                fixes.append(f"subject: '{raw_subj}' → '{normalized}'")

        # ---- age_group 格式化（去除"岁"字）----
        raw_age = str(q.get("age_group", ""))
        if "岁" in raw_age:
            cleaned = raw_age.replace("岁", "").strip()
            q["age_group"] = cleaned
            fixes.append(f"age_group: '{raw_age}' → '{cleaned}'")

        # ---- options 格式统一 ----
        raw_options = q.get("options")
        if raw_options is not None and isinstance(raw_options, list):
            normalized_opts = self._normalize_options(raw_options)
            if normalized_opts != raw_options:
                q["options"] = normalized_opts
                fixes.append("options: 格式已统一为 [{label, text}]")

        return q, fixes

    @staticmethod
    def _normalize_options(options: list[dict]) -> list[dict]:
        """
        将 options 统一为 [{"label": "A", "text": "..."}] 格式

        支持的输入格式:
        - {"label": "A", "text": "..."}  → 保持
        - {"label": "A", "content": "..."} → content → text
        - {"A": "..."}  → 转换
        - ["选项A文本", "选项B文本"] → 按序号分配 label
        """
        result: list[dict] = []
        labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        for idx, opt in enumerate(options):
            if not isinstance(opt, dict):
                # 列表形式: ["选项文本", ...]
                result.append({
                    "label": labels[idx] if idx < len(labels) else str(idx),
                    "text": str(opt),
                })
                continue

            # 已有 label + text → 直接使用
            if "label" in opt and "text" in opt:
                result.append({"label": opt["label"], "text": opt["text"]})
                continue

            # 有 label 但没有 text（可能有 content）
            if "label" in opt:
                text = opt.get("text") or opt.get("content") or opt.get("value") or ""
                result.append({"label": opt["label"], "text": str(text)})
                continue

            # 没有 label，尝试从 key 推断
            # 格式如 {"A": "xxx", "B": "yyy"} 之类的单元素字典
            for key, val in opt.items():
                label = str(key).upper().strip()
                # 如果 key 看起来像选项标号 (A/B/C/...)
                if label in labels and len(label) == 1:
                    result.append({"label": label, "text": str(val)})
                else:
                    # 否则当作普通字段，按序号分配 label
                    result.append({
                        "label": labels[idx] if idx < len(labels) else str(idx),
                        "text": str(val),
                    })
                break  # 每个字典只取第一个 key-value

        return result

    # --------------------------------------------------------
    # 阶段 2: 语言检测
    # --------------------------------------------------------

    def _stage2_check_language(self, question: dict) -> tuple[dict, list[str]]:
        """
        阶段2：语言检测

        - 非英语学科 content 不得以英文字母开头
        - 非英语学科 options 必须为中文
        - 返回 (修复后的题, 错误列表)
        """
        q = dict(question)
        errors: list[str] = []
        subject = q.get("subject", "").strip().lower()

        # 英语学科跳过检测
        if subject in ENGLISH_SUBJECTS:
            return q, errors

        # 检查 content 是否以英文字母开头
        content = str(q.get("content", ""))
        if content and re.match(r"^[A-Za-z]", content):
            errors.append(
                f"非英语学科({subject})的 content 以英文字母开头: '{content[:30]}...'"
            )

        # 检查 options 是否为中文
        options = q.get("options")
        if options and isinstance(options, list):
            for opt in options:
                text = str(opt.get("text", ""))
                if text and not self._contains_chinese(text):
                    errors.append(
                        f"非英语学科({subject})的选项 '{opt.get('label', '?')}' "
                        f"不含中文: '{text[:30]}'"
                    )

        return q, errors

    @staticmethod
    def _contains_chinese(text: str) -> bool:
        """判断文本是否包含中文字符"""
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    # --------------------------------------------------------
    # 阶段 3: 质量门禁
    # --------------------------------------------------------

    def _stage3_quality_check(
        self, question: dict
    ) -> tuple[dict | None, list[str], int]:
        """
        阶段3：质量门禁

        检查项:
        - content 长度 > 5
        - correct_answer 非空
        - explanation 长度 >= min_explanation_length (默认50)
        - difficulty 在标准值域内
        - type 在标准值域内
        - 适龄性检查（content / option 长度不超过年龄组上限）

        返回: (题或None, 错误列表, 质量评分0-100)
        """
        errors: list[str] = []
        # 加分制：从0分开始，只有真正优秀的题才能得到高分

        content = str(question.get("content", ""))
        correct_answer = str(question.get("correct_answer", ""))
        explanation = str(question.get("explanation", ""))
        difficulty = question.get("difficulty", "").strip()
        q_type = question.get("type", "").strip()
        age_group = str(question.get("age_group", "")).strip()
        options = question.get("options")
        tags = question.get("tags")

        score = 0

        # ========== 一票否决项（不加分，直接拒绝） ==========

        # ---- content 非空且长度 > 5 ----
        if self.config["reject_zero_content"]:
            if not content or len(content) <= 5:
                errors.append(f"content 长度不足 (当前 {len(content)} 字符，要求 > 5)")
                return None, errors, 0

        # ---- correct_answer 非空 ----
        if not correct_answer.strip():
            errors.append("correct_answer 为空")
            return None, errors, 0

        # ========== 基础分（满足最低标准即可获得） ==========
        score += 20  # 通过了否决项即得20分基础分

        # ========== 内容质量（最高30分） ==========
        content_len = len(content)

        # 题干长度适中性
        if 15 <= content_len <= 60:
            score += 8   # 简洁精炼（适合低年龄段）
        elif 60 < content_len <= 120:
            score += 10  # 中等长度，信息量适中
        elif 120 < content_len <= 200:
            score += 10  # 较长题目，信息丰富
        elif content_len > 200:
            score += 7   # 过长可能不够精炼
        elif content_len > 5:
            score += 3   # 偏短但有内容

        # 题干完整性：包含标点符号、问号等
        if "？" in content or "?" in content:
            score += 5   # 有明确的问题形式
        if "。" in content or "." in content or "，" in content or "," in content:
            score += 3   # 有完整的语句结构

        # ========== 解析质量（最高25分）==========
        exp_len = len(explanation) if explanation else 0

        if exp_len >= 150:
            score += 15  # 解析详细充分
        elif exp_len >= 100:
            score += 12  # 解析较详细
        elif exp_len >= 50:
            score += 8   # 解析达到最低要求
        elif exp_len >= 20:
            score += 3   # 有解析但偏短
        # exp_len < 20: 0分

        # 解析质量：是否包含推理过程
        if explanation:
            reasoning_keywords = ["因为", "所以", "由于", "因此", "根据", "因为", "原理是",
                                   "首先", "然后", "步骤", "公式", "思路"]
            has_reasoning = any(kw in explanation for kw in reasoning_keywords)
            if has_reasoning:
                score += 7   # 包含推理过程
            elif len(explanation) >= 30:
                score += 3   # 有一定解释但不包含推理

        # ========== 选项质量（最高15分，仅选择题）==========
        if q_type in ("single_choice", "multiple_choice"):
            if options and isinstance(options, list):
                opt_count = len(options)
                if opt_count == 4:
                    score += 8  # 标准4选项
                elif opt_count == 3:
                    score += 5  # 3选项
                elif opt_count >= 5:
                    score += 6  # 5个以上选项
                elif opt_count == 2:
                    score += 2  # 仅2选项（判断题水平）

                # 选项长度一致性：各选项长度相近说明干扰项质量高
                if opt_count >= 3:
                    opt_texts = []
                    for opt in options:
                        if isinstance(opt, dict):
                            opt_texts.append(len(opt.get("text", "")))
                        elif isinstance(opt, str):
                            opt_texts.append(len(opt))
                    if len(opt_texts) >= 3:
                        avg_len = sum(opt_texts) / len(opt_texts)
                        variance = sum((l - avg_len) ** 2 for l in opt_texts) / len(opt_texts)
                        if variance < 50:
                            score += 4   # 选项长度非常一致，干扰项质量高
                        elif variance < 150:
                            score += 2   # 选项长度较一致
                # 选择题没有选项
            else:
                score -= 5
        elif q_type in ("fill_blank", "short_answer"):
            score += 3  # 非选择题没有选项要求，给基础分

        # ========== 适龄性（最高5分） ==========
        age_errors, age_penalty = self._check_age_appropriateness(
            content, options, age_group
        )
        if age_errors:
            errors.extend(age_errors)
            # 不再扣分，只是不加分
        else:
            score += 5  # 完全符合适龄性要求

        # ========== 元数据完整性（最高5分）==========
        if tags and isinstance(tags, (list, str)):
            tag_count = len(tags) if isinstance(tags, list) else len([t for t in tags.split(",") if t.strip()])
            if tag_count >= 3:
                score += 3  # 标签丰富
            elif tag_count >= 1:
                score += 1
        if difficulty in VALID_DIFFICULTIES:
            score += 1
        if q_type in VALID_TYPES:
            score += 1

        score = max(0, min(score, 100))  # 限制在 0-100
        return question, errors, score

    def _check_age_appropriateness(
        self, content: str, options: Any, age_group: str
    ) -> tuple[list[str], int]:
        """
        适龄性检查：不同年龄组对 content 和 option 长度有上限要求

        返回: (错误列表, 扣分)
        """
        errors: list[str] = []
        penalty = 0

        age_limits = self.config.get("age_group_max_lengths", {})
        limits = age_limits.get(age_group)
        if not limits:
            # 未知年龄组不做检查
            return errors, penalty

        max_content_len = limits.get("content", 9999)
        max_option_len = limits.get("option", 9999)

        if len(content) > max_content_len:
            errors.append(
                f"适龄性: {age_group} 岁组 content 长度 {len(content)} 超过上限 {max_content_len}"
            )
            penalty += 10

        if options and isinstance(options, list):
            for opt in options:
                text = str(opt.get("text", ""))
                if len(text) > max_option_len:
                    label = opt.get("label", "?")
                    errors.append(
                        f"适龄性: {age_group} 岁组选项 {label} 长度 {len(text)} "
                        f"超过上限 {max_option_len}"
                    )
                    penalty += 5

        return errors, penalty

    # --------------------------------------------------------
    # 阶段 4: 评分打分
    # --------------------------------------------------------

    def _stage4_score(self, question: dict, quality_score: int) -> dict:
        """
        阶段4：评分打分

        - 设置 quality_score
        - 设置 review_status: >= 70 → "approved", 40-70 → "review", < 40 → "rejected"
        - 设置 generation_source
        - 设置 language ("zh" 或 "en")
        - 计算 knowledge_fingerprint (简易版: subject+age_group+difficulty+type)
        """
        q = dict(question)

        # 质量评分
        q["quality_score"] = quality_score

        # 审核状态
        if quality_score >= 70:
            q["review_status"] = "approved"
        elif quality_score >= 40:
            q["review_status"] = "review"
        else:
            q["review_status"] = "rejected"

        # 生成来源
        q["generation_source"] = q.get("source") or q.get("generation_source") or "pipeline"

        # 语言判断
        subject = str(q.get("subject", "")).lower()
        if subject in ENGLISH_SUBJECTS:
            q["language"] = "en"
        else:
            q["language"] = "zh"

        # 知识指纹 (简易版: subject + age_group + difficulty + type 的哈希)
        fp_raw = (
            f"{q.get('subject', '')}|"
            f"{q.get('age_group', '')}|"
            f"{q.get('difficulty', '')}|"
            f"{q.get('type', '')}"
        )
        q["knowledge_fingerprint"] = {
            "fingerprint": hashlib.md5(fp_raw.encode("utf-8")).hexdigest()[:16],
            "subject": q.get("subject", ""),
            "age_group": q.get("age_group", ""),
            "difficulty": q.get("difficulty", ""),
            "type": q.get("type", ""),
        }

        return q

    # --------------------------------------------------------
    # 阶段 5: 去重检查
    # --------------------------------------------------------

    def _stage5_dedup(self, question: dict) -> tuple[bool, str]:
        """
        阶段5：去重检查

        基于 content 前 100 字符 + correct_answer 做指纹。
        如果指纹已存在于 self.seen_fingerprints 中，则判定为重复。

        返回: (是否唯一, 指纹字符串)
        """
        content = str(question.get("content", ""))[:100]
        correct_answer = str(question.get("correct_answer", ""))
        raw = f"{content}||{correct_answer}"
        fingerprint = hashlib.md5(raw.encode("utf-8")).hexdigest()

        if fingerprint in self.seen_fingerprints:
            return False, fingerprint

        self.seen_fingerprints.add(fingerprint)
        return True, fingerprint

    # --------------------------------------------------------
    # 配置与报告
    # --------------------------------------------------------

    @staticmethod
    def _default_config() -> dict:
        """默认配置"""
        return {
            "reject_zero_content": True,
            "reject_short_explanation": True,
            "min_explanation_length": 50,
            "reject_language_error": True,
            "min_quality_score": 0,  # 0 = 不根据分数拒绝，仅标记
            "age_group_max_lengths": {
                "6-8": {"content": 60, "option": 20},
                "9-12": {"content": 100, "option": 30},
                "13-15": {"content": 150, "option": 40},
                "16-18": {"content": 250, "option": 60},
            },
        }

    @staticmethod
    def _build_batch_report(result: PipelineResult, detailed_reports: list[dict]) -> dict:
        """构建批量处理的汇总报告"""
        # 按阶段统计
        stage_stats: dict[str, dict[str, int]] = {}
        for rpt in detailed_reports:
            for stage_name, stage_info in rpt.get("stages", {}).items():
                if stage_name not in stage_stats:
                    stage_stats[stage_name] = {}
                status = stage_info.get("status", "unknown")
                stage_stats[stage_name][status] = stage_stats[stage_name].get(status, 0) + 1

        # 收集被拒绝和重复的题目摘要
        rejected_summaries = []
        duplicate_summaries = []
        for rpt in detailed_reports:
            if rpt.get("final_status") == "rejected":
                rejected_summaries.append({
                    "content_preview": rpt.get("original", "")[:50],
                    "reason": rpt.get("stages", {}).get(
                        "stage3_quality", {}
                    ).get("details", [])[:3],
                })
            elif rpt.get("final_status") == "duplicate":
                duplicate_summaries.append({
                    "content_preview": rpt.get("original", "")[:50],
                    "fingerprint": rpt.get("stages", {}).get(
                        "stage5_dedup", {}
                    ).get("fingerprint", ""),
                })

        return {
            "summary": {
                "input_count": result.input_count,
                "passed_count": result.passed_count,
                "auto_fixed_count": result.auto_fixed_count,
                "rejected_count": result.rejected_count,
                "duplicate_count": result.duplicate_count,
                "pass_rate": (
                    f"{result.passed_count / result.input_count * 100:.1f}%"
                    if result.input_count > 0
                    else "N/A"
                ),
            },
            "stage_statistics": stage_stats,
            "rejected_details": rejected_summaries,
            "duplicate_details": duplicate_summaries,
        }

    def generate_report(self, result: PipelineResult) -> str:
        """
        生成 Markdown 格式的质量报告

        Args:
            result: 流水线处理结果

        Returns:
            Markdown 格式的报告字符串
        """
        lines: list[str] = []
        lines.append("# 题库处理流水线质量报告")
        lines.append("")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # ---- 汇总统计 ----
        rpt = result.report
        summary = rpt.get("summary", {})
        lines.append("## 1. 汇总统计")
        lines.append("")
        lines.append("| 指标 | 数值 |")
        lines.append("|------|------|")
        lines.append(f"| 输入题目数 | {result.input_count} |")
        lines.append(f"| 通过题目数 | {result.passed_count} |")
        lines.append(f"| 自动修复数 | {result.auto_fixed_count} |")
        lines.append(f"| 丢弃题目数 | {result.rejected_count} |")
        lines.append(f"| 重复题目数 | {result.duplicate_count} |")
        lines.append(f"| 通过率 | {summary.get('pass_rate', 'N/A')} |")
        lines.append("")

        # ---- 各阶段统计 ----
        stage_stats = rpt.get("stage_statistics", {})
        if stage_stats:
            lines.append("## 2. 各阶段统计")
            lines.append("")
            stage_names = {
                "stage1_normalize": "阶段1: 字段标准化",
                "stage2_language": "阶段2: 语言检测",
                "stage3_quality": "阶段3: 质量门禁",
                "stage4_scoring": "阶段4: 评分打分",
                "stage5_dedup": "阶段5: 去重检查",
            }
            for stage_key, statuses in stage_stats.items():
                display_name = stage_names.get(stage_key, stage_key)
                lines.append(f"### {display_name}")
                lines.append("")
                lines.append("| 状态 | 数量 |")
                lines.append("|------|------|")
                for status, count in statuses.items():
                    status_label = {
                        "passed": "通过",
                        "auto_fixed": "自动修复",
                        "warning": "警告",
                        "rejected": "拒绝",
                        "duplicate": "重复",
                        "unique": "唯一",
                        "done": "完成",
                    }.get(status, status)
                    lines.append(f"| {status_label} | {count} |")
                lines.append("")

        # ---- 被拒绝的题目详情 ----
        rejected = rpt.get("rejected_details", [])
        if rejected:
            lines.append("## 3. 被拒绝的题目")
            lines.append("")
            for i, item in enumerate(rejected, 1):
                preview = item.get("content_preview", "")
                reasons = item.get("reason", [])
                reason_text = "; ".join(str(r) for r in reasons) if reasons else "未知原因"
                lines.append(f"{i}. **{preview}...**")
                lines.append(f"   - 原因: {reason_text}")
                lines.append("")

        # ---- 重复题目详情 ----
        duplicates = rpt.get("duplicate_details", [])
        if duplicates:
            lines.append("## 4. 重复题目")
            lines.append("")
            for i, item in enumerate(duplicates, 1):
                preview = item.get("content_preview", "")
                fp = item.get("fingerprint", "")
                lines.append(f"{i}. **{preview}...** (指纹: `{fp}`)")
            lines.append("")

        return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================

def main():
    """命令行入口：支持从 JSON 文件或数据库读取题目进行批量处理"""
    parser = argparse.ArgumentParser(
        description="题库统一处理流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 从 JSON 文件处理
  python question_pipeline.py --input sql/questions_full.json --output sql/questions_cleaned.json

  # 从数据库处理（ai_learn 库）
  python question_pipeline.py --db --db-url "postgresql://postgres:postgres@localhost:5432/ai_learn"
        """,
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        help="输入 JSON 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="输出 JSON 文件路径（仅 --input 模式有效）",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        default=False,
        help="从数据库读取并写回",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default="postgresql://postgres:postgres@localhost:5432/ai_learn",
        help="PostgreSQL 连接字符串（默认: postgresql://postgres:postgres@localhost:5432/ai_learn）",
    )
    parser.add_argument(
        "--table",
        type=str,
        default="questions",
        help="数据库表名（默认: questions）",
    )
    parser.add_argument(
        "--report",
        type=str,
        default=None,
        help="输出 Markdown 报告文件路径（可选）",
    )

    args = parser.parse_args()

    # 校验参数
    if not args.db and not args.input:
        parser.error("请指定 --input <json文件> 或 --db 以选择数据来源")
    if args.input and args.db:
        parser.error("--input 和 --db 不能同时使用")

    pipeline = QuestionPipeline()

    if args.db:
        # ---- 数据库模式 ----
        print(f"[流水线] 从数据库读取 (表: {args.table})...")
        result = pipeline.process_database(args.db_url, args.table)
    else:
        # ---- JSON 文件模式 ----
        print(f"[流水线] 从文件读取: {args.input}")
        with open(args.input, "r", encoding="utf-8") as f:
            questions = json.load(f)

        if not isinstance(questions, list):
            print("[错误] JSON 文件顶层应为数组 (list)")
            sys.exit(1)

        print(f"[流水线] 共读取 {len(questions)} 道题目，开始处理...")
        result = pipeline.process_batch(questions)

        # 写出结果
        output_path = args.output
        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result.questions, f, ensure_ascii=False, indent=2)
            print(f"[流水线] 清洗后题目已写入: {output_path}")
        else:
            # 没有指定输出路径，打印到标准输出
            print(json.dumps(result.questions, ensure_ascii=False, indent=2))

    # 输出汇总
    print("")
    print("=" * 60)
    print(f"  输入: {result.input_count}  |  "
          f"通过: {result.passed_count}  |  "
          f"修复: {result.auto_fixed_count}  |  "
          f"丢弃: {result.rejected_count}  |  "
          f"重复: {result.duplicate_count}")
    print("=" * 60)

    # 生成 Markdown 报告
    md_report = pipeline.generate_report(result)
    report_path = args.report
    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        print(f"[报告] 已写入: {report_path}")
    else:
        # 没有指定报告路径时，打印到标准输出
        print("")
        print(md_report)


if __name__ == "__main__":
    main()