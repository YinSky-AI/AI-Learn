"""
backend/app/ai/agents/summary_agent.py

Layer8 SummaryAgent —— Hermes 五环学习进化模块

本模块在出题闭环之外独立运行，负责从会话数据中提炼可复用的知识、
Skill 和用户画像，实现系统的持续进化与个性化适配。

Hermes 五环机制：
1. 记忆策划（环1）：从会话数据中筛选 ≤5 条高价值信息
2. Skill 创建（环2）：将高质量出题模式蒸馏为可复用 Skill
3. Skill 自改进（环3）：更新 Skill 的步骤、偏好、陷阱
4. 跨会话召回（环4）：FTS 检索最相关记忆
5. 用户建模（环5）：更新能力估计、行为模式、偏好冲突

层级位置：L8（学习进化层，在出题闭环之外独立运行）
输入：完整会话数据（session_data）
输出：MemoryItem、SkillFile、UserProfileUpdate

关键约束：
- 每次提炼记忆不超过 5 条
- Skill 文件大小不超过 15KB
- 记忆 TTL 默认 90 天
- 反馈一致性 < 70% 时不更新策略
- v0.1 仅实现 Skill 内容优化，不实现 Prompt 模板自修改
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from backend.app.ai.agents.base import BaseAgent
from backend.app.ai.prompts.summary import (
    build_memory_distill_prompt,
    build_skill_creation_prompt,
    build_user_profile_update_prompt,
)

logger = logging.getLogger(__name__)

# Skill 文件最大大小（字节）
MAX_SKILL_SIZE = 15 * 1024  # 15KB
# 记忆默认 TTL（天）
DEFAULT_MEMORY_TTL = 90
# 最大记忆条数
MAX_MEMORY_ITEMS = 5


class SummaryAgent(BaseAgent):
    """
    总结 Agent — Hermes 五环

    在学习会话结束时执行，从会话数据中提炼可复用的知识和技能。
    """

    agent_name = "SummaryAgent"
    layer = "L8"
    upstream_agents = ["Harness"]  # 接收整个会话数据
    downstream_agents = ["SessionMemory", "Skill存储", "User表"]
    input_signals = ["session_data"]
    output_signals = ["MemoryItem", "SkillFile", "UserProfileUpdate"]
    requires_json_output = True
    model = "deepseek-chat"
    temperature = 0.3

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Skill 存储目录
        self._skills_dir: Optional[str] = None
        # 进化备份目录
        self._evolution_dir: Optional[str] = None
        # 记忆持久化回调
        self._memory_persist_callback: Optional[Any] = None
        # 用户画像更新回调
        self._profile_update_callback: Optional[Any] = None

    def set_skills_dir(self, path: str) -> None:
        """设置 Skill 存储目录"""
        self._skills_dir = path

    def set_evolution_dir(self, path: str) -> None:
        """设置进化备份目录"""
        self._evolution_dir = path

    def set_memory_persist_callback(self, callback: Any) -> None:
        """设置记忆持久化回调"""
        self._memory_persist_callback = callback

    def set_profile_update_callback(self, callback: Any) -> None:
        """设置用户画像更新回调"""
        self._profile_update_callback = callback

    async def execute_summary(
        self,
        session_data: dict[str, Any],
        user_id: str,
        existing_memories: list[dict] = None,
        current_profile: dict = None,
    ) -> dict[str, Any]:
        """
        执行完整的五环总结流程

        Args:
            session_data: 会话数据
            user_id: 用户 ID
            existing_memories: 已有记忆
            current_profile: 当前用户画像

        Returns:
            总结结果 {memory_items, skill_file, profile_update}
        """
        logger.info(f"[SummaryAgent] 开始五环总结 | user={user_id}")

        result = {
            "memory_items": [],
            "skill_file": None,
            "profile_update": None,
        }

        # 环1: 记忆策划
        memory_items = await self._ring1_memory_distill(
            session_data, user_id, existing_memories
        )
        result["memory_items"] = memory_items

        # 环2: Skill 创建（仅在高质量出题时触发）
        skill_file = await self._ring2_skill_creation(session_data)
        result["skill_file"] = skill_file

        # 环5: 用户建模
        profile_update = await self._ring5_user_modeling(
            session_data, current_profile or {}
        )
        result["profile_update"] = profile_update

        logger.info(
            f"[SummaryAgent] 五环总结完成: "
            f"memories={len(memory_items)} | "
            f"skill={'有' if skill_file else '无'} | "
            f"profile_updated={'是' if profile_update else '否'}"
        )

        return result

    async def _ring1_memory_distill(
        self,
        session_data: dict[str, Any],
        user_id: str,
        existing_memories: list[dict] = None,
    ) -> list[dict[str, Any]]:
        """
        环1: 记忆策划 — 从会话数据中提炼不超过 5 条高价值记忆

        Args:
            session_data: 会话数据
            user_id: 用户 ID
            existing_memories: 已有记忆

        Returns:
            记忆项列表（不超过 5 条）
        """
        messages = build_memory_distill_prompt(
            session_data=session_data,
            user_id=user_id,
            existing_memories=existing_memories,
        )

        try:
            response = await self._call_llm(messages)
            content = response.get("content", "")
            data = self._safe_parse_json(content)

            if not isinstance(data, list):
                data = [data]

            # 限制数量
            memory_items = data[:MAX_MEMORY_ITEMS]

            # 验证每条记忆
            validated = []
            for item in memory_items:
                if not isinstance(item, dict):
                    continue
                if not item.get("content"):
                    continue

                validated.append({
                    "type": item.get("type", "quality_insight"),
                    "content": item["content"],
                    "confidence": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                    "ttl_days": min(180, max(30, int(item.get("ttl_days", DEFAULT_MEMORY_TTL)))),
                    "related_topic": item.get("related_topic", ""),
                    "user_id": user_id,
                })

            logger.info(f"[SummaryAgent] 环1记忆策划: 提炼 {len(validated)} 条记忆")

            # 持久化
            if self._memory_persist_callback and validated:
                try:
                    await self._memory_persist_callback(validated)
                except Exception as e:
                    logger.error(f"[SummaryAgent] 记忆持久化失败: {e}")

            return validated

        except Exception as e:
            logger.error(f"[SummaryAgent] 环1记忆策划失败: {e}")
            return []

    async def _ring2_skill_creation(
        self,
        session_data: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        环2: Skill 创建 — 将成功模式蒸馏为可复用 Skill

        Args:
            session_data: 会话数据

        Returns:
            Skill 文件数据（如果创建成功）
        """
        # 判断是否有值得创建 Skill 的成功模式
        success_rate = session_data.get("success_rate", 0)
        if success_rate < 0.8:  # 成功率低于 80% 不创建 Skill
            logger.info(
                f"[SummaryAgent] 环2跳过Skill创建: "
                f"成功率 {success_rate:.0%} < 80%"
            )
            return None

        topic = session_data.get("course_topic", "")
        messages = build_skill_creation_prompt(
            success_pattern=session_data,
            topic=topic,
        )

        try:
            response = await self._call_llm(messages)
            content = response.get("content", "")

            # 验证 Skill 文件大小
            if len(content.encode("utf-8")) > MAX_SKILL_SIZE:
                logger.warning(
                    f"[SummaryAgent] Skill 文件过大 "
                    f"({len(content.encode('utf-8'))} bytes > {MAX_SKILL_SIZE})"
                )
                return None

            skill_data = {
                "name": f"skill-{topic}-{datetime.utcnow().strftime('%Y%m%d')}",
                "content": content,
                "size": len(content.encode("utf-8")),
            }

            # 保存 Skill 文件
            if self._skills_dir:
                try:
                    os.makedirs(self._skills_dir, exist_ok=True)
                    file_path = os.path.join(
                        self._skills_dir,
                        f"{skill_data['name']}.md"
                    )
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.info(f"[SummaryAgent] Skill 文件已保存: {file_path}")
                except Exception as e:
                    logger.error(f"[SummaryAgent] Skill 文件保存失败: {e}")

            return skill_data

        except Exception as e:
            logger.error(f"[SummaryAgent] 环2 Skill创建失败: {e}")
            return None

    async def _ring5_user_modeling(
        self,
        session_data: dict[str, Any],
        current_profile: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        环5: 用户建模 — 更新用户画像

        Args:
            session_data: 会话数据
            current_profile: 当前用户画像

        Returns:
            用户画像更新数据
        """
        messages = build_user_profile_update_prompt(
            session_data=session_data,
            current_profile=current_profile,
        )

        try:
            response = await self._call_llm(messages)
            content = response.get("content", "")
            data = self._safe_parse_json(content)

            # 持久化
            if self._profile_update_callback and data:
                try:
                    await self._profile_update_callback(data)
                except Exception as e:
                    logger.error(f"[SummaryAgent] 用户画像更新失败: {e}")

            return data

        except Exception as e:
            logger.error(f"[SummaryAgent] 环5 用户建模失败: {e}")
            return None

    # 以下方法用于 BaseAgent 的标准 execute()，但 SummaryAgent 通常使用 execute_summary()
    def _build_prompt(
        self,
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, str]]:
        """标准 Prompt 构建（默认执行记忆提炼）"""
        return build_memory_distill_prompt(
            session_data=input_data.get("session_data", {}),
            user_id=input_data.get("user_id", ""),
        )

    def _parse_response(
        self,
        response: dict[str, Any],
        input_data: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """标准响应解析"""
        content = response.get("content", "")
        try:
            data = self._safe_parse_json(content)
            if isinstance(data, list):
                return {"memory_items": data[:MAX_MEMORY_ITEMS]}
            return {"memory_items": [data] if isinstance(data, dict) else []}
        except Exception:
            return {"memory_items": []}
