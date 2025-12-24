"""
Paper trading broker adapter for simulation.

This adapter simulates order execution without real money,
perfect for testing strategies and during GUIDE mode operations.
"""

import uuid
from decimal import Decimal
from typing import Optional
from datetime import datetime
import random

from .base_broker import (
    BaseBrokerAdapter,
    BrokerOrderResult,
    BrokerPositionInfo,
    BrokerAccountInfo,
    OrderRequest,
)


class PaperBrokerAdapter(BaseBrokerAdapter):
    """
    Paper trading adapter for simulated execution.
    
    Features:
    - Simulated order fills with realistic slippage
    - Virtual account balance tracking
    - Position management
    - Order history
    
    Use this for:
    - Strategy testing
    - GUIDE mode signal validation
    - Development and debugging
    """
    
    def __init__(
        self,
        initial_balance: Decimal = Decimal("100000"),
        slippage_bps: int = 5,  # 5 basis points default slippage
        commission_per_trade: Decimal = Decimal("0"),
    ):
        """
        Initialize paper broker.
        
        Args:
            initial_balance: Starting account balance
            slippage_bps: Simulated slippage in basis points
            commission_per_trade: Fixed commission per trade
        """
        super().__init__(broker_name="PaperTrading", is_paper=True)
        
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.slippage_bps = slippage_bps
        self.commission = commission_per_trade
        
        # Track positions: symbol -> BrokerPositionInfo
        self._positions: dict[str, BrokerPositionInfo] = {}
        
        # Track orders: order_id -> order_details
        self._orders: dict[str, dict] = {}
        
        # Simulated prices: symbol -> price
        self._prices: dict[str, Decimal] = {}
    
    async def connect(self) -> bool:
        """Paper broker is always connected."""
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        """Paper broker disconnect is a no-op."""
        self._connected = False
    
    def set_price(self, symbol: str, price: Decimal) -> None:
        """
        Set simulated price for a symbol.
        
        Args:
            symbol: Trading symbol
            price: Current price to simulate
        """
        self._prices[symbol] = price
    
    def _apply_slippage(self, price: Decimal, side: str) -> Decimal:
        """
        Apply realistic slippage to fill price.
        
        Args:
            price: Base price
            side: BUY or SELL
            
        Returns:
            Price with slippage applied
        """
        slippage_factor = Decimal(str(self.slippage_bps)) / Decimal("10000")
        
        # Random slippage between 0 and max
        actual_slippage = slippage_factor * Decimal(str(random.uniform(0, 1)))
        
        if side == "BUY":
            # Buyers pay slightly more
            return price * (1 + actual_slippage)
        else:
            # Sellers receive slightly less
            return price * (1 - actual_slippage)
    
    async def submit_order(self, order: OrderRequest) -> BrokerOrderResult:
        """
        Simulate order execution.
        
        For paper trading:
        - MARKET orders fill immediately at current price ± slippage
        - LIMIT orders check if price is favorable
        - STOP orders trigger at stop price
        """
        # Validate order first
        is_valid, error = self.validate_order(order)
        if not is_valid:
            return BrokerOrderResult(
                success=False,
                error_message=error,
            )
        
        # Get current price
        current_price = self._prices.get(order.symbol)
        if current_price is None:
            return BrokerOrderResult(
                success=False,
                error_message=f"No price available for {order.symbol}. Set price first.",
            )
        
        # Determine fill price based on order type
        fill_price: Optional[Decimal] = None
        
        if order.order_type == "MARKET":
            fill_price = self._apply_slippage(current_price, order.side)
        
        elif order.order_type == "LIMIT":
            if order.side == "BUY" and current_price <= order.limit_price:
                fill_price = self._apply_slippage(current_price, order.side)
            elif order.side == "SELL" and current_price >= order.limit_price:
                fill_price = self._apply_slippage(current_price, order.side)
        
        elif order.order_type == "STOP":
            if order.side == "BUY" and current_price >= order.stop_price:
                fill_price = self._apply_slippage(current_price, order.side)
            elif order.side == "SELL" and current_price <= order.stop_price:
                fill_price = self._apply_slippage(current_price, order.side)
        
        elif order.order_type == "STOP_LIMIT":
            # Stop must trigger first
            stop_triggered = False
            if order.side == "BUY" and current_price >= order.stop_price:
                stop_triggered = True
            elif order.side == "SELL" and current_price <= order.stop_price:
                stop_triggered = True
            
            if stop_triggered:
                # Then check limit
                if order.side == "BUY" and current_price <= order.limit_price:
                    fill_price = self._apply_slippage(current_price, order.side)
                elif order.side == "SELL" and current_price >= order.limit_price:
                    fill_price = self._apply_slippage(current_price, order.side)
        
        # Generate order ID
        broker_order_id = str(uuid.uuid4())[:8].upper()
        
        if fill_price is None:
            # Order pending (limit/stop not triggered)
            self._orders[broker_order_id] = {
                "order": order,
                "status": "PENDING",
                "created_at": datetime.utcnow(),
            }
            return BrokerOrderResult(
                success=True,
                broker_order_id=broker_order_id,
                error_message="Order pending - limit/stop not triggered",
            )
        
        # Calculate total cost
        total_cost = fill_price * order.quantity
        commission_paid = self.commission
        
        # Check sufficient balance for buys
        if order.side == "BUY":
            required = total_cost + commission_paid
            if required > self.balance:
                return BrokerOrderResult(
                    success=False,
                    error_message=f"Insufficient balance. Required: {required}, Available: {self.balance}",
                )
        
        # Execute the fill
        if order.side == "BUY":
            self.balance -= (total_cost + commission_paid)
            self._update_position(order.symbol, order.quantity, fill_price, "BUY")
        else:
            # For sells, check we have the position
            position = self._positions.get(order.symbol)
            if not position or position.quantity < order.quantity:
                return BrokerOrderResult(
                    success=False,
                    error_message=f"Insufficient position to sell {order.quantity} {order.symbol}",
                )
            self.balance += (total_cost - commission_paid)
            self._update_position(order.symbol, order.quantity, fill_price, "SELL")
        
        # Record the filled order
        self._orders[broker_order_id] = {
            "order": order,
            "status": "FILLED",
            "fill_price": fill_price,
            "fill_quantity": order.quantity,
            "commission": commission_paid,
            "filled_at": datetime.utcnow(),
        }
        
        return BrokerOrderResult(
            success=True,
            broker_order_id=broker_order_id,
            filled_price=fill_price,
            filled_quantity=order.quantity,
            commission=commission_paid,
        )
    
    def _update_position(
        self,
        symbol: str,
        quantity: Decimal,
        price: Decimal,
        side: str,
    ) -> None:
        """Update position after a fill."""
        existing = self._positions.get(symbol)
        
        if side == "BUY":
            if existing:
                # Average in
                total_qty = existing.quantity + quantity
                avg_price = (
                    (existing.average_price * existing.quantity) + (price * quantity)
                ) / total_qty
                self._positions[symbol] = BrokerPositionInfo(
                    symbol=symbol,
                    quantity=total_qty,
                    average_price=avg_price,
                    current_price=price,
                )
            else:
                self._positions[symbol] = BrokerPositionInfo(
                    symbol=symbol,
                    quantity=quantity,
                    average_price=price,
                    current_price=price,
                )
        else:  # SELL
            if existing:
                new_qty = existing.quantity - quantity
                if new_qty <= 0:
                    # Position closed
                    del self._positions[symbol]
                else:
                    self._positions[symbol] = BrokerPositionInfo(
                        symbol=symbol,
                        quantity=new_qty,
                        average_price=existing.average_price,
                        current_price=price,
                    )
    
    async def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        """Cancel a pending order."""
        order_data = self._orders.get(broker_order_id)
        
        if not order_data:
            return BrokerOrderResult(
                success=False,
                error_message=f"Order {broker_order_id} not found",
            )
        
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
        return self._orders.get(broker_order_id)
    
    async def get_positions(self) -> list[BrokerPositionInfo]:
        """Get all positions."""
        return list(self._positions.values())
    
    async def get_position(self, symbol: str) -> Optional[BrokerPositionInfo]:
        """Get position for symbol."""
        return self._positions.get(symbol)
    
    async def get_account_info(self) -> BrokerAccountInfo:
        """Get account information."""
        # Calculate equity = balance + positions value
        positions_value = Decimal("0")
        for pos in self._positions.values():
            price = self._prices.get(pos.symbol, pos.average_price)
            positions_value += pos.quantity * price
        
        equity = self.balance + positions_value
        
        return BrokerAccountInfo(
            balance=self.balance,
            equity=equity,
            margin_used=Decimal("0"),  # Paper trading has no margin
            margin_available=equity,
            currency="USD",
        )
    
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """Get current price for symbol."""
        return self._prices.get(symbol)
    
    def reset(self) -> None:
        """Reset paper broker to initial state."""
        self.balance = self.initial_balance
        self._positions.clear()
        self._orders.clear()
        self._prices.clear()
