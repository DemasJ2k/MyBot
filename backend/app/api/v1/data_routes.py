from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.user import User
from app.data import TwelveDataClient, DataService

router = APIRouter(prefix="/data", tags=["data"])


# === Schemas ===

class CandleSchema(BaseModel):
    symbol: str
    interval: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    class Config:
        from_attributes = True


class QuoteSchema(BaseModel):
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime


class SymbolSearchResult(BaseModel):
    symbol: str
    instrument_name: str
    exchange: str
    currency: str
    country: str
    type: str


class SyncResponse(BaseModel):
    symbol: str
    interval: str
    candles_inserted: int
    message: str


# === Endpoints ===

@router.get("/candles/{symbol}", response_model=List[CandleSchema])
async def get_candles(
    symbol: str,
    interval: str = Query(default="1day", pattern="^(1min|5min|15min|30min|1h|4h|1day|1week|1month)$"),
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get historical candles for a symbol from database."""
    if not start_date:
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
    if not end_date:
        end_date = datetime.now(timezone.utc)

    async with TwelveDataClient() as client:
        service = DataService(db, client)
        candles = await service.get_candles(
            symbol=symbol.upper(),
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )

    return candles


@router.get("/quote/{symbol}", response_model=QuoteSchema)
async def get_quote(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """Get real-time quote for a symbol."""
    async with TwelveDataClient() as client:
        try:
            quote = await client.get_quote(symbol.upper())
            return QuoteSchema(**quote)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch quote: {str(e)}")


@router.get("/search", response_model=List[SymbolSearchResult])
async def search_symbols(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user)
):
    """Search for symbols by name or ticker."""
    async with TwelveDataClient() as client:
        try:
            results = await client.search_symbol(query, limit=limit)
            return [SymbolSearchResult(**r) for r in results]
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Search failed: {str(e)}")


@router.post("/sync/{symbol}", response_model=SyncResponse)
async def sync_symbol_data(
    symbol: str,
    interval: str = Query(default="1day", pattern="^(1min|5min|15min|30min|1h|4h|1day|1week|1month)$"),
    outputsize: int = Query(default=5000, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Fetch and store candles from TwelveData into the database."""
    async with TwelveDataClient() as client:
        service = DataService(db, client)
        try:
            inserted = await service.fetch_and_store_candles(
                symbol=symbol.upper(),
                interval=interval,
                outputsize=outputsize
            )

            return SyncResponse(
                symbol=symbol.upper(),
                interval=interval,
                candles_inserted=inserted,
                message=f"Successfully synced {inserted} candles"
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Sync failed: {str(e)}")
