"""
Simulated Broker Adapter.

This adapter provides realistic trade simulation using database-backed 
SimulationAccount for persistent state. Unlike PaperBrokerAdapter which
is in-memory only, this adapter:

1. Persists state to database (SimulationAccount, SimulationPosition)
2. Simulates realistic market conditions (slippage, latency, partial fills)
3. Provides complete audit trail
4. Is the DEFAULT execution mode for safety

Safety First: This is the default mode. Live trading requires explicit opt-in.
"""

import uuid
import asyncio
import random
from decimal import Decimal
from typing import Optional
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .base_broker import (
    BaseBrokerAdapter,
    BrokerOrderResult,
    BrokerPositionInfo,
    BrokerAccountInfo,
    OrderRequest,
)
from app.models.execution_mode import (
    ExecutionMode,
    SimulationAccount,
    SimulationPosition,
)


class SimulatedBrokerAdapter(BaseBrokerAdapter):
    """
    Database-backed simulated broker for SIMULATION mode.
    
    Features:
    - Persistent state via SimulationAccount model
    - Configurable slippage, latency, and fill probability
    - Realistic order execution simulation
    - Complete position tracking with SL/TP
    - Full audit trail for compliance
    
    This is the DEFAULT and SAFEST mode for strategy testing.
    No real money is ever at risk.
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        user_id: int,
        simulation_account: Optional[SimulationAccount] = None,
    ):
        """
        Initialize simulated broker.
        
        Args:
            db_session: Async database session for persistence
            user_id: User ID for account lookup/creation
            simulation_account: Pre-loaded SimulationAccount (optional)
        """
        super().__init__(broker_name="Simulation", is_paper=True)
        
        self.db = db_session
        self.user_id = user_id
        self._account = simulation_account
        
        # Simulated prices: symbol -> (bid, ask)
        self._prices: dict[str, tuple[Decimal, Decimal]] = {}
        
        # Pending orders for limit/stop orders
        self._pending_orders: dict[str, dict] = {}
    
    async def _ensure_account(self) -> SimulationAccount:
        """Get or create simulation account for user."""
        if self._account:
            return self._account
        
        # Try to find existing account
        result = await self.db.execute(
            select(SimulationAccount).where(SimulationAccount.user_id == self.user_id)
        )
        account = result.scalar_one_or_none()
        
        if not account:
            # Create new account with defaults
            account = SimulationAccount(user_id=self.user_id)
            self.db.add(account)
            await self.db.flush()
        
        self._account = account
        return account
    
    async def connect(self) -> bool:
        """
        Connect to simulation broker.
        
        Ensures SimulationAccount exists for the user.
        Always succeeds since this is simulated.
        """
        try:
            await self._ensure_account()
            self._connected = True
            return True
        except Exception as e:
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from simulation broker."""
        self._connected = False
    
    def set_price(self, symbol: str, bid: Decimal, ask: Decimal) -> None:
        """
        Set simulated bid/ask prices for a symbol.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            bid: Bid price (sell price)
            ask: Ask price (buy price)
        """
        self._prices[symbol] = (bid, ask)
    
    def set_mid_price(self, symbol: str, price: Decimal, spread_pips: Decimal = Decimal("1")) -> None:
        """
        Set price using mid price and spread.
        
        Args:
            symbol: Trading symbol
            price: Mid price
            spread_pips: Spread in pips (default 1 pip)
        """
        half_spread = spread_pips * Decimal("0.00005")  # Convert pips to price
        self._prices[symbol] = (price - half_spread, price + half_spread)
    
    def _get_fill_price(self, symbol: str, side: str) -> Optional[Decimal]:
        """
        Get fill price with slippage simulation.
        
        Args:
            symbol: Trading symbol
            side: "BUY" or "SELL"
            
        Returns:
            Fill price with slippage, or None if no price
        """
        prices = self._prices.get(symbol)
        if not prices:
            return None
        
        bid, ask = prices
        base_price = ask if side == "BUY" else bid
        
        # Apply slippage from account settings
        if self._account:
            slippage_pips = Decimal(str(self._account.slippage_pips))
            # Random slippage between 0 and configured max
            actual_slippage = slippage_pips * Decimal(str(random.uniform(0, 1)))
            slippage_amount = actual_slippage * Decimal("0.0001")
            
            # Slippage is always unfavorable
            if side == "BUY":
                base_price += slippage_amount
            else:
                base_price -= slippage_amount
        
        return base_price
    
    async def _simulate_latency(self) -> None:
        """Simulate network/execution latency."""
        if self._account and self._account.latency_ms > 0:
            # Add some randomness (±20%)
            latency = self._account.latency_ms * random.uniform(0.8, 1.2)
            await asyncio.sleep(latency / 1000)
    
    def _check_fill_probability(self) -> bool:
        """Check if order should fill based on fill probability."""
        if self._account:
            return random.random() < self._account.fill_probability
        return True  # Default: always fill
    
    async def submit_order(self, order: OrderRequest) -> BrokerOrderResult:
        """
        Submit order to simulation.
        
        Simulates realistic execution with:
        - Configurable latency
        - Slippage simulation
        - Fill probability (partial fills possible)
        - Proper position and margin tracking
        """
        # Ensure we have an account
        account = await self._ensure_account()
        
        # Validate order
        is_valid, error = self.validate_order(order)
        if not is_valid:
            return BrokerOrderResult(
                success=False,
                error_message=error,
            )
        
        # Simulate latency
        await self._simulate_latency()
        
        # Check fill probability (simulate market conditions)
        if not self._check_fill_probability():
            # Order rejected due to market conditions
            return BrokerOrderResult(
                success=False,
                error_message="Order rejected - simulated market conditions unfavorable",
            )
        
        # Get fill price
        fill_price = self._get_fill_price(order.symbol, order.side)
        if fill_price is None:
            return BrokerOrderResult(
                success=False,
                error_message=f"No price available for {order.symbol}. Use set_price() first.",
            )
        
        # Handle different order types
        should_fill = False
        
        if order.order_type == "MARKET":
            should_fill = True
            
        elif order.order_type == "LIMIT":
            if order.side == "BUY" and fill_price <= order.limit_price:
                should_fill = True
            elif order.side == "SELL" and fill_price >= order.limit_price:
                should_fill = True
                
        elif order.order_type == "STOP":
            if order.side == "BUY" and fill_price >= order.stop_price:
                should_fill = True
            elif order.side == "SELL" and fill_price <= order.stop_price:
                should_fill = True
                
        elif order.order_type == "STOP_LIMIT":
            stop_triggered = False
            if order.side == "BUY" and fill_price >= order.stop_price:
                stop_triggered = True
            elif order.side == "SELL" and fill_price <= order.stop_price:
                stop_triggered = True
            
            if stop_triggered:
                if order.side == "BUY" and fill_price <= order.limit_price:
                    should_fill = True
                elif order.side == "SELL" and fill_price >= order.limit_price:
                    should_fill = True
        
        # Generate order ID
        broker_order_id = f"SIM-{uuid.uuid4().hex[:8].upper()}"
        
        if not should_fill:
            # Store as pending order
            self._pending_orders[broker_order_id] = {
                "order": order,
                "status": "PENDING",
                "created_at": datetime.utcnow(),
            }
            return BrokerOrderResult(
                success=True,
                broker_order_id=broker_order_id,
                error_message="Order pending - limit/stop not triggered",
            )
        
        # Calculate trade value and commission
        trade_value = float(fill_price) * float(order.quantity) * 100000  # Standard lot
        commission = account.commission_per_lot * float(order.quantity)
        
        # Check margin/balance for buys
        if order.side == "BUY":
            required_margin = trade_value * 0.01  # 1% margin requirement (100:1 leverage)
            if required_margin + commission > account.margin_available:
                return BrokerOrderResult(
                    success=False,
                    error_message=f"Insufficient margin. Required: {required_margin:.2f}, Available: {account.margin_available:.2f}",
                )
        
        # Execute the trade - create/update position
        await self._execute_fill(
            account=account,
            order=order,
            fill_price=fill_price,
            commission=commission,
            broker_order_id=broker_order_id,
        )
        
        return BrokerOrderResult(
            success=True,
            broker_order_id=broker_order_id,
            filled_price=fill_price,
            filled_quantity=order.quantity,
            commission=Decimal(str(commission)),
            timestamp=datetime.utcnow(),
        )
    
    async def _execute_fill(
        self,
        account: SimulationAccount,
        order: OrderRequest,
        fill_price: Decimal,
        commission: float,
        broker_order_id: str,
    ) -> None:
        """Execute fill and update position/account state."""
        # Check for existing position
        result = await self.db.execute(
            select(SimulationPosition).where(
                SimulationPosition.simulation_account_id == account.id,
                SimulationPosition.symbol == order.symbol,
            )
        )
        existing_position = result.scalar_one_or_none()
        
        side = "long" if order.side == "BUY" else "short"
        
        if existing_position:
            if existing_position.side == side:
                # Adding to position - average in
                total_qty = existing_position.quantity + float(order.quantity)
                avg_price = (
                    (existing_position.entry_price * existing_position.quantity) +
                    (float(fill_price) * float(order.quantity))
                ) / total_qty
                
                existing_position.quantity = total_qty
                existing_position.entry_price = avg_price
                existing_position.current_price = float(fill_price)
                existing_position.update_price(float(fill_price))
            else:
                # Reducing/closing position
                remaining = existing_position.quantity - float(order.quantity)
                
                if remaining <= 0:
                    # Position closed - calculate P&L
                    pnl = existing_position.unrealized_pnl - commission
                    is_winner = pnl > 0
                    account.record_trade(pnl, is_winner)
                    await self.db.delete(existing_position)
                else:
                    # Partial close
                    closed_qty = float(order.quantity)
                    partial_pnl = (existing_position.unrealized_pnl / existing_position.quantity) * closed_qty
                    pnl = partial_pnl - commission
                    is_winner = pnl > 0
                    account.record_trade(pnl, is_winner)
                    
                    existing_position.quantity = remaining
                    existing_position.update_price(float(fill_price))
        else:
            # New position
            margin_required = float(fill_price) * float(order.quantity) * 100000 * 0.01
            
            position = SimulationPosition(
                user_id=self.user_id,
                simulation_account_id=account.id,
                symbol=order.symbol,
                side=side,
                quantity=float(order.quantity),
                entry_price=float(fill_price),
                current_price=float(fill_price),
                stop_loss=float(order.stop_loss) if order.stop_loss else None,
                take_profit=float(order.take_profit) if order.take_profit else None,
                margin_required=margin_required,
                order_id=broker_order_id,
            )
            self.db.add(position)
            
            # Update margin
            account.margin_used += margin_required
            account.margin_available = account.equity - account.margin_used
        
        # Deduct commission from balance
        account.balance -= commission
        account.equity = account.balance + sum(
            p.unrealized_pnl for p in await self._get_all_positions()
        )
        
        await self.db.flush()
    
    async def _get_all_positions(self) -> list[SimulationPosition]:
        """Get all positions for this account."""
        account = await self._ensure_account()
        result = await self.db.execute(
            select(SimulationPosition).where(
                SimulationPosition.simulation_account_id == account.id
            )
        )
        return list(result.scalars().all())
    
    async def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        """Cancel a pending order."""
        if broker_order_id not in self._pending_orders:
            return BrokerOrderResult(
                success=False,
                error_message=f"Order {broker_order_id} not found",
            )
        
        order_data = self._pending_orders[broker_order_id]
        if order_data["status"] != "PENDING":
            return BrokerOrderResult(
                success=False,
                error_message=f"Order {broker_order_id} cannot be cancelled - status: {order_data['status']}",
            )
        
        order_data["status"] = "CANCELLED"
        order_data["cancelled_at"] = datetime.utcnow()
        
        return BrokerOrderResult(
            success=True,
            broker_order_id=broker_order_id,
        )
    
    async def get_order_status(self, broker_order_id: str) -> Optional[dict]:
        """Get order status."""
        return self._pending_orders.get(broker_order_id)
    
    async def get_positions(self) -> list[BrokerPositionInfo]:
        """Get all open positions."""
        positions = await self._get_all_positions()
        return [
            BrokerPositionInfo(
                symbol=p.symbol,
                quantity=Decimal(str(p.quantity)),
                average_price=Decimal(str(p.entry_price)),
                current_price=Decimal(str(p.current_price)),
                unrealized_pnl=Decimal(str(p.unrealized_pnl)),
            )
            for p in positions
        ]
    
    async def get_position(self, symbol: str) -> Optional[BrokerPositionInfo]:
        """Get position for symbol."""
        account = await self._ensure_account()
        result = await self.db.execute(
            select(SimulationPosition).where(
                SimulationPosition.simulation_account_id == account.id,
                SimulationPosition.symbol == symbol,
            )
        )
        position = result.scalar_one_or_none()
        
        if not position:
            return None
        
        return BrokerPositionInfo(
            symbol=position.symbol,
            quantity=Decimal(str(position.quantity)),
            average_price=Decimal(str(position.entry_price)),
            current_price=Decimal(str(position.current_price)),
            unrealized_pnl=Decimal(str(position.unrealized_pnl)),
        )
    
    async def get_account_info(self) -> BrokerAccountInfo:
        """Get account information."""
        account = await self._ensure_account()
        
        return BrokerAccountInfo(
            balance=Decimal(str(account.balance)),
            equity=Decimal(str(account.equity)),
            margin_used=Decimal(str(account.margin_used)),
            margin_available=Decimal(str(account.margin_available)),
            currency=account.currency,
        )
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current mid price for symbol."""
        prices = self._prices.get(symbol)
        if not prices:
            return None
        bid, ask = prices
        return (bid + ask) / 2
    
    async def reset_account(self) -> None:
        """Reset simulation account to initial state."""
        account = await self._ensure_account()
        
        # Close all positions
        positions = await self._get_all_positions()
        for position in positions:
            await self.db.delete(position)
        
        # Reset account
        account.reset()
        
        # Clear pending orders
        self._pending_orders.clear()
        
        await self.db.flush()
    
    async def update_prices(self, price_updates: dict[str, tuple[Decimal, Decimal]]) -> None:
        """
        Update multiple prices and check SL/TP triggers.
        
        Args:
            price_updates: Dict of symbol -> (bid, ask)
        """
        self._prices.update(price_updates)
        
        # Check SL/TP for all positions
        positions = await self._get_all_positions()
        account = await self._ensure_account()
        
        for position in positions:
            prices = self._prices.get(position.symbol)
            if not prices:
                continue
            
            bid, ask = prices
            current_price = float(bid) if position.side == "long" else float(ask)
            position.update_price(current_price)
            
            # Check stop loss
            if position.check_stop_loss():
                await self._close_position_at_market(position, account, "Stop Loss")
            
            # Check take profit
            elif position.check_take_profit():
                await self._close_position_at_market(position, account, "Take Profit")
        
        # Update account equity
        total_unrealized = sum(p.unrealized_pnl for p in await self._get_all_positions())
        account.update_equity(total_unrealized)
        
        await self.db.flush()
    
    async def _close_position_at_market(
        self,
        position: SimulationPosition,
        account: SimulationAccount,
        reason: str,
    ) -> None:
        """Close a position at market price."""
        pnl = position.unrealized_pnl
        commission = account.commission_per_lot * position.quantity
        net_pnl = pnl - commission
        is_winner = net_pnl > 0
        
        account.record_trade(net_pnl, is_winner)
        account.margin_used -= position.margin_required
        account.margin_available = account.equity - account.margin_used
        
        await self.db.delete(position)
