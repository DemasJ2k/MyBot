from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from app.ai_agents.base_agent import BaseAgent
from app.models.ai_agent import AgentRole, DecisionType, SystemMode
from app.models.signal import Signal, SignalStatus
from app.models.position import Position, PositionStatus, PositionSide
import logging

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """
    Trade execution agent.

    Responsibilities:
    - Execute approved signals
    - Manage open positions
    - Update stop loss / take profit
    - Close positions
    - GUIDE mode: Simulate only, no real execution
    - AUTONOMOUS mode: Execute live trades
    """

    def get_role(self) -> AgentRole:
        return AgentRole.EXECUTION

    async def execute_signal(
        self,
        signal: Signal,
        position_size: float,
        account_balance: float
    ) -> Optional[Position]:
        """
        Execute a validated trading signal.

        In GUIDE mode: Logs recommendation only
        In AUTONOMOUS mode: Creates real position

        Args:
            signal: Approved signal
            position_size: Validated position size
            account_balance: Current account balance

        Returns:
            Position object if executed, None otherwise
        """
        if self.system_mode == SystemMode.GUIDE:
            # GUIDE MODE: Simulate only, do not execute
            await self.log_decision(
                decision_type=DecisionType.TRADE_EXECUTION,
                decision=f"SIMULATED: Would execute {signal.signal_type.value} {signal.symbol}",
                reasoning="System is in GUIDE mode - execution is simulated",
                context={
                    "signal_id": signal.id,
                    "strategy": signal.strategy_name,
                    "symbol": signal.symbol,
                    "entry_price": signal.entry_price,
                    "position_size": position_size,
                    "mode": "guide"
                },
                executed=False
            )

            logger.info(f"GUIDE MODE: Simulated execution of {signal.strategy_name} {signal.signal_type.value} {signal.symbol}")
            return None

        else:
            # AUTONOMOUS MODE: Execute live trade
            position = Position(
                user_id=signal.user_id,
                strategy_name=signal.strategy_name,
                symbol=signal.symbol,
                side=PositionSide.LONG if signal.signal_type.value == "long" else PositionSide.SHORT,
                status=PositionStatus.OPEN,
                entry_price=signal.entry_price,
                position_size=position_size,
                entry_time=datetime.utcnow(),
                stop_loss=signal.stop_loss,
                take_profit=signal.take_profit,
                unrealized_pnl=0.0
            )

            self.db.add(position)

            # Update signal status
            signal.status = SignalStatus.EXECUTED
            signal.executed_at = datetime.utcnow()
            signal.position_size = position_size

            await self.db.commit()
            await self.db.refresh(position)

            await self.log_decision(
                decision_type=DecisionType.TRADE_EXECUTION,
                decision=f"EXECUTED: {signal.signal_type.value} {signal.symbol} @ {signal.entry_price}",
                reasoning=f"Live execution in AUTONOMOUS mode for {signal.strategy_name}",
                context={
                    "signal_id": signal.id,
                    "position_id": position.id,
                    "strategy": signal.strategy_name,
                    "symbol": signal.symbol,
                    "side": position.side.value,
                    "entry_price": signal.entry_price,
                    "position_size": position_size,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "mode": "autonomous"
                },
                executed=True
            )

            logger.info(f"AUTONOMOUS MODE: Executed {signal.strategy_name} {signal.signal_type.value} {signal.symbol} @ {signal.entry_price}")

            return position

    async def close_position(
        self,
        position: Position,
        exit_price: float,
        reason: str
    ) -> Position:
        """
        Close an open position.

        Args:
            position: Position to close
            exit_price: Exit price
            reason: Reason for closing

        Returns:
            Updated position
        """
        position.status = PositionStatus.CLOSED
        position.exit_price = exit_price
        position.exit_time = datetime.utcnow()

        # Calculate realized P&L
        if position.side == PositionSide.LONG:
            pnl = (exit_price - position.entry_price) * position.position_size
        else:
            pnl = (position.entry_price - exit_price) * position.position_size

        position.realized_pnl = pnl

        await self.db.commit()

        await self.log_decision(
            decision_type=DecisionType.TRADE_EXECUTION,
            decision=f"CLOSED: {position.side.value} {position.symbol} @ {exit_price}",
            reasoning=reason,
            context={
                "position_id": position.id,
                "strategy": position.strategy_name,
                "symbol": position.symbol,
                "entry_price": position.entry_price,
                "exit_price": exit_price,
                "pnl": pnl,
                "reason": reason
            },
            executed=True
        )

        logger.info(f"Closed position {position.id}: {position.symbol} P&L={pnl:.2f}")

        return position
