from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.data.data_service import DataService
from app.data.twelvedata_client import TwelveDataClient
from app.strategies.strategy_manager import StrategyManager
from app.models.signal import Signal, SignalStatus
from sqlalchemy import select, and_
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategies", tags=["strategies"])


# === Schemas ===

class SignalResponse(BaseModel):
    id: Optional[int] = None
    strategy_name: str
    symbol: str
    signal_type: str
    status: str
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_percent: float
    confidence: float
    reason: Optional[str]
    signal_time: datetime
    risk_reward_ratio: float

    class Config:
        from_attributes = True

    @classmethod
    def from_signal(cls, signal: Signal) -> "SignalResponse":
        return cls(
            id=signal.id,
            strategy_name=signal.strategy_name,
            symbol=signal.symbol,
            signal_type=signal.signal_type.value,
            status=signal.status.value,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            risk_percent=signal.risk_percent,
            confidence=signal.confidence,
            reason=signal.reason,
            signal_time=signal.signal_time,
            risk_reward_ratio=signal.risk_reward_ratio
        )


class StrategyListResponse(BaseModel):
    strategies: List[str]


# === Endpoints ===

@router.get("/", response_model=StrategyListResponse)
async def list_strategies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available strategies."""
    manager = StrategyManager(db=db)
    strategies = manager.list_strategies()
    return {"strategies": strategies}


@router.post("/analyze/{symbol}")
async def analyze_symbol(
    symbol: str,
    strategy_name: Optional[str] = None,
    interval: str = Query("1h"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Run strategy analysis on a symbol.

    If strategy_name is provided, runs only that strategy.
    Otherwise, runs all strategies.
    """
    async with TwelveDataClient() as client:
        data_service = DataService(db=db, client=client)

        # Get historical candles
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=90)

        candles = await data_service.get_candles(
            symbol=symbol,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )

        if not candles:
            # Fetch if missing
            await data_service.fetch_and_store_candles(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date
            )
            candles = await data_service.get_candles(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date
            )

        if not candles:
            raise HTTPException(status_code=404, detail=f"No data available for {symbol}")

        # Get current price
        quote = await client.get_quote(symbol)
        current_price = quote["price"]

        # Run strategies
        manager = StrategyManager(db=db)

        if strategy_name:
            try:
                signals = await manager.run_strategy(
                    strategy_name=strategy_name,
                    symbol=symbol,
                    candles=candles,
                    current_price=current_price
                )
                result = {strategy_name: [SignalResponse.from_signal(s) for s in signals]}
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
        else:
            all_signals = await manager.run_all_strategies(
                symbol=symbol,
                candles=candles,
                current_price=current_price
            )
            result = {
                name: [SignalResponse.from_signal(s) for s in sigs]
                for name, sigs in all_signals.items()
            }

        return result


@router.get("/signals", response_model=List[SignalResponse])
async def get_signals(
    strategy_name: Optional[str] = None,
    symbol: Optional[str] = None,
    status: Optional[SignalStatus] = None,
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get signals with optional filters."""
    stmt = select(Signal)

    filters = []
    if strategy_name:
        filters.append(Signal.strategy_name == strategy_name)
    if symbol:
        filters.append(Signal.symbol == symbol)
    if status:
        filters.append(Signal.status == status)

    if filters:
        stmt = stmt.where(and_(*filters))

    stmt = stmt.order_by(Signal.signal_time.desc()).limit(limit)

    result = await db.execute(stmt)
    signals = result.scalars().all()

    return [SignalResponse.from_signal(s) for s in signals]


@router.post("/signals/{signal_id}/cancel")
async def cancel_signal(
    signal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Cancel a pending signal."""
    stmt = select(Signal).where(Signal.id == signal_id)
    result = await db.execute(stmt)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if signal.status != SignalStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Cannot cancel signal with status {signal.status}")

    signal.status = SignalStatus.CANCELLED
    await db.commit()

    return {"message": f"Signal {signal_id} cancelled"}
