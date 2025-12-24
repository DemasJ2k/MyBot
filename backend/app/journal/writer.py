"""
Journal Writer for recording trades.

Writes immutable journal entries for all trades (backtest, live, paper).
Prompt 11 - Journaling and Feedback Loop.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.journal import JournalEntry, TradeSource
from app.models.position import Position
from app.backtest.portfolio import Trade
import uuid
import logging

logger = logging.getLogger(__name__)


class JournalWriter:
    """
    Writes immutable journal entries for all trades.

    Journal is the SINGLE SOURCE OF TRUTH for performance analysis.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def record_backtest_trade(
        self,
        trade: Trade,
        strategy_name: str,
        strategy_config: Dict[str, Any],
        backtest_id: str,
        market_context: Optional[Dict[str, Any]] = None,
        timeframe: str = "unknown"
    ) -> JournalEntry:
        """
        Record a backtest trade to journal.

        Args:
            trade: Trade from backtest
            strategy_name: Strategy name
            strategy_config: Strategy configuration used
            backtest_id: Backtest result ID
            market_context: Market conditions at trade time
            timeframe: Timeframe used for the backtest

        Returns:
            Created journal entry
        """
        duration_minutes = int((trade.exit_time - trade.entry_time).total_seconds() / 60)

        # Determine exit reason
        exit_reason = "unknown"
        if hasattr(trade, "reason") and trade.reason:
            exit_reason = trade.reason

        # Calculate metrics
        is_winner = trade.pnl > 0
        
        # Calculate pnl_percent from trade's pnl_percent if available
        pnl_percent = trade.pnl_percent if hasattr(trade, "pnl_percent") else 0.0

        entry_id = f"BT_{backtest_id[:8]}_{uuid.uuid4().hex[:8]}"

        # Get side value - handle both string and enum
        side_value = trade.side.value if hasattr(trade.side, "value") else str(trade.side).lower()

        entry = JournalEntry(
            entry_id=entry_id,
            source=TradeSource.BACKTEST,
            strategy_name=strategy_name,
            strategy_config=strategy_config,
            symbol=trade.symbol,
            timeframe=timeframe,
            side=side_value,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            position_size=trade.quantity,
            stop_loss=0.0,  # Not tracked in simple backtest
            take_profit=0.0,
            risk_percent=2.0,  # Default assumption
            risk_reward_ratio=2.0,  # Default assumption
            pnl=trade.pnl - trade.commission,  # Net P&L
            pnl_percent=pnl_percent,
            is_winner=is_winner,
            exit_reason=exit_reason,
            entry_slippage=0.0,
            exit_slippage=0.0,
            commission=trade.commission,
            market_context=market_context or {},
            entry_time=trade.entry_time,
            exit_time=trade.exit_time,
            duration_minutes=duration_minutes,
            backtest_id=backtest_id
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"Recorded backtest trade: {entry_id} P&L={entry.pnl:.2f}")

        return entry

    async def record_live_trade(
        self,
        position: Position,
        strategy_config: Dict[str, Any],
        execution_order_id: int,
        signal_id: Optional[int] = None,
        market_context: Optional[Dict[str, Any]] = None,
        timeframe: str = "unknown"
    ) -> JournalEntry:
        """
        Record a live trade to journal.

        Args:
            position: Closed position
            strategy_config: Strategy configuration used
            execution_order_id: Execution order ID
            signal_id: Signal ID that generated trade
            market_context: Market conditions at trade time
            timeframe: Timeframe of the strategy

        Returns:
            Created journal entry
        """
        if position.exit_time is None or position.realized_pnl is None:
            raise ValueError("Cannot journal open position")

        duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)

        # Calculate metrics
        is_winner = position.realized_pnl > 0
        risk_amount = abs(position.entry_price - position.stop_loss) * position.position_size
        reward_amount = abs(position.take_profit - position.entry_price) * position.position_size
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0

        pnl_percent = (position.realized_pnl / (position.entry_price * position.position_size) * 100.0) if position.entry_price > 0 else 0.0

        # Determine exit reason
        exit_reason = "manual"  # Default
        if abs(position.exit_price - position.stop_loss) < 0.0001:
            exit_reason = "sl"
        elif abs(position.exit_price - position.take_profit) < 0.0001:
            exit_reason = "tp"

        entry_id = f"LIVE_{execution_order_id}_{uuid.uuid4().hex[:8]}"

        # Get side value - handle both string and enum
        side_value = position.side.value if hasattr(position.side, "value") else str(position.side).lower()

        entry = JournalEntry(
            entry_id=entry_id,
            source=TradeSource.LIVE,
            strategy_name=position.strategy_name,
            strategy_config=strategy_config,
            symbol=position.symbol,
            timeframe=timeframe,
            side=side_value,
            entry_price=position.entry_price,
            exit_price=position.exit_price,
            position_size=position.position_size,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            risk_percent=2.0,  # Would need to calculate from account balance
            risk_reward_ratio=rr_ratio,
            pnl=position.realized_pnl,
            pnl_percent=pnl_percent,
            is_winner=is_winner,
            exit_reason=exit_reason,
            entry_slippage=0.0,  # Would need actual execution data
            exit_slippage=0.0,
            commission=position.commission_paid,
            market_context=market_context or {},
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            duration_minutes=duration_minutes,
            execution_order_id=execution_order_id,
            signal_id=signal_id
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"Recorded live trade: {entry_id} P&L={position.realized_pnl:.2f}")

        return entry

    async def record_paper_trade(
        self,
        position: Position,
        strategy_config: Dict[str, Any],
        execution_order_id: int,
        signal_id: Optional[int] = None,
        market_context: Optional[Dict[str, Any]] = None,
        timeframe: str = "unknown"
    ) -> JournalEntry:
        """
        Record a paper trade to journal.

        Args:
            position: Closed position from paper trading
            strategy_config: Strategy configuration used
            execution_order_id: Execution order ID
            signal_id: Signal ID that generated trade
            market_context: Market conditions at trade time
            timeframe: Timeframe of the strategy

        Returns:
            Created journal entry
        """
        if position.exit_time is None or position.realized_pnl is None:
            raise ValueError("Cannot journal open position")

        duration_minutes = int((position.exit_time - position.entry_time).total_seconds() / 60)

        # Calculate metrics
        is_winner = position.realized_pnl > 0
        risk_amount = abs(position.entry_price - position.stop_loss) * position.position_size
        reward_amount = abs(position.take_profit - position.entry_price) * position.position_size
        rr_ratio = reward_amount / risk_amount if risk_amount > 0 else 0.0

        pnl_percent = (position.realized_pnl / (position.entry_price * position.position_size) * 100.0) if position.entry_price > 0 else 0.0

        # Determine exit reason
        exit_reason = "manual"
        if abs(position.exit_price - position.stop_loss) < 0.0001:
            exit_reason = "sl"
        elif abs(position.exit_price - position.take_profit) < 0.0001:
            exit_reason = "tp"

        entry_id = f"PAPER_{execution_order_id}_{uuid.uuid4().hex[:8]}"

        # Get side value - handle both string and enum
        side_value = position.side.value if hasattr(position.side, "value") else str(position.side).lower()

        entry = JournalEntry(
            entry_id=entry_id,
            source=TradeSource.PAPER,
            strategy_name=position.strategy_name,
            strategy_config=strategy_config,
            symbol=position.symbol,
            timeframe=timeframe,
            side=side_value,
            entry_price=position.entry_price,
            exit_price=position.exit_price,
            position_size=position.position_size,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            risk_percent=2.0,
            risk_reward_ratio=rr_ratio,
            pnl=position.realized_pnl,
            pnl_percent=pnl_percent,
            is_winner=is_winner,
            exit_reason=exit_reason,
            entry_slippage=0.0,
            exit_slippage=0.0,
            commission=position.commission_paid,
            market_context=market_context or {},
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            duration_minutes=duration_minutes,
            execution_order_id=execution_order_id,
            signal_id=signal_id
        )

        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)

        logger.info(f"Recorded paper trade: {entry_id} P&L={position.realized_pnl:.2f}")

        return entry
