"""
FeedbackAggregator — PID 计算 + 状态观测 + 控制信号生成

内嵌于 AI Harness 中，是系统唯一的控制信号生产者。

职责：
1. 偏差信号汇聚：接收 L5 (QualityCheckAgent) 和 L6 (SafetyAuditAgent/QualityReviewAgent) 的偏差信号
2. PID 三分量计算：
   - P（比例）：当前批次的质量通过率偏差 → 即时纠正力度
   - I（积分）：过去 N 次生成的累计质量偏差方向 → 系统性修正触发
   - D（微分）：质量变化斜率 → 趋势干预策略
3. 控制信号生成：将 PID 结果转换为可注入 L2/L3/L4 的 ControlSignal
4. 状态观测器维护：更新质量基线、用户能力估计、知识覆盖度、重复风险

关键约束：
- FeedbackAggregator 是唯一的控制信号生产者
- Agent 不得自行计算 PID 参数或生成控制信号
"""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime
from typing import Any, Optional

from backend.app.ai.schemas import ControlSignal

logger = logging.getLogger(__name__)

# PID 控制参数
P_GAIN = 1.0          # 比例增益
I_GAIN = 0.1          # 积分增益
D_GAIN = 0.5          # 微分增益

# 质量通过率阈值
QUALITY_PASS_TARGET = 0.8  # 目标通过率 80%

# 状态观测器参数
BASELINE_WINDOW = 50     # 质量基线窗口大小
HISTORY_WINDOW = 10      # I 分量历史窗口
DUPLICATE_RISK_THRESHOLD = 0.5  # 重复风险阈值

# PID 输出限幅
MAX_DIFFICULTY_DELTA = 1.0
MAX_COUNT_DELTA = 10


class FeedbackAggregator:
    """
    反馈聚合器 — PID 控制器

    接收偏差信号，计算 PID 三分量，生成 ControlSignal。
    维护系统状态观测器。
    """

    def __init__(self):
        """初始化 FeedbackAggregator"""
        # 历史质量分数（用于 I 和 D 分量计算）
        self._quality_history: deque[float] = deque(maxlen=BASELINE_WINDOW)
        # 历史通过率（用于 I 分量计算）
        self._pass_rate_history: deque[float] = deque(maxlen=HISTORY_WINDOW)
        # 安全否决计数
        self._safety_reject_count: int = 0
        # 循环计数
        self._iteration: int = 0
        # 当前控制信号
        self._current_signal: Optional[ControlSignal] = None

        # 状态观测器
        self._state = {
            "quality_baseline": 0.0,      # 最近 N 题平均质量分
            "ability": 0.5,                # 用户能力估计
            "coverage": 0.0,              # 知识点覆盖度
            "duplicate_risk": 0.0,         # 重复风险
        }

    def reset(self) -> None:
        """重置状态（新会话开始时调用）"""
        self._quality_history.clear()
        self._pass_rate_history.clear()
        self._safety_reject_count = 0
        self._iteration = 0
        self._current_signal = None
        self._state = {
            "quality_baseline": 0.0,
            "ability": 0.5,
            "coverage": 0.0,
            "duplicate_risk": 0.0,
        }

    def ingest_quality_checks(
        self,
        quick_check_results: list[dict[str, Any]],
    ) -> None:
        """
        接收 QualityCheckAgent 的快速检查结果

        Args:
            quick_check_results: QuickCheckResult 列表
        """
        if not quick_check_results:
            return

        total_score = 0.0
        pass_count = 0
        for result in quick_check_results:
            score = result.get("score", 0)
            total_score += score
            self._quality_history.append(score)
            if result.get("passed", False):
                pass_count += 1

        pass_rate = pass_count / len(quick_check_results)
        self._pass_rate_history.append(pass_rate)

        logger.debug(
            f"[FeedbackAggregator] 质量数据摄入: "
            f"n={len(quick_check_results)} | "
            f"avg_score={total_score / len(quick_check_results):.1f} | "
            f"pass_rate={pass_rate:.2f}"
        )

    def ingest_safety_audits(
        self,
        safety_audit_results: list[dict[str, Any]],
    ) -> None:
        """
        接收 SafetyAuditAgent 的安全审查结果

        Args:
            safety_audit_results: SafetyAuditResult 列表
        """
        reject_count = sum(
            1 for r in safety_audit_results
            if r.get("verdict") == "REJECT"
        )
        self._safety_reject_count += reject_count

        # 安全否决更新重复风险评估
        if reject_count > 0:
            self._state["duplicate_risk"] = min(
                1.0,
                self._state["duplicate_risk"] + 0.1 * reject_count,
            )

    def ingest_quality_trend(
        self,
        trend_report: dict[str, Any],
    ) -> None:
        """
        接收 QualityReviewAgent 的质量趋势报告

        Args:
            trend_report: QualityTrendReport
        """
        # 更新系统质量分数
        sys_score = trend_report.get("system_quality_score", 0)
        if sys_score > 0:
            self._quality_history.append(sys_score)

        # 趋势影响 I 分量（通过 pass_rate_history 的方向体现）
        # 这里不做额外处理，因为 D 分量已经通过 history 计算了趋势

        # 应用推荐调整
        adjustments = trend_report.get("recommended_adjustments", {})
        if adjustments:
            logger.info(
                f"[FeedbackAggregator] 接收 QR 推荐调整: {adjustments}"
            )

    def compute_control_signal(self) -> ControlSignal:
        """
        计算 PID 三分量并生成 ControlSignal

        这是 FeedbackAggregator 的核心方法。

        Returns:
            ControlSignal 实例
        """
        self._iteration += 1

        # --- P 分量（比例）---
        # 当前批次通过率偏差
        if self._pass_rate_history:
            current_pass_rate = self._pass_rate_history[-1]
        else:
            current_pass_rate = QUALITY_PASS_TARGET

        p_error = current_pass_rate - QUALITY_PASS_TARGET
        # P 分量直接使用偏差值

        # --- I 分量（积分）---
        # 历史偏差方向
        if len(self._pass_rate_history) >= 3:
            # 计算历史通过率趋势
            rates = list(self._pass_rate_history)
            recent_avg = sum(rates[-3:]) / 3
            older_avg = sum(rates[:-3]) / max(1, len(rates) - 3) if len(rates) > 3 else recent_avg

            if recent_avg > older_avg + 0.05:
                i_drift = "improving"
            elif recent_avg < older_avg - 0.05:
                i_drift = "declining"
            else:
                i_drift = "stable"
        else:
            i_drift = "stable"

        # --- D 分量（微分）---
        # 质量变化斜率
        if len(self._quality_history) >= 3:
            scores = list(self._quality_history)
            recent_avg = sum(scores[-3:]) / 3
            older_avg = sum(scores[-3:-6]) / 3 if len(scores) >= 6 else recent_avg

            slope = recent_avg - older_avg
            if slope > 3:
                d_slope = "positive"
            elif slope < -3:
                d_slope = "negative"
            else:
                d_slope = "zero"
        else:
            d_slope = "zero"

        # --- 计算调整量 ---
        # 难度调整
        difficulty_delta = 0.0
        if p_error < -0.2:
            # 通过率过低，降低难度
            difficulty_delta = -1.0
        elif p_error < -0.1:
            difficulty_delta = -0.5
        elif p_error > 0.15:
            # 通过率很高，可以增加难度
            difficulty_delta = 0.5
        elif p_error > 0.2:
            difficulty_delta = 1.0

        # I 分量影响：长期下降则额外降低难度
        if i_drift == "declining":
            difficulty_delta = max(-MAX_DIFFICULTY_DELTA, difficulty_delta - 0.3)

        # D 分量影响：趋势恶化则紧急干预
        if d_slope == "negative":
            difficulty_delta = max(-MAX_DIFFICULTY_DELTA, difficulty_delta - 0.5)

        # 限幅
        difficulty_delta = max(-MAX_DIFFICULTY_DELTA, min(MAX_DIFFICULTY_DELTA, difficulty_delta))

        # 数量调整（安全否决多则减少生成量）
        count_delta = 0
        if self._safety_reject_count > 3:
            count_delta = -2

        # 知识覆盖范围建议
        topic_scope = ""
        coverage = self._update_coverage()
        if coverage < 0.5:
            topic_scope = "扩大知识点覆盖范围"

        # --- 更新状态观测器 ---
        self._update_state_estimator()

        # --- 生成 ControlSignal ---
        signal = ControlSignal(
            pid={
                "p_error": round(p_error, 4),
                "i_drift": i_drift,
                "d_slope": d_slope,
            },
            adjustments={
                "difficulty_delta": round(difficulty_delta, 2),
                "count_delta": count_delta,
                "topic_scope": topic_scope,
            },
            state_estimate={
                "quality_baseline": round(self._state["quality_baseline"], 2),
                "ability": round(self._state["ability"], 3),
                "coverage": round(coverage, 3),
                "duplicate_risk": round(self._state["duplicate_risk"], 3),
            },
            iteration=self._iteration,
        )

        self._current_signal = signal

        logger.info(
            f"[FeedbackAggregator] 控制信号生成 | iter={self._iteration} | "
            f"P={p_error:.4f} | I={i_drift} | D={d_slope} | "
            f"diff_delta={difficulty_delta:.2f} | "
            f"quality_baseline={self._state['quality_baseline']:.1f} | "
            f"rejects={self._safety_reject_count}"
        )

        return signal

    def _update_state_estimator(self) -> None:
        """更新状态观测器"""
        # 质量基线
        if self._quality_history:
            self._state["quality_baseline"] = (
                sum(self._quality_history) / len(self._quality_history)
            )

        # 用户能力估计（基于通过率）
        if self._pass_rate_history:
            avg_rate = sum(self._pass_rate_history) / len(self._pass_rate_history)
            # 能力估计平滑更新
            self._state["ability"] = (
                self._state["ability"] * 0.7 + avg_rate * 0.3
            )

    def _update_coverage(self) -> float:
        """
        更新知识覆盖度（简化实现）

        Returns:
            覆盖度 (0-1)
        """
        # v0.1 简化：覆盖度基于生成的题目数量和多样性
        # 后续可通过知识点标签精确计算
        coverage = min(1.0, len(self._quality_history) / BASELINE_WINDOW)
        self._state["coverage"] = coverage
        return coverage

    @property
    def current_signal(self) -> Optional[ControlSignal]:
        """获取当前控制信号"""
        return self._current_signal

    @property
    def iteration(self) -> int:
        """获取当前循环编号"""
        return self._iteration

    @property
    def state(self) -> dict[str, float]:
        """获取状态观测器"""
        return self._state.copy()

    def get_signal_dict(self) -> dict[str, Any]:
        """获取控制信号的字典表示（方便注入 Prompt）"""
        if self._current_signal:
            return self._current_signal.model_dump()
        return ControlSignal().model_dump()
