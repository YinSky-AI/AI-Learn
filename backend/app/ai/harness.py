"""
AI Harness 编排入口 — 管理完整的 8 层闭环控制流程

职责：
- 编排 8 层 Agent 的执行流程
- 错误处理、重试、降级
- 记录 ToolCallLog
- 内嵌 FeedbackAggregator 子组件
- 注入 ControlSignal 到下一次循环
- 管理 HarnessRun 生命周期

执行流程：
L1 CourseIntentAgent → L2 QuestionPlannerAgent → L3 QuestionMemoryAgent
→ L4 QuestionGeneratorAgent → L5 QualityCheckAgent
→ L6 SafetyAuditAgent + L6 QualityReviewAgent（并行）
→ L7 FeedbackAggregator（内嵌）
→ ToolHarness（保存题目、日志）
→ L8 SummaryAgent（可选，会话结束时）

关键约束：
- Harness 只负责编排和审计，不直接承担业务判题
- 每个 Agent 单一职责
- 所有工具调用必须记录 tool_name、input、output_summary、latency_ms、status、error
- v0.1 不调用联网搜索
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Optional

from backend.app.ai.schemas import (
    HarnessRunContext,
    HarnessRunStatus,
    ToolCallRecord,
)
from backend.app.ai.agents.course_intent import CourseIntentAgent
from backend.app.ai.agents.question_planner import QuestionPlannerAgent
from backend.app.ai.agents.question_memory import QuestionMemoryAgent
from backend.app.ai.agents.question_generator import QuestionGeneratorAgent
from backend.app.ai.agents.quality_checker import QualityCheckAgent
from backend.app.ai.agents.safety_auditor import SafetyAuditAgent
from backend.app.ai.agents.quality_reviewer import QualityReviewAgent
from backend.app.ai.agents.summary_agent import SummaryAgent
from backend.app.ai.feedback_aggregator import FeedbackAggregator
from backend.app.ai.error_logger import ErrorLogger
from backend.app.ai.tools.question_memory_tool import QuestionMemoryTool
from backend.app.ai.tools.question_save_tool import QuestionSaveTool
from backend.app.ai.tools.audit_log_tool import AuditLogTool
from backend.app.ai.tools.skill_retrieval_tool import SkillRetrievalTool

logger = logging.getLogger(__name__)

# 最大循环次数（防止无限循环）
MAX_ITERATIONS = 3
# 质量检查通过率阈值（低于此值触发重试）
MIN_PASS_RATE = 0.5


class AIHarness:
    """
    AI 出题 Harness 编排器

    管理完整的 8 层闭环控制流程。
    """

    def __init__(
        self,
        db_session: Optional[Any] = None,
        skills_dir: Optional[str] = None,
        evolution_dir: Optional[str] = None,
    ):
        """
        初始化 AI Harness

        Args:
            db_session: 数据库会话（可选）
            skills_dir: Skill 存储目录路径（可选）
            evolution_dir: 进化记录目录路径（可选）
        """
        # 内嵌 FeedbackAggregator
        self._feedback = FeedbackAggregator()

        # 内嵌 ErrorLogger
        self._error_logger = ErrorLogger()

        # 初始化 8 层 Agent
        self._course_intent = CourseIntentAgent(
            error_logger=self._error_logger,
        )
        self._planner = QuestionPlannerAgent(
            error_logger=self._error_logger,
        )
        self._memory = QuestionMemoryAgent(
            error_logger=self._error_logger,
        )
        self._generator = QuestionGeneratorAgent(
            error_logger=self._error_logger,
        )
        self._quality_checker = QualityCheckAgent(
            error_logger=self._error_logger,
        )
        self._safety_auditor = SafetyAuditAgent(
            error_logger=self._error_logger,
        )
        self._quality_reviewer = QualityReviewAgent(
            error_logger=self._error_logger,
        )
        self._summary = SummaryAgent(
            error_logger=self._error_logger,
        )

        # 初始化工具
        self._memory_tool = QuestionMemoryTool(db_session=db_session)
        self._save_tool = QuestionSaveTool(db_session=db_session)
        self._audit_tool = AuditLogTool(db_session=db_session)
        self._skill_tool = SkillRetrievalTool(skills_dir=skills_dir)

        # 注入工具回调
        self._memory.set_memory_search_callback(
            self._memory_tool.search_similar_questions
        )
        self._summary.set_skills_dir(skills_dir or "")
        self._summary.set_evolution_dir(evolution_dir or "")

        # Harness 运行上下文
        self._run_context: Optional[HarnessRunContext] = None

    @property
    def feedback(self) -> FeedbackAggregator:
        """获取 FeedbackAggregator 实例"""
        return self._feedback

    @property
    def error_logger(self) -> ErrorLogger:
        """获取 ErrorLogger 实例"""
        return self._error_logger

    async def generate(
        self,
        user_id: str,
        user_input: str = "",
        age_group: str = "",
        subject: str = "",
        course_topic: str = "",
        difficulty: str = "medium",
        question_types: Optional[list[str]] = None,
        question_count: int = 10,
        learning_goal: str = "",
    ) -> dict[str, Any]:
        """
        执行完整的出题生成流程

        这是 Harness 的主入口方法。

        Args:
            user_id: 用户 ID
            user_input: 用户原始输入
            age_group: 年龄分级
            subject: 学科
            course_topic: 课程主题
            difficulty: 难度
            question_types: 题型列表
            question_count: 题目数量
            learning_goal: 学习目标

        Returns:
            生成结果 {
                "batch_id": str,
                "questions": list,
                "run_id": str,
                "status": str,
                "statistics": dict,
            }
        """
        run_id = str(uuid.uuid4())
        start_time = time.monotonic()

        logger.info(f"[Harness] 开始生成 | run_id={run_id} | user={user_id}")

        # 创建运行上下文
        self._run_context = HarnessRunContext(
            run_id=run_id,
            user_id=user_id,
            run_type="question_generation",
            status=HarnessRunStatus.RUNNING,
            input_payload={
                "user_input": user_input,
                "age_group": age_group,
                "subject": subject,
                "course_topic": course_topic,
                "difficulty": difficulty,
                "question_types": question_types or ["choice", "fill_blank"],
                "question_count": question_count,
                "learning_goal": learning_goal,
            },
        )

        # 重置组件状态
        self._feedback.reset()
        self._error_logger.reset()
        self._audit_tool.clear_cache()

        try:
            result = await self._run_generation_loop()

            # 更新运行上下文
            self._run_context.status = HarnessRunStatus.SUCCEEDED
            self._run_context.output_summary = {
                "question_count": len(result.get("questions", [])),
                "batch_id": result.get("batch_id", ""),
            }

        except Exception as e:
            logger.error(f"[Harness] 生成失败 | run_id={run_id} | {e}")
            self._run_context.status = HarnessRunStatus.FAILED
            self._run_context.error_message = str(e)

            result = {
                "batch_id": "",
                "questions": [],
                "run_id": run_id,
                "status": "failed",
                "error": str(e),
                "statistics": {},
            }

        finally:
            self._run_context.completed_at = datetime.utcnow()
            total_ms = int((time.monotonic() - start_time) * 1000)
            self._run_context.model_usage = {
                "total_latency_ms": total_ms,
            }

            # 持久化错误日志
            await self._error_logger.flush()

            # 记录审计日志
            await self._persist_tool_logs()

        result["run_id"] = run_id
        return result

    async def _run_generation_loop(self) -> dict[str, Any]:
        """
        执行生成循环（支持最多 MAX_ITERATIONS 次重试）

        Returns:
            生成结果
        """
        all_passed_questions = []

        for iteration in range(MAX_ITERATIONS):
            logger.info(
                f"[Harness] 循环 {iteration + 1}/{MAX_ITERATIONS} | "
                f"run_id={self._run_context.run_id if self._run_context else 'unknown'}"
            )

            self._run_context.iteration = iteration

            # 获取当前控制信号
            control_signal = self._feedback.get_signal_dict()

            # 执行 8 层流程
            intent_params = await self._step1_course_intent(control_signal)
            plan_result = await self._step2_question_plan(intent_params, control_signal)
            memory_context = await self._step3_memory_retrieval(plan_result, control_signal)
            generated = await self._step4_generate(plan_result, memory_context, control_signal)
            qc_results = await self._step5_quality_check(generated, intent_params)

            # 安全审查和质量趋势分析（并行执行）
            safety_results = await self._step6a_safety_audit(generated, intent_params)
            trend_report = await self._step6b_quality_review(generated, qc_results)

            # 过滤通过的题目
            passed_questions = self._filter_passed_questions(
                generated["questions"], qc_results, safety_results
            )

            # 汇聚反馈信号
            self._feedback.ingest_quality_checks(qc_results)
            self._feedback.ingest_safety_audits(safety_results)
            self._feedback.ingest_quality_trend(trend_report)
            control_signal = self._feedback.compute_control_signal()

            # 记录控制信号审计
            await self._audit_tool.log_control_signal(
                control_signal=control_signal,
                run_id=self._run_context.run_id,
            )

            # 计算通过率
            total_generated = len(generated["questions"])
            total_passed = len(passed_questions)
            pass_rate = total_passed / max(1, total_generated)

            logger.info(
                f"[Harness] 循环 {iteration + 1} 结果: "
                f"generated={total_generated} | passed={total_passed} | "
                f"pass_rate={pass_rate:.2f}"
            )

            all_passed_questions.extend(passed_questions)

            # 通过率足够高或已到最大循环次数，退出
            if pass_rate >= MIN_PASS_RATE or iteration >= MAX_ITERATIONS - 1:
                break

            logger.info(
                f"[Harness] 通过率 {pass_rate:.2f} < {MIN_PASS_RATE}，继续循环"
            )

        # 保存通过的题目
        batch_id = str(uuid.uuid4())
        if all_passed_questions:
            await self._save_questions(batch_id, all_passed_questions)

        return {
            "batch_id": batch_id,
            "questions": all_passed_questions,
            "status": "succeeded",
            "statistics": {
                "total_generated": total_generated,
                "total_passed": len(all_passed_questions),
                "iterations": iteration + 1,
                "control_signal": control_signal,
            },
        }

    # =========================================================================
    # 8 层执行步骤
    # =========================================================================

    async def _step1_course_intent(
        self, control_signal: dict
    ) -> dict[str, Any]:
        """
        L1: 课程意图理解

        如果输入已有完整参数，可跳过 LLM 调用。
        """
        step_name = "intent"
        input_payload = self._run_context.input_payload

        # 如果已有完整参数，跳过 LLM 调用
        if (
            input_payload.get("age_group")
            and input_payload.get("subject")
            and input_payload.get("course_topic")
        ):
            intent_params = {
                "age_group": input_payload["age_group"],
                "subject": input_payload["subject"],
                "course_topic": input_payload["course_topic"],
                "difficulty": input_payload.get("difficulty", "medium"),
                "question_types": input_payload.get(
                    "question_types", ["choice", "fill_blank"]
                ),
                "question_count": input_payload.get("question_count", 10),
                "learning_goal": input_payload.get("learning_goal", ""),
                "raw_input": input_payload.get("user_input", ""),
                "clarification_required": False,
            }
            logger.info(f"[Harness] L1 跳过：参数已完整")
        else:
            intent_params = await self._course_intent.execute(
                input_data=input_payload,
                context={"run_id": self._run_context.run_id},
            )

        self._record_tool_call(
            step_name=step_name,
            tool_name="CourseIntentAgent",
            input_summary={"raw_input": input_payload.get("user_input", "")[:100]},
            output_summary={"topic": intent_params.get("course_topic", "")},
        )

        return intent_params

    async def _step2_question_plan(
        self, intent_params: dict, control_signal: dict
    ) -> dict[str, Any]:
        """L2: 出题规划"""
        plan_input = {
            **intent_params,
            "control_signal": control_signal,
        }
        plan_result = await self._planner.execute(
            input_data=plan_input,
            context={"run_id": self._run_context.run_id},
        )

        self._record_tool_call(
            step_name="plan",
            tool_name="QuestionPlannerAgent",
            input_summary={
                "topic": intent_params.get("course_topic", ""),
                "count": intent_params.get("question_count", 10),
            },
            output_summary={
                "planned_count": plan_result.get("planned_count", 0),
                "deviation": plan_result.get("deviation_declaration") is not None,
            },
        )

        return plan_result

    async def _step3_memory_retrieval(
        self, plan_result: dict, control_signal: dict
    ) -> dict[str, Any]:
        """L3: 记忆检索"""
        intent_params = self._run_context.input_payload

        # 使用工具检索相似题目
        similar_result = await self._memory_tool.search_similar_questions(
            user_id=self._run_context.user_id,
            subject=intent_params.get("subject", "数学"),
            course_topic=intent_params.get("course_topic", ""),
        )

        # 检索 Skill 提示
        skill_hints = await self._skill_tool.get_skill_hints(
            subject=intent_params.get("subject", ""),
            topic=intent_params.get("course_topic", ""),
            age_group=intent_params.get("age_group", ""),
            difficulty=intent_params.get("difficulty", ""),
        )

        memory_input = {
            "subject": intent_params.get("subject", "数学"),
            "course_topic": intent_params.get("course_topic", ""),
            "difficulty": intent_params.get("difficulty", "medium"),
            "retrieved_questions": similar_result.get("questions", []),
            "user_preferences": await self._memory_tool.search_user_preferences(
                self._run_context.user_id,
            ),
            "error_patterns": await self._memory_tool.search_error_patterns(
                user_id=self._run_context.user_id,
                subject=intent_params.get("subject", "数学"),
                course_topic=intent_params.get("course_topic", ""),
            ),
            "skill_hints": skill_hints,
            "control_signal": control_signal,
        }

        memory_context = await self._memory.execute(
            input_data=memory_input,
            context={"run_id": self._run_context.run_id},
        )

        self._record_tool_call(
            step_name="memory",
            tool_name="QuestionMemoryAgent",
            input_summary={"topic": intent_params.get("course_topic", "")},
            output_summary={
                "avoid_count": len(memory_context.get("avoid_list", [])),
                "skill_hints": len(memory_context.get("skill_hints", [])),
            },
        )

        return memory_context

    async def _step4_generate(
        self,
        plan_result: dict,
        memory_context: dict,
        control_signal: dict,
    ) -> dict[str, Any]:
        """L4: 题目生成"""
        intent_params = self._run_context.input_payload

        generated = await self._generator.execute(
            input_data={
                "age_group": intent_params.get("age_group", "10-12"),
                "subject": intent_params.get("subject", "数学"),
                "course_topic": intent_params.get("course_topic", ""),
                "difficulty": intent_params.get("difficulty", "medium"),
                "question_type": "choice",  # 按 plan 的题型分组生成
                "question_count": plan_result.get("planned_count", 10),
                "avoid_list": memory_context.get("avoid_list", []),
                "skill_hints": memory_context.get("skill_hints", []),
                "error_patterns": memory_context.get("error_patterns", []),
                "coverage_gaps": memory_context.get("coverage_gaps", []),
                "control_signal": control_signal,
            },
            context={"run_id": self._run_context.run_id},
        )

        self._record_tool_call(
            step_name="generate",
            tool_name="QuestionGeneratorAgent",
            input_summary={"topic": intent_params.get("course_topic", "")},
            output_summary={
                "count": len(generated.get("questions", [])),
                "deviation": generated.get("deviation_declaration") is not None,
            },
        )

        return generated

    async def _step5_quality_check(
        self, generated: dict, intent_params: dict
    ) -> list[dict]:
        """L5: 快速质量检查（每道题必检）"""
        questions = generated.get("questions", [])
        qc_results = []

        for question in questions:
            result = await self._quality_checker.execute(
                input_data={
                    "question": question,
                    "age_group": intent_params.get("age_group", "10-12"),
                    "subject": intent_params.get("subject", "数学"),
                    "expected_difficulty": intent_params.get("difficulty", "medium"),
                },
                context={"run_id": self._run_context.run_id},
            )
            qc_results.append(result)

            # 记录审计日志
            await self._audit_tool.log_quality_check(
                question_id=question.get("id", ""),
                passed=result.get("passed", False),
                score=result.get("score", 0),
                issues=result.get("issues", []),
                run_id=self._run_context.run_id,
            )

        passed_count = sum(1 for r in qc_results if r.get("passed"))
        self._record_tool_call(
            step_name="quality",
            tool_name="QualityCheckAgent",
            input_summary={"total": len(questions)},
            output_summary={"passed": passed_count, "failed": len(questions) - passed_count},
        )

        return qc_results

    async def _step6a_safety_audit(
        self, generated: dict, intent_params: dict
    ) -> list[dict]:
        """L6a: 四维安全审查（QC 通过的题目）"""
        questions = generated.get("questions", [])
        safety_results = []

        for question in questions:
            result = await self._safety_auditor.execute(
                input_data={
                    "question": question,
                    "age_group": intent_params.get("age_group", "10-12"),
                    "subject": intent_params.get("subject", "数学"),
                },
                context={"run_id": self._run_context.run_id},
            )
            safety_results.append(result)

            # 如果否决，通过 ErrorLogger 记录
            if result.get("verdict") == "REJECT":
                await self._error_logger.capture_safe_audit(
                    agent_name="SafetyAuditAgent",
                    step_name="safety_audit",
                    question_id=question.get("id", ""),
                    reason=result.get("blocking_issue", "未知原因"),
                    context={"question_preview": question.get("question_body", "")[:100]},
                )

            # 记录审计日志
            await self._audit_tool.log_safety_audit(
                question_id=question.get("id", ""),
                verdict=result.get("verdict", "PASS"),
                scores=result.get("scores", {}),
                issues=result.get("issues", []),
                blocking_issue=result.get("blocking_issue"),
                run_id=self._run_context.run_id,
            )

        return safety_results

    async def _step6b_quality_review(
        self, generated: dict, qc_results: list[dict]
    ) -> dict[str, Any]:
        """L6b: 抽样深度质量评估 + 趋势分析"""
        questions = generated.get("questions", [])
        intent_params = self._run_context.input_payload

        # 选择抽样题目
        sampled = self._quality_reviewer.select_samples(questions, qc_results)

        if not sampled:
            return {"trend": "stable", "system_quality_score": 0, "top_issues": []}

        trend_report = await self._quality_reviewer.execute(
            input_data={
                "sampled_questions": sampled,
                "quality_checks": qc_results,
                "historical_scores": [],
                "subject": intent_params.get("subject", "数学"),
                "age_group": intent_params.get("age_group", "10-12"),
            },
            context={"run_id": self._run_context.run_id},
        )

        self._record_tool_call(
            step_name="quality_review",
            tool_name="QualityReviewAgent",
            input_summary={"sampled": len(sampled), "total": len(questions)},
            output_summary={"trend": trend_report.get("trend", "stable")},
        )

        return trend_report

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _filter_passed_questions(
        self,
        questions: list[dict],
        qc_results: list[dict],
        safety_results: list[dict],
    ) -> list[dict]:
        """
        过滤通过的题目

        条件：QC 通过 AND 安全审查 PASS
        """
        qc_map = {r.get("question_id", ""): r for r in qc_results}
        safety_map = {r.get("question_id", ""): r for r in safety_results}

        passed = []
        for q in questions:
            qid = q.get("id", "")
            qc = qc_map.get(qid, {})
            safety = safety_map.get(qid, {})

            qc_passed = qc.get("passed", False)
            safety_passed = safety.get("verdict") == "PASS"

            if qc_passed and safety_passed:
                passed.append(q)

        return passed

    async def _save_questions(
        self,
        batch_id: str,
        questions: list[dict],
    ) -> None:
        """保存通过的题目"""
        await self._save_tool.save_batch(
            batch_id=batch_id,
            user_id=self._run_context.user_id,
            questions=questions,
            batch_meta={
                "age_group": self._run_context.input_payload.get("age_group", ""),
                "subject": self._run_context.input_payload.get("subject", ""),
                "course_topic": self._run_context.input_payload.get("course_topic", ""),
                "difficulty": self._run_context.input_payload.get("difficulty", "medium"),
                "prompt_version": "v0.1.0",
                "harness_run_id": self._run_context.run_id,
            },
        )

        self._record_tool_call(
            step_name="save",
            tool_name="QuestionSaveTool",
            input_summary={"batch_id": batch_id, "count": len(questions)},
            output_summary={"saved": len(questions)},
        )

    def _record_tool_call(
        self,
        step_name: str,
        tool_name: str,
        input_summary: dict,
        output_summary: Optional[dict] = None,
        status: str = "succeeded",
        error_message: Optional[str] = None,
    ) -> None:
        """
        记录工具调用日志

        所有工具调用必须记录。
        """
        if self._run_context:
            record = ToolCallRecord(
                step_name=step_name,
                tool_name=tool_name,
                input_summary=input_summary,
                output_summary=output_summary,
                latency_ms=0,
                status=status,
                error_message=error_message,
            )
            self._run_context.tool_call_logs.append(record)

    async def _persist_tool_logs(self) -> None:
        """持久化工具调用日志和审计日志"""
        if not self._run_context or not self._db_available():
            return

        # TODO: 当数据库模型就绪后持久化 ToolCallLog
        for log in self._run_context.tool_call_logs:
            logger.debug(
                f"[Harness] ToolCall: step={log.step_name} | "
                f"tool={log.tool_name} | status={log.status}"
            )

    def _db_available(self) -> bool:
        """检查数据库是否可用"""
        return self._memory_tool._db_session is not None

    async def run_summary(
        self,
        session_data: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """
        执行会话总结（L8 SummaryAgent）

        Args:
            session_data: 会话数据
            user_id: 用户 ID

        Returns:
            总结结果
        """
        return await self._summary.execute_summary(
            session_data=session_data,
            user_id=user_id,
        )

    def get_run_context(self) -> Optional[HarnessRunContext]:
        """获取当前运行上下文"""
        return self._run_context
