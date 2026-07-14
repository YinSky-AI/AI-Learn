"""
backend/app/ai/tools/skill_retrieval_tool.py

Skill 检索工具 —— SkillRetrievalTool

本模块负责从 Skill 存储目录中检索与当前出题场景匹配的 Skill 文件，
为 QuestionMemoryAgent 提供策略提示，支持 SummaryAgent 的跨会话召回（Hermes 环4）。

核心功能：
- 扫描 Skill 目录并解析 YAML frontmatter
- 基于触发条件、文件名和内容的匹配度排序
- 提取 Skill 中的执行步骤、用户偏好和常见陷阱
- 内存缓存机制，避免重复磁盘 I/O

关键约束：
- Skill 文件大小不超过 15KB（MAX_SKILL_SIZE）
- 触发条件必须明确可匹配
- 仅解析 .md 格式的 Skill 文件
- 目录变更后自动重新加载缓存

Skill 文件格式：
- YAML frontmatter 定义元数据（name, trigger, version, success_count）
- Markdown body 包含执行步骤、用户偏好记录、常见陷阱
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Skill 文件最大大小
MAX_SKILL_SIZE = 15 * 1024  # 15KB


class SkillRetrievalTool:
    """
    Skill 检索工具

    从 Skill 存储目录中检索匹配的 Skill 文件。
    """

    tool_name = "SkillRetrievalTool"

    def __init__(self, skills_dir: Optional[str] = None):
        """
        初始化 Skill 检索工具

        Args:
            skills_dir: Skill 存储目录路径
        """
        self._skills_dir = skills_dir
        # Skill 缓存
        self._cache: dict[str, dict[str, Any]] = {}
        self._cache_loaded = False

    def set_skills_dir(self, path: str) -> None:
        """设置 Skill 存储目录"""
        self._skills_dir = path
        self._cache_loaded = False  # 目录变更后重新加载

    def _load_cache(self) -> None:
        """加载 Skill 文件缓存"""
        if self._cache_loaded or not self._skills_dir:
            return

        if not os.path.isdir(self._skills_dir):
            logger.warning(f"[SkillRetrievalTool] Skill 目录不存在: {self._skills_dir}")
            self._cache_loaded = True
            return

        self._cache.clear()

        try:
            for filename in os.listdir(self._skills_dir):
                if not filename.endswith(".md"):
                    continue

                file_path = os.path.join(self._skills_dir, filename)
                file_size = os.path.getsize(file_path)

                if file_size > MAX_SKILL_SIZE:
                    logger.warning(
                        f"[SkillRetrievalTool] Skill 文件过大: {filename} "
                        f"({file_size} > {MAX_SKILL_SIZE})"
                    )
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # 解析 YAML frontmatter
                    skill_data = self._parse_skill_file(content, filename)
                    self._cache[filename] = skill_data

                except Exception as e:
                    logger.error(
                        f"[SkillRetrievalTool] 读取 Skill 文件失败: {filename} | {e}"
                    )

            self._cache_loaded = True
            logger.info(
                f"[SkillRetrievalTool] 缓存加载完成: {len(self._cache)} 个 Skill"
            )

        except Exception as e:
            logger.error(f"[SkillRetrievalTool] 目录扫描失败: {e}")
            self._cache_loaded = True

    def _parse_skill_file(
        self, content: str, filename: str
    ) -> dict[str, Any]:
        """
        解析 Skill 文件

        解析 YAML frontmatter 提取元数据。

        Args:
            content: 文件内容
            filename: 文件名

        Returns:
            Skill 数据字典
        """
        # 提取 YAML frontmatter
        frontmatter = {}
        body_start = 0

        if content.startswith("---"):
            end_idx = content.find("---", 3)
            if end_idx > 0:
                yaml_part = content[3:end_idx].strip()
                body_start = end_idx + 3

                # 简单解析 YAML（不依赖 PyYAML）
                for line in yaml_part.split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        frontmatter[key] = value

        body = content[body_start:].strip()

        return {
            "filename": filename,
            "name": frontmatter.get("name", filename),
            "trigger": frontmatter.get("trigger", ""),
            "version": int(frontmatter.get("version", 1)),
            "success_count": int(frontmatter.get("success_count", 0)),
            "created": frontmatter.get("created", ""),
            "body": body,
            "size": len(content.encode("utf-8")),
        }

    async def search_skills(
        self,
        subject: str = "",
        topic: str = "",
        age_group: str = "",
        difficulty: str = "",
    ) -> list[dict[str, Any]]:
        """
        搜索匹配的 Skill 文件

        Args:
            subject: 学科
            topic: 课程主题
            age_group: 年龄分级
            difficulty: 难度

        Returns:
            匹配的 Skill 列表（按匹配度排序）
        """
        self._load_cache()

        if not self._cache:
            return []

        matched = []
        search_terms = [t for t in [subject, topic, age_group, difficulty] if t]

        for filename, skill_data in self._cache.items():
            # 计算匹配度
            match_score = 0
            trigger = skill_data.get("trigger", "").lower()
            name = skill_data.get("name", "").lower()

            for term in search_terms:
                term_lower = term.lower()
                if term_lower in trigger:
                    match_score += 3  # 触发条件匹配权重高
                if term_lower in name:
                    match_score += 1  # 名称匹配
                if term_lower in skill_data.get("body", "").lower():
                    match_score += 0.5  # 内容匹配

            if match_score > 0:
                skill_data["match_score"] = match_score
                matched.append(skill_data)

        # 按匹配度排序
        matched.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        logger.info(
            f"[SkillRetrievalTool] Skill 搜索: "
            f"terms={search_terms} | "
            f"total={len(self._cache)} | "
            f"matched={len(matched)}"
        )

        return matched

    async def get_skill_hints(
        self,
        subject: str = "",
        topic: str = "",
        age_group: str = "",
        difficulty: str = "",
    ) -> list[dict[str, str]]:
        """
        获取 Skill 策略提示（用于注入 QuestionGeneratorAgent）

        Args:
            subject: 学科
            topic: 主题
            age_group: 年龄分级
            difficulty: 难度

        Returns:
            策略提示列表
        """
        skills = await self.search_skills(
            subject=subject,
            topic=topic,
            age_group=age_group,
            difficulty=difficulty,
        )

        hints = []
        for skill in skills[:3]:  # 最多使用 3 个 Skill 的提示
            body = skill.get("body", "")
            # 提取"执行步骤"部分
            steps = self._extract_section(body, "执行步骤")
            preferences = self._extract_section(body, "用户偏好记录")
            pitfalls = self._extract_section(body, "常见陷阱")

            hint = f"[Skill: {skill['name']}]"
            if steps:
                hint += f" 步骤: {steps[:200]}"
            if pitfalls:
                hint += f" 陷阱: {pitfalls[:200]}"

            hints.append({
                "skill_name": skill["name"],
                "hint": hint,
                "match_score": skill.get("match_score", 0),
            })

        return hints

    def _extract_section(self, body: str, section_name: str) -> str:
        """从 Skill body 中提取指定段落"""
        pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##\s|\Z)"
        match = re.search(pattern, body, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def get_tool_call_record(
        self,
        step_name: str,
        input_summary: dict[str, Any],
        output_summary: Optional[dict[str, Any]] = None,
        latency_ms: int = 0,
        status: str = "succeeded",
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        """生成工具调用日志记录"""
        return {
            "step_name": step_name,
            "tool_name": self.tool_name,
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": latency_ms,
            "status": status,
            "error_message": error_message,
        }
