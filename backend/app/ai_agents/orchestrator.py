from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.ai_agents.supervisor_agent import SupervisorAgent
from app.ai_agents.strategy_agent import StrategyAgent
from app.ai_agents.risk_agent import RiskAgent
from app.ai_agents.execution_agent import ExecutionAgent
from app.models.ai_agent import SystemMode, SystemConfig
from app.models.signal import Signal, SignalStatus
import logging

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """
    Master orchestrator for AI agent system.

    Coordinates all agents and enforces mode-specific behavior.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.system_mode = None
        self.supervisor = None
        self.strategy_agent = None
        self.risk_agent = None
        self.execution_agent = None

    async def initialize(self):
        """Initialize orchestrator and load system mode."""
        # Load system mode from config
        stmt = select(SystemConfig).where(SystemConfig.key == "system_mode")
        result = await self.db.execute(stmt)
        config = result.scalar_one_or_none()

        if config:
            mode_str = config.value.get("mode", "guide")
            self.system_mode = SystemMode.GUIDE if mode_str == "guide" else SystemMode.AUTONOMOUS
        else:
            # Default to GUIDE mode
            self.system_mode = SystemMode.GUIDE
            config = SystemConfig(
                key="system_mode",
                value={"mode": "guide"},
                description="Current system operating mode (guide or autonomous)"
            )
            self.db.add(config)
            await self.db.commit()

        # Initialize agents
        self.supervisor = SupervisorAgent(db=self.db, system_mode=self.system_mode)
        self.strategy_agent = StrategyAgent(db=self.db, system_mode=self.system_mode)
        self.risk_agent = RiskAgent(db=self.db, system_mode=self.system_mode)
        self.execution_agent = ExecutionAgent(db=self.db, system_mode=self.system_mode)

        logger.info(f"AI Orchestrator initialized in {self.system_mode.value} mode")

    async def run_trading_cycle(
        self,
        symbol: str,
        available_strategies: List[str],
        account_balance: float,
        peak_balance: float
    ) -> Dict[str, Any]:
        """
        Execute one complete trading cycle.

        Steps:
        1. Supervisor enforces mode
        2. Strategy agent selects strategies
        3. Risk agent validates signals
        4. Execution agent executes trades

        Args:
            symbol: Trading symbol
            available_strategies: List of strategy names
            account_balance: Current account balance
            peak_balance: Peak account balance

        Returns:
            Cycle execution summary
        """
        cycle_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "mode": self.system_mode.value,
            "symbol": symbol,
            "strategies_selected": [],
            "signals_validated": 0,
            "trades_executed": 0,
            "errors": []
        }

        try:
            # Step 1: Mode enforcement
            mode_ok = await self.supervisor.enforce_mode()
            if not mode_ok:
                cycle_result["errors"].append("Mode enforcement failed")
                return cycle_result

            # Step 2: Emergency check
            emergency = await self.risk_agent.check_emergency_conditions(account_balance, peak_balance)
            if emergency:
                cycle_result["errors"].append("Emergency shutdown triggered")
                return cycle_result

            # Step 3: Select strategies
            selected_strategies = await self.strategy_agent.analyze_and_select_strategies(
                symbol=symbol,
                available_strategies=available_strategies
            )

            cycle_result["strategies_selected"] = selected_strategies

            if not selected_strategies:
                logger.info(f"No strategies selected for {symbol}")
                return cycle_result

            # Step 4: Get pending signals
            stmt = select(Signal).where(
                Signal.symbol == symbol,
                Signal.status == SignalStatus.PENDING
            )

            result = await self.db.execute(stmt)
            pending_signals = result.scalars().all()

            # Step 5: Validate and execute signals
            for signal in pending_signals:
                # Risk validation
                validation = await self.risk_agent.validate_signal(signal, account_balance)

                if validation["approved"]:
                    cycle_result["signals_validated"] += 1

                    # Execute (or simulate)
                    position = await self.execution_agent.execute_signal(
                        signal=signal,
                        position_size=validation["position_size"],
                        account_balance=account_balance
                    )

                    if position:
                        cycle_result["trades_executed"] += 1

            logger.info(f"Trading cycle complete: {cycle_result['signals_validated']} validated, {cycle_result['trades_executed']} executed")

            return cycle_result

        except Exception as e:
            logger.error(f"Trading cycle error: {e}")
            cycle_result["errors"].append(str(e))
            return cycle_result
