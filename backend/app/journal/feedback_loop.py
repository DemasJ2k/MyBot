"""
AI Feedback Loop for learning and automatic adjustments.

Analyzes journal performance and triggers deterministic actions.
Prompt 11 - Journaling and Feedback Loop.
"""

from typing import Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.journal.analyzer import PerformanceAnalyzer
from app.models.journal import FeedbackDecision
from app.models.optimization import OptimizationJob, OptimizationStatus
from app.models.risk import StrategyRiskBudget
import logging

logger = logging.getLogger(__name__)


class FeedbackLoop:
    """
    AI feedback loop that learns from journal and triggers actions.

    Deterministic and auditable.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.analyzer = PerformanceAnalyzer(db)

    async def run_feedback_cycle(
        self,
        strategy_name: str,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Run one feedback cycle for a strategy.

        Steps:
        1. Analyze performance from journal
        2. Detect underperformance patterns
        3. Determine action
        4. Log decision
        5. Execute action (if appropriate)

        Args:
            strategy_name: Strategy name
            symbol: Symbol

        Returns:
            Feedback cycle result
        """
        logger.info(f"Running feedback cycle for {strategy_name} on {symbol}")

        # Step 1: Analyze performance
        underperformance = await self.analyzer.detect_underperformance(strategy_name, symbol)

        # Step 2: Determine action
        if not underperformance["underperforming"]:
            logger.info(f"{strategy_name} on {symbol} is performing normally")
            return {
                "action": "none",
                "reason": "Performance within acceptable range",
                "underperformance": underperformance
            }

        recommendation = underperformance["recommendation"]

        # Step 3: Log decision
        decision = await self._log_decision(
            strategy_name=strategy_name,
            symbol=symbol,
            analysis=underperformance,
            recommendation=recommendation
        )

        # Step 4: Execute action
        result = await self._execute_action(
            decision_id=decision.id,
            strategy_name=strategy_name,
            symbol=symbol,
            recommendation=recommendation
        )

        return {
            "action": recommendation,
            "decision_id": decision.id,
            "execution_result": result,
            "underperformance": underperformance
        }

    async def _log_decision(
        self,
        strategy_name: str,
        symbol: str,
        analysis: Dict[str, Any],
        recommendation: str
    ) -> FeedbackDecision:
        """Log feedback decision to audit trail."""
        decision = FeedbackDecision(
            decision_type=recommendation,
            strategy_name=strategy_name,
            symbol=symbol,
            analysis=analysis,
            action_taken=f"Recommendation: {recommendation}",
            executed=False,
            decision_time=datetime.utcnow()
        )

        self.db.add(decision)
        await self.db.commit()
        await self.db.refresh(decision)

        logger.info(f"Feedback decision logged: {decision.id} - {recommendation}")

        return decision

    async def _execute_action(
        self,
        decision_id: int,
        strategy_name: str,
        symbol: str,
        recommendation: str
    ) -> str:
        """Execute feedback action."""
        stmt = select(FeedbackDecision).where(FeedbackDecision.id == decision_id)
        result = await self.db.execute(stmt)
        decision = result.scalar_one_or_none()

        if not decision:
            return "Decision not found"

        if recommendation == "trigger_optimization":
            execution_result = await self._handle_trigger_optimization(
                decision, strategy_name, symbol
            )

        elif recommendation == "disable_strategy":
            execution_result = await self._handle_disable_strategy(
                decision, strategy_name, symbol
            )

        elif recommendation == "monitor_closely":
            execution_result = await self._handle_monitor_closely(decision)

        else:
            execution_result = f"Unknown recommendation: {recommendation}"

        return execution_result

    async def _handle_trigger_optimization(
        self,
        decision: FeedbackDecision,
        strategy_name: str,
        symbol: str
    ) -> str:
        """Handle trigger_optimization recommendation."""
        # Check if optimization already running
        stmt = select(OptimizationJob).where(
            OptimizationJob.strategy_name == strategy_name,
            OptimizationJob.symbol == symbol,
            OptimizationJob.status.in_([OptimizationStatus.PENDING, OptimizationStatus.RUNNING])
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            execution_result = f"Optimization already in progress (job {existing.id})"
        else:
            # Mark that optimization should be triggered
            # The actual job creation would be done by the optimization service
            execution_result = (
                f"Optimization recommended for {strategy_name} on {symbol}. "
                "Create optimization job via /optimization/jobs endpoint."
            )

        decision.executed = True
        decision.executed_at = datetime.utcnow()
        decision.execution_result = execution_result
        decision.action_params = {
            "recommended_action": "create_optimization_job",
            "strategy_name": strategy_name,
            "symbol": symbol
        }
        await self.db.commit()

        logger.info(f"Triggered optimization recommendation for {strategy_name} on {symbol}")
        return execution_result

    async def _handle_disable_strategy(
        self,
        decision: FeedbackDecision,
        strategy_name: str,
        symbol: str
    ) -> str:
        """Handle disable_strategy recommendation."""
        # Disable strategy in risk budget
        stmt = select(StrategyRiskBudget).where(
            StrategyRiskBudget.strategy_name == strategy_name,
            StrategyRiskBudget.symbol == symbol
        )
        result = await self.db.execute(stmt)
        budget = result.scalar_one_or_none()

        if budget:
            budget.is_enabled = False
            budget.disabled_reason = "AI feedback loop: Underperformance detected"
            budget.last_updated = datetime.utcnow()
            await self.db.commit()

            execution_result = f"Strategy {strategy_name} disabled in risk budget for {symbol}"
        else:
            execution_result = f"Risk budget not found for {strategy_name} on {symbol}"

        decision.executed = True
        decision.executed_at = datetime.utcnow()
        decision.execution_result = execution_result
        decision.action_params = {
            "action_taken": "disable_strategy",
            "strategy_name": strategy_name,
            "symbol": symbol,
            "budget_found": budget is not None
        }
        await self.db.commit()

        logger.warning(f"Disabled {strategy_name} on {symbol} due to underperformance")
        return execution_result

    async def _handle_monitor_closely(self, decision: FeedbackDecision) -> str:
        """Handle monitor_closely recommendation."""
        execution_result = "Monitoring enabled - no immediate action taken"

        decision.executed = True
        decision.executed_at = datetime.utcnow()
        decision.execution_result = execution_result
        decision.action_params = {
            "action_taken": "monitor_closely",
            "note": "Strategy flagged for close monitoring"
        }
        await self.db.commit()

        return execution_result

    async def get_decision_history(
        self,
        strategy_name: str | None = None,
        symbol: str | None = None,
        limit: int = 50
    ) -> list[Dict[str, Any]]:
        """
        Get feedback decision history.

        Args:
            strategy_name: Filter by strategy name
            symbol: Filter by symbol
            limit: Maximum number of decisions to return

        Returns:
            List of decision records
        """
        stmt = select(FeedbackDecision)

        if strategy_name:
            stmt = stmt.where(FeedbackDecision.strategy_name == strategy_name)
        if symbol:
            stmt = stmt.where(FeedbackDecision.symbol == symbol)

        stmt = stmt.order_by(FeedbackDecision.decision_time.desc()).limit(limit)

        result = await self.db.execute(stmt)
        decisions = result.scalars().all()

        return [
            {
                "id": d.id,
                "decision_type": d.decision_type,
                "strategy_name": d.strategy_name,
                "symbol": d.symbol,
                "analysis": d.analysis,
                "action_taken": d.action_taken,
                "action_params": d.action_params,
                "executed": d.executed,
                "execution_result": d.execution_result,
                "decision_time": d.decision_time.isoformat() if d.decision_time else None,
                "executed_at": d.executed_at.isoformat() if d.executed_at else None
            }
            for d in decisions
        ]

    async def run_batch_feedback(
        self,
        strategies: list[tuple[str, str]]
    ) -> Dict[str, Any]:
        """
        Run feedback cycle for multiple strategy/symbol pairs.

        Args:
            strategies: List of (strategy_name, symbol) tuples

        Returns:
            Batch results
        """
        results = {}
        actions_taken = []

        for strategy_name, symbol in strategies:
            try:
                result = await self.run_feedback_cycle(strategy_name, symbol)
                results[f"{strategy_name}:{symbol}"] = result

                if result["action"] != "none":
                    actions_taken.append({
                        "strategy": strategy_name,
                        "symbol": symbol,
                        "action": result["action"]
                    })

            except Exception as e:
                logger.error(f"Error in feedback cycle for {strategy_name} on {symbol}: {e}")
                results[f"{strategy_name}:{symbol}"] = {
                    "action": "error",
                    "error": str(e)
                }

        return {
            "total_analyzed": len(strategies),
            "actions_taken": len(actions_taken),
            "actions": actions_taken,
            "details": results
        }
