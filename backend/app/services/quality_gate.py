# -*- coding: utf-8 -*-
"""
题库质量门禁模块

对题目数据进行多维度质量检查，输出通过/失败/需修复的结果。
检查维度包括：字段非空、字段值域、适龄性、选项完整性、语言规范性。
所有依赖均为 Python 标准库，无第三方引入。

使用示例：
    gate = QualityGate()
    result = gate.check(question_dict)
    if result.passed:
        print("题目通过质量门禁")
    else:
        print(result.errors)
"""

import json
import re
from dataclasses import dataclass, field


# ============================================================
# 常量定义
# ============================================================

# 合法的难度值
VALID_DIFFICULTIES = ["beginner", "intermediate", "advanced"]

# 合法的题型
VALID_TYPES = [
    "single_choice",
    "multiple_choice",
    "fill_blank",
    "true_false",
    "short_answer",
]

# 合法的学科
VALID_SUBJECTS = [
    "math",
    "chinese",
    "english",
    "science",
    "physics",
    "chemistry",
    "biology",
    "history",
    "geography",
    "politics",
]

# 合法的年龄分组
VALID_AGE_GROUPS = ["6-8", "9-12", "13-15", "16-18"]

# 适龄性字数限制映射：{年龄分组: (题目最大字数, 选项最大字数)}
AGE_LENGTH_LIMITS = {
    "6-8": (60, 20),
    "9-12": (100, 30),
    "13-15": (150, 40),
    "16-18": (250, 60),
}

# 需要选项的题型（必须拥有 options 字段）
TYPES_REQUIRING_OPTIONS = ["single_choice", "multiple_choice", "true_false"]

# 通过门禁的最低分数
PASS_THRESHOLD = 60

# 质量评分扣分规则
SCORE_FIELD_MISSING = 15       # 每缺一个必填字段扣分
SCORE_AGE_OVERLENGTH = 5       # 适龄性每超长一个字段扣分
SCORE_LANGUAGE_ERROR = 20      # 语言错误扣分
SCORE_DOMAIN_ERROR = 10        # difficulty/type 不在值域内扣分


# ============================================================
# 数据模型
# ============================================================

@dataclass
class QualityResult:
    """
    单道题目的质量检查结果

    Attributes:
        passed:       是否通过质量门禁（score >= PASS_THRESHOLD）
        score:        质量评分，0-100 整数
        errors:       错误列表（必须修复的问题，描述性信息）
        warnings:     警告列表（建议修复但不阻断的问题）
        auto_fixable: 是否存在可自动修复的建议
        fixes:        自动修复建议，键为字段名，值为修复后的值
    """
    passed: bool = False
    score: int = 100
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_fixable: bool = False
    fixes: dict = field(default_factory=dict)


# ============================================================
# 辅助函数：语言检查（内嵌，不依赖外部模块）
# ============================================================

def _is_chinese_char(ch: str) -> bool:
    """
    判断单个字符是否为 CJK 统一汉字

    范围覆盖 CJK 基本区（4E00-9FFF）和扩展 A 区（3400-4DBF）。
    """
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF)


def _has_chinese(text: str) -> bool:
    """
    判断文本中是否包含至少一个汉字
    """
    return any(_is_chinese_char(ch) for ch in text)


def _is_mostly_chinese(text: str, threshold: float = 0.5) -> bool:
    """
    判断文本是否主要由中文构成

    当中文字符占总非空白字符的比例 >= threshold 时返回 True。
    纯标点、数字、英文的混合文本也会被合理处理。

    Args:
        text:      待检测文本
        threshold: 中文占比阈值，默认 0.5

    Returns:
        文本是否主要由中文构成
    """
    if not text or not text.strip():
        return False
    # 过滤空白字符后统计
    non_space = [ch for ch in text if not ch.isspace()]
    if not non_space:
        return False
    chinese_count = sum(1 for ch in non_space if _is_chinese_char(ch))
    return (chinese_count / len(non_space)) >= threshold


def _check_language(question: dict) -> tuple[list[str], list[str], dict]:
    """
    语言规范性检查（内嵌实现）

    规则：
    - 非英语学科的 content 不得以英文字母开头
    - 非英语学科的 options 文本必须为中文
    - 非英语学科的 explanation 必须为中文

    Returns:
        (errors, warnings, fixes) 三元组
    """
    errors: list[str] = []
    warnings: list[str] = []
    fixes: dict = {}

    subject = question.get("subject", "")
    is_english = (subject == "english")

    if is_english:
        # 英语学科不做中文语言检查
        return errors, warnings, fixes

    # 检查 content 是否以英文字母开头
    content = question.get("content", "")
    if content and re.match(r"^[A-Za-z]", content):
        errors.append(
            f"非英语学科（{subject}）的题目内容不应以英文字母开头，"
            f"实际开头为：'{content[:20]}'"
        )

    # 检查 options 文本是否为中文
    options = question.get("options", [])
    if isinstance(options, list):
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                continue
            opt_text = opt.get("text", "")
            if opt_text and not _is_mostly_chinese(opt_text):
                errors.append(
                    f"非英语学科（{subject}）的第 {i + 1} 个选项文本应主要为中文，"
                    f"实际内容：'{opt_text[:30]}'"
                )

    # 检查 explanation 是否为中文
    explanation = question.get("explanation", "")
    if explanation and not _is_mostly_chinese(explanation):
        errors.append(
            f"非英语学科（{subject}）的解析应主要为中文，"
            f"实际内容：'{explanation[:30]}'"
        )

    return errors, warnings, fixes


# ============================================================
# 辅助函数：difficulty 标准化（内嵌，不依赖外部模块）
# ============================================================

_DIFFICULTY_ALIASES = {
    # 中文别名 -> 标准值
    "简单": "beginner",
    "初级": "beginner",
    "容易": "beginner",
    "入门": "beginner",
    "中等": "intermediate",
    "中级": "intermediate",
    "一般": "intermediate",
    "较难": "advanced",
    "困难": "advanced",
    "高级": "advanced",
    "难": "advanced",
    # 英文别名（大小写兼容）
    "easy": "beginner",
    "medium": "intermediate",
    "hard": "advanced",
    "basic": "beginner",
    "EASY": "beginner",
    "MEDIUM": "intermediate",
    "HARD": "advanced",
    "BASIC": "beginner",
}


def _normalize_difficulty(raw: str) -> tuple[str, bool]:
    """
    将非标准的 difficulty 值标准化为合法值

    Args:
        raw: 原始 difficulty 值

    Returns:
        (normalized_value, was_normalized) 二元组
        若无法识别则原样返回 (raw, False)
    """
    if not raw or not isinstance(raw, str):
        return raw, False
    stripped = raw.strip().lower()
    if stripped in VALID_DIFFICULTIES:
        return stripped, False
    # 先精确匹配
    if raw in _DIFFICULTY_ALIASES:
        return _DIFFICULTY_ALIASES[raw], True
    # 再忽略大小写匹配
    if stripped in _DIFFICULTY_ALIASES:
        return _DIFFICULTY_ALIASES[stripped], True
    return raw, False


# ============================================================
# 质量门禁主类
# ============================================================

class QualityGate:
    """
    题库质量门禁

    对单道或批量题目执行多维度质量检查：
    1. 字段非空检查
    2. 字段值域检查
    3. 适龄性检查
    4. 选项完整性检查
    5. 语言规范性检查
    6. 综合质量评分

    使用方式：
        gate = QualityGate()
        result = gate.check(question_dict)
        print(result.passed, result.score, result.errors)
    """

    def __init__(self, pass_threshold: int = PASS_THRESHOLD):
        """
        初始化质量门禁

        Args:
            pass_threshold: 通过门禁的最低分数，默认 60
        """
        self.pass_threshold = pass_threshold

    # --------------------------------------------------------
    # 检查入口
    # --------------------------------------------------------

    def check(self, question: dict) -> QualityResult:
        """
        检查单道题目

        对传入的题目字典执行全部维度的质量检查，返回包含评分、
        错误、警告和自动修复建议的 QualityResult 对象。

        Args:
            question: 题目字典，至少应包含 content、correct_answer、
                      explanation、subject、age_group、type、difficulty
                      等字段

        Returns:
            QualityResult 检查结果
        """
        result = QualityResult()

        # 依次执行各项检查
        self._check_field_non_empty(question, result)
        self._check_field_domain(question, result)
        self._check_age_appropriateness(question, result)
        self._check_options_completeness(question, result)
        self._check_language(question, result)

        # 汇总评分并判定是否通过
        result.score = max(0, min(100, result.score))
        result.passed = result.score >= self.pass_threshold

        # 如果存在修复建议，标记为可自动修复
        result.auto_fixable = len(result.fixes) > 0

        return result

    def check_batch(self, questions: list[dict]) -> list[QualityResult]:
        """
        批量检查题目

        逐一检查每道题目，返回与输入等长的结果列表。

        Args:
            questions: 题目字典列表

        Returns:
            QualityResult 列表，顺序与输入一致
        """
        results: list[QualityResult] = []
        for q in questions:
            results.append(self.check(q))
        return results

    def generate_report(self, results: list[QualityResult]) -> str:
        """
        生成质量报告

        统计批量检查结果，输出结构化的文本报告，包含：
        - 总体概览（通过率、平均分、分数分布）
        - 常见错误统计
        - 未通过题目的错误明细

        Args:
            results: 批量检查的结果列表

        Returns:
            质量报告文本
        """
        if not results:
            return "无检查结果，请先执行 check 或 check_batch。"

        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0

        # 分数分布
        score_ranges = {
            "90-100（优秀）": 0,
            "60-89（合格）": 0,
            "0-59（不合格）": 0,
        }
        for r in results:
            if r.score >= 90:
                score_ranges["90-100（优秀）"] += 1
            elif r.score >= 60:
                score_ranges["60-89（合格）"] += 1
            else:
                score_ranges["0-59（不合格）"] += 1

        avg_score = sum(r.score for r in results) / total if total > 0 else 0

        # 统计常见错误
        error_counter: dict[str, int] = {}
        for r in results:
            for err in r.errors:
                # 提取错误类型关键词（取第一个冒号之前的部分）
                err_type = err.split("：")[0].split(":")[0].strip()
                error_counter[err_type] = error_counter.get(err_type, 0) + 1

        # 统计常见警告
        warn_counter: dict[str, int] = {}
        for r in results:
            for w in r.warnings:
                warn_type = w.split("：")[0].split(":")[0].strip()
                warn_counter[warn_type] = warn_counter.get(warn_type, 0) + 1

        # 统计可自动修复数量
        fixable = sum(1 for r in results if r.auto_fixable)

        # 构建报告
        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("题库质量门禁报告")
        lines.append("=" * 60)
        lines.append("")

        # 总体概览
        lines.append("【总体概览】")
        lines.append(f"  检查总数：{total}")
        lines.append(f"  通过数量：{passed}")
        lines.append(f"  未通过数量：{failed}")
        lines.append(f"  通过率：{pass_rate:.1f}%")
        lines.append(f"  平均分：{avg_score:.1f}")
        lines.append(f"  可自动修复：{fixable} 道")
        lines.append("")

        # 分数分布
        lines.append("【分数分布】")
        for label, count in score_ranges.items():
            bar = "#" * count
            pct = (count / total * 100) if total > 0 else 0
            lines.append(f"  {label}：{count} 道 ({pct:.1f}%)  {bar}")
        lines.append("")

        # 常见错误
        if error_counter:
            lines.append("【常见错误 TOP 10】")
            sorted_errors = sorted(error_counter.items(), key=lambda x: -x[1])[:10]
            for err_type, count in sorted_errors:
                lines.append(f"  [{count} 次] {err_type}")
            lines.append("")
        else:
            lines.append("【常见错误】无")
            lines.append("")

        # 常见警告
        if warn_counter:
            lines.append("【常见警告 TOP 5】")
            sorted_warns = sorted(warn_counter.items(), key=lambda x: -x[1])[:5]
            for w_type, count in sorted_warns:
                lines.append(f"  [{count} 次] {w_type}")
            lines.append("")
        else:
            lines.append("【常见警告】无")
            lines.append("")

        # 未通过题目的错误明细
        failed_results = [r for r in results if not r.passed]
        if failed_results:
            lines.append(f"【未通过题目明细】（共 {len(failed_results)} 道）")
            for idx, r in enumerate(failed_results, 1):
                lines.append(f"  --- 第 {idx} 道（得分：{r.score}）---")
                for err in r.errors:
                    lines.append(f"    [错误] {err}")
                for w in r.warnings:
                    lines.append(f"    [警告] {w}")
                if r.fixes:
                    fix_summary = json.dumps(r.fixes, ensure_ascii=False)
                    lines.append(f"    [修复建议] {fix_summary}")
                lines.append("")
        else:
            lines.append("【未通过题目明细】全部通过，无明细。")
            lines.append("")

        lines.append("=" * 60)
        lines.append("报告结束")
        lines.append("=" * 60)

        return "\n".join(lines)

    # --------------------------------------------------------
    # 检查维度 1：字段非空检查
    # --------------------------------------------------------

    def _check_field_non_empty(self, question: dict, result: QualityResult) -> None:
        """
        字段非空检查

        规则：
        - content 不为空且长度 > 5
        - correct_answer 不为空
        - explanation 不为空且长度 >= 50
        - subject, age_group, type 不为空
        """
        # content 检查
        content = question.get("content", "")
        if not content or (isinstance(content, str) and not content.strip()):
            result.errors.append("字段非空检查失败：content 为空")
            result.score -= SCORE_FIELD_MISSING
        elif len(str(content).strip()) <= 5:
            result.errors.append(
                f"字段非空检查失败：content 长度应 > 5，当前长度 {len(str(content).strip())}"
            )
            result.score -= SCORE_FIELD_MISSING

        # correct_answer 检查
        correct_answer = question.get("correct_answer", "")
        if not correct_answer or (isinstance(correct_answer, str) and not correct_answer.strip()):
            result.errors.append("字段非空检查失败：correct_answer 为空")
            result.score -= SCORE_FIELD_MISSING

        # explanation 检查
        explanation = question.get("explanation", "")
        if not explanation or (isinstance(explanation, str) and not explanation.strip()):
            result.errors.append("字段非空检查失败：explanation 为空")
            result.score -= SCORE_FIELD_MISSING
        elif len(str(explanation).strip()) < 50:
            result.errors.append(
                f"字段非空检查失败：explanation 长度应 >= 50，"
                f"当前长度 {len(str(explanation).strip())}"
            )
            result.score -= SCORE_FIELD_MISSING

        # subject 检查
        subject = question.get("subject", "")
        if not subject or (isinstance(subject, str) and not subject.strip()):
            result.errors.append("字段非空检查失败：subject 为空")
            result.score -= SCORE_FIELD_MISSING

        # age_group 检查
        age_group = question.get("age_group", "")
        if not age_group or (isinstance(age_group, str) and not age_group.strip()):
            result.errors.append("字段非空检查失败：age_group 为空")
            result.score -= SCORE_FIELD_MISSING

        # type 检查
        q_type = question.get("type", "")
        if not q_type or (isinstance(q_type, str) and not q_type.strip()):
            result.errors.append("字段非空检查失败：type 为空")
            result.score -= SCORE_FIELD_MISSING

    # --------------------------------------------------------
    # 检查维度 2：字段值域检查
    # --------------------------------------------------------

    def _check_field_domain(self, question: dict, result: QualityResult) -> None:
        """
        字段值域检查

        规则：
        - difficulty 必须在 VALID_DIFFICULTIES 中
        - type 必须在 VALID_TYPES 中
        - subject 必须在 VALID_SUBJECTS 中
        - age_group 必须在 VALID_AGE_GROUPS 中

        对于 difficulty，会先尝试将常见别名标准化。
        """
        # difficulty 值域检查
        raw_difficulty = question.get("difficulty", "")
        if raw_difficulty and isinstance(raw_difficulty, str):
            normalized, was_normalized = _normalize_difficulty(raw_difficulty.strip())
            if was_normalized:
                # 可以自动修复
                result.fixes["difficulty"] = normalized
                result.warnings.append(
                    f"字段值域警告：difficulty '{raw_difficulty}' 已标准化为 '{normalized}'"
                )
            elif normalized not in VALID_DIFFICULTIES:
                result.errors.append(
                    f"字段值域检查失败：difficulty '{raw_difficulty}' "
                    f"不在合法值 {VALID_DIFFICULTIES} 中"
                )
                result.score -= SCORE_DOMAIN_ERROR
        elif not raw_difficulty:
            result.warnings.append("字段值域警告：difficulty 为空，跳过值域检查")

        # type 值域检查
        q_type = question.get("type", "")
        if q_type and isinstance(q_type, str):
            q_type_stripped = q_type.strip()
            if q_type_stripped not in VALID_TYPES:
                result.errors.append(
                    f"字段值域检查失败：type '{q_type}' "
                    f"不在合法值 {VALID_TYPES} 中"
                )
                result.score -= SCORE_DOMAIN_ERROR

        # subject 值域检查
        subject = question.get("subject", "")
        if subject and isinstance(subject, str):
            subject_stripped = subject.strip()
            if subject_stripped not in VALID_SUBJECTS:
                result.errors.append(
                    f"字段值域检查失败：subject '{subject}' "
                    f"不在合法值 {VALID_SUBJECTS} 中"
                )
                result.score -= SCORE_DOMAIN_ERROR

        # age_group 值域检查
        age_group = question.get("age_group", "")
        if age_group and isinstance(age_group, str):
            age_group_stripped = age_group.strip()
            if age_group_stripped not in VALID_AGE_GROUPS:
                result.errors.append(
                    f"字段值域检查失败：age_group '{age_group}' "
                    f"不在合法值 {VALID_AGE_GROUPS} 中"
                )
                result.score -= SCORE_DOMAIN_ERROR

    # --------------------------------------------------------
    # 检查维度 3：适龄性检查
    # --------------------------------------------------------

    def _check_age_appropriateness(self, question: dict, result: QualityResult) -> None:
        """
        适龄性检查

        根据年龄分组限制题目内容和选项的文本长度：
        - 6-8岁：content <= 60字，options文本 <= 20字
        - 9-12岁：content <= 100字，options文本 <= 30字
        - 13-15岁：content <= 150字，options文本 <= 40字
        - 16-18岁：content <= 250字，options文本 <= 60字
        """
        age_group = str(question.get("age_group", "")).strip()
        if age_group not in AGE_LENGTH_LIMITS:
            # 年龄分组不合法或为空，跳过适龄性检查
            # （值域错误已在值域检查中报告）
            return

        max_content_len, max_option_len = AGE_LENGTH_LIMITS[age_group]

        # 检查 content 长度
        content = str(question.get("content", "")).strip()
        if content and len(content) > max_content_len:
            result.errors.append(
                f"适龄性检查失败：{age_group}岁组 content 长度 {len(content)} "
                f"超过限制 {max_content_len} 字"
            )
            result.score -= SCORE_AGE_OVERLENGTH

        # 检查 options 文本长度
        options = question.get("options", [])
        if isinstance(options, list):
            for i, opt in enumerate(options):
                if not isinstance(opt, dict):
                    continue
                opt_text = str(opt.get("text", "")).strip()
                if opt_text and len(opt_text) > max_option_len:
                    result.errors.append(
                        f"适龄性检查失败：{age_group}岁组第 {i + 1} 个选项文本长度 "
                        f"{len(opt_text)} 超过限制 {max_option_len} 字"
                    )
                    result.score -= SCORE_AGE_OVERLENGTH

    # --------------------------------------------------------
    # 检查维度 4：选项完整性检查
    # --------------------------------------------------------

    def _check_options_completeness(self, question: dict, result: QualityResult) -> None:
        """
        选项完整性检查

        规则：
        - single_choice/multiple_choice/true_false 类型必须有 options 且 >= 2 个选项
        - 每个选项必须有 label 和 text 字段
        - multiple_choice 的 correct_answer 格式应为 "A,C" 或 "A,B,D"（逗号分隔的标签）
        """
        q_type = str(question.get("type", "")).strip()

        # 仅对需要选项的题型进行检查
        if q_type not in TYPES_REQUIRING_OPTIONS:
            return

        options = question.get("options", [])

        # 检查 options 是否存在且为列表
        if not options or not isinstance(options, list):
            result.errors.append(
                f"选项完整性检查失败：{q_type} 类型必须提供 options 列表"
            )
            result.score -= SCORE_FIELD_MISSING
            return

        # 检查选项数量
        if len(options) < 2:
            result.errors.append(
                f"选项完整性检查失败：{q_type} 类型至少需要 2 个选项，"
                f"当前仅有 {len(options)} 个"
            )
            result.score -= SCORE_FIELD_MISSING

        # 检查每个选项的 label 和 text 字段
        for i, opt in enumerate(options):
            if not isinstance(opt, dict):
                result.errors.append(
                    f"选项完整性检查失败：第 {i + 1} 个选项不是有效的字典对象"
                )
                result.score -= SCORE_FIELD_MISSING
                continue

            if "label" not in opt or not str(opt["label"]).strip():
                result.errors.append(
                    f"选项完整性检查失败：第 {i + 1} 个选项缺少 label 字段"
                )
                result.score -= SCORE_FIELD_MISSING

            if "text" not in opt or not str(opt["text"]).strip():
                result.errors.append(
                    f"选项完整性检查失败：第 {i + 1} 个选项缺少 text 字段"
                )
                result.score -= SCORE_FIELD_MISSING

        # 检查 multiple_choice 的 correct_answer 格式
        if q_type == "multiple_choice":
            correct_answer = str(question.get("correct_answer", "")).strip()
            if correct_answer:
                # 合法格式：单个标签或逗号分隔的多个标签，如 "A,C" 或 "A,B,D"
                labels = [opt.get("label", "") for opt in options if isinstance(opt, dict)]
                labels_str = ",".join(str(l).strip() for l in labels if l)

                # 检查是否为逗号分隔的标签格式（不包含选项文本内容）
                # 合法格式只包含大写字母和逗号
                if not re.match(r"^[A-Z](,[A-Z])*$", correct_answer):
                    result.errors.append(
                        f"选项完整性检查失败：multiple_choice 的 correct_answer "
                        f"格式应为逗号分隔的标签（如 'A,C'），"
                        f"实际值为 '{correct_answer}'"
                    )
                    result.score -= SCORE_FIELD_MISSING

                # 检查 correct_answer 中的标签是否在 options 中存在
                answer_labels = [l.strip() for l in correct_answer.split(",") if l.strip()]
                valid_labels = {str(opt.get("label", "")).strip() for opt in options if isinstance(opt, dict)}
                for al in answer_labels:
                    if al and al not in valid_labels:
                        result.errors.append(
                            f"选项完整性检查失败：correct_answer 中的标签 '{al}' "
                            f"在 options 中不存在"
                        )
                        result.score -= SCORE_FIELD_MISSING

    # --------------------------------------------------------
    # 检查维度 5：语言规范性检查
    # --------------------------------------------------------

    def _check_language(self, question: dict, result: QualityResult) -> None:
        """
        语言规范性检查

        调用内嵌的语言检查函数，检查非英语学科的中文规范性。
        若发现语言错误，扣 20 分。
        """
        errors, warnings, fixes = _check_language(question)
        result.errors.extend(errors)
        result.warnings.extend(warnings)
        result.fixes.update(fixes)

        # 语言错误扣分
        if errors:
            result.score -= SCORE_LANGUAGE_ERROR