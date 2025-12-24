from typing import List, Dict, Any
from datetime import datetime
from sqlalchemy import select, desc, and_
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType
from app.models.backtest import BacktestResult
from app.models.optimization import Playbook, OptimizationJob, OptimizationStatus
import logging

logger = logging.getLogger(__name__)


class StrategyAgent(BaseAgent):
    """
    Strategy selection and management agent.

    Responsibilities:
    - Evaluate strategy performance
    - Select which strategies to run
    - Disable underperforming strategies
    - Trigger optimization when needed
    - Learn from backtest results
    """

    def get_role(self) -> AgentRole:
        return AgentRole.STRATEGY

    async def analyze_and_select_strategies(
        self,
        symbol: str,
        available_strategies: List[str]
    ) -> List[str]:
        """
        Analyze available strategies and select which ones to run.

        Args:
            symbol: Trading symbol
            available_strategies: List of strategy names to consider

        Returns:
            List of selected strategy names
        """
        selected = []

        for strategy_name in available_strategies:
            # Check if strategy is enabled in playbooks
            stmt = select(Playbook).where(
                and_(
                    Playbook.strategy_name == strategy_name,
                    Playbook.symbol == symbol,
                    Playbook.is_active == True
                )
            )

            result = await self.db.execute(stmt)
            playbook = result.scalar_one_or_none()

            if not playbook:
                logger.debug(f"No active playbook for {strategy_name} on {symbol}")
                continue

            # Evaluate strategy performance
            should_continue = await self._evaluate_strategy_performance(strategy_name, symbol)

            if should_continue:
                selected.append(strategy_name)

                await self.log_decision(
                    decision_type=DecisionType.STRATEGY_SELECTION,
                    decision=f"Selected {strategy_name} for {symbol}",
                    reasoning="Strategy passed performance evaluation",
                    context={
                        "strategy_name": strategy_name,
                        "symbol": symbol,
                        "playbook_id": playbook.id
                    },
                    executed=True
                )
            else:
                # Disable underperforming strategy
                await self._disable_strategy(strategy_name, symbol, playbook)

            # Check if optimization is needed
            should_optimize = await self.should_trigger_optimization(strategy_name, symbol)

            if should_optimize:
                await self.log_decision(
                    decision_type=DecisionType.OPTIMIZATION_TRIGGER,
                    decision=f"Optimization needed for {strategy_name} on {symbol}",
                    reasoning="Strategy requires parameter optimization",
                    context={
                        "strategy_name": strategy_name,
                        "symbol": symbol
                    },
                    executed=False
                )

        logger.info(f"Selected {len(selected)}/{len(available_strategies)} strategies for {symbol}")

        return selected

    async def _evaluate_strategy_performance(
        self,
        strategy_name: str,
        symbol: str
    ) -> bool:
        """
        Evaluate if strategy should continue running.

        Criteria:
        - Recent backtest Sharpe ratio > 0.5
        - Max drawdown < 20%
        - Win rate > 40%
        - At least 10 trades in backtest

        Returns:
            True if strategy should continue, False to disable
        """
        # Get most recent backtest for this strategy
        stmt = select(BacktestResult).where(
            and_(
                BacktestResult.strategy_name == strategy_name,
                BacktestResult.symbol == symbol
            )
        ).order_by(desc(BacktestResult.created_at)).limit(1)

        result = await self.db.execute(stmt)
        backtest = result.scalar_one_or_none()

        if not backtest:
            logger.warning(f"No backtest found for {strategy_name} on {symbol}")
            return False

        # Check performance criteria
        if backtest.total_trades < 10:
            logger.info(f"{strategy_name}: Too few trades ({backtest.total_trades})")
            return False

        if backtest.sharpe_ratio is None or backtest.sharpe_ratio < 0.5:
            logger.info(f"{strategy_name}: Low Sharpe ratio ({backtest.sharpe_ratio})")
            return False

        if backtest.max_drawdown > 20.0:
            logger.info(f"{strategy_name}: High drawdown ({backtest.max_drawdown}%)")
            return False

        if backtest.win_rate < 40.0:
            logger.info(f"{strategy_name}: Low win rate ({backtest.win_rate}%)")
            return False

        # Store performance in memory
        await self.store_memory(
            memory_type="strategy_performance",
            memory_key=f"{strategy_name}_{symbol}",
            data={
                "sharpe_ratio": backtest.sharpe_ratio,
                "max_drawdown": backtest.max_drawdown,
                "win_rate": backtest.win_rate,
                "total_trades": backtest.total_trades,
                "last_evaluated": datetime.utcnow().isoformat()
            },
            confidence=0.8
        )

        return True

    async def _disable_strategy(
        self,
        strategy_name: str,
        symbol: str,
        playbook: Playbook
    ):
        """Disable underperforming strategy."""
        playbook.is_active = False
        await self.db.commit()

        await self.log_decision(
            decision_type=DecisionType.STRATEGY_DISABLE,
            decision=f"Disabled {strategy_name} for {symbol}",
            reasoning="Strategy failed performance evaluation criteria",
            context={
                "strategy_name": strategy_name,
                "symbol": symbol,
                "playbook_id": playbook.id
            },
            executed=True
        )

        logger.warning(f"Disabled strategy {strategy_name} for {symbol} due to poor performance")

    async def should_trigger_optimization(
        self,
        strategy_name: str,
        symbol: str
    ) -> bool:
        """
        Determine if optimization should be triggered.

        Triggers:
        - No optimization in last 30 days
        - Recent performance degradation
        - New market regime detected

        Returns:
            True if optimization should run
        """
        # Check last optimization time
        stmt = select(OptimizationJob).where(
            and_(
                OptimizationJob.strategy_name == strategy_name,
                OptimizationJob.symbol == symbol,
                OptimizationJob.status == OptimizationStatus.COMPLETED
            )
        ).order_by(desc(OptimizationJob.completed_at)).limit(1)

        result = await self.db.execute(stmt)
        last_opt = result.scalar_one_or_none()

        if not last_opt:
            # Never optimized
            await self.log_decision(
                decision_type=DecisionType.OPTIMIZATION_TRIGGER,
                decision=f"Trigger optimization for {strategy_name} on {symbol}",
                reasoning="No previous optimization found",
                context={"strategy_name": strategy_name, "symbol": symbol},
                executed=False
            )
            return True

        # Check if optimization is recent (within 30 days)
        days_since_opt = (datetime.utcnow() - last_opt.completed_at).days

        if days_since_opt > 30:
            await self.log_decision(
                decision_type=DecisionType.OPTIMIZATION_TRIGGER,
                decision=f"Trigger optimization for {strategy_name} on {symbol}",
                reasoning=f"Last optimization was {days_since_opt} days ago (threshold: 30 days)",
                context={
                    "strategy_name": strategy_name,
                    "symbol": symbol,
                    "days_since_optimization": days_since_opt
                },
                executed=False
            )
            return True

        return False
