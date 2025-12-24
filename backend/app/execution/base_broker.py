"""
Abstract broker adapter interface.

All broker integrations (Signum, direct APIs) must implement this interface.
This ensures consistent behavior and auditability across all execution paths.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class BrokerOrderResult(BaseModel):
    """Result returned by broker after order submission."""
    success: bool
    broker_order_id: Optional[str] = None
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    commission: Optional[Decimal] = None
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None
    timestamp: datetime = datetime.utcnow()


class BrokerPositionInfo(BaseModel):
    """Current position information from broker."""
    symbol: str
    quantity: Decimal
    average_price: Decimal
    current_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    realized_pnl: Optional[Decimal] = None


class BrokerAccountInfo(BaseModel):
    """Account information from broker."""
    balance: Decimal
    equity: Decimal
    margin_used: Decimal
    margin_available: Decimal
    currency: str = "USD"


class OrderRequest(BaseModel):
    """Standard order request format for all brokers."""
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", "STOP", "STOP_LIMIT"
    quantity: Decimal
    limit_price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    time_in_force: str = "GTC"  # GTC, IOC, FOK, DAY
    client_order_id: Optional[str] = None


class BaseBrokerAdapter(ABC):
    """
    Abstract base class for all broker adapters.
    
    CRITICAL: This is the ONLY authorized path to execute trades.
    All implementations must:
    1. Log every action for auditability
    2. Validate orders before submission
    3. Handle errors gracefully
    4. Return standardized results
    """
    
    def __init__(self, broker_name: str, is_paper: bool = True):
        """
        Initialize broker adapter.
        
        Args:
            broker_name: Human-readable broker identifier
            is_paper: If True, this is a paper trading account
        """
        self.broker_name = broker_name
        self.is_paper = is_paper
        self._connected = False
    
    @property
    def is_connected(self) -> bool:
        """Check if broker connection is active."""
        return self._connected
    
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to broker.
        
        Returns:
            True if connection successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close broker connection gracefully."""
        pass
    
    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> BrokerOrderResult:
        """
        Submit an order to the broker.
        
        Args:
            order: Standardized order request
            
        Returns:
            BrokerOrderResult with success/failure details
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> BrokerOrderResult:
        """
        Cancel an existing order.
        
        Args:
            broker_order_id: The broker's order identifier
            
        Returns:
            BrokerOrderResult with cancellation status
        """
        pass
    
    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> Optional[dict]:
        """
        Get current status of an order.
        
        Args:
            broker_order_id: The broker's order identifier
            
        Returns:
            Order status dict or None if not found
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[BrokerPositionInfo]:
        """
        Get all open positions.
        
        Returns:
            List of current positions
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[BrokerPositionInfo]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Position info or None if no position
        """
        pass
    
    @abstractmethod
    async def get_account_info(self) -> BrokerAccountInfo:
        """
        Get current account information.
        
        Returns:
            Account balance, equity, margin info
        """
        pass
    
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Optional[Decimal]:
        """
        Get current market price for symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Current price or None if unavailable
        """
        pass
    
    def validate_order(self, order: OrderRequest) -> tuple[bool, Optional[str]]:
        """
        Basic order validation before submission.
        
        Args:
            order: Order to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not order.symbol:
            return False, "Symbol is required"
        
        if order.side not in ("BUY", "SELL"):
            return False, f"Invalid side: {order.side}"
        
        if order.order_type not in ("MARKET", "LIMIT", "STOP", "STOP_LIMIT"):
            return False, f"Invalid order type: {order.order_type}"
        
        if order.quantity <= 0:
            return False, "Quantity must be positive"
        
        if order.order_type in ("LIMIT", "STOP_LIMIT") and not order.limit_price:
            return False, f"{order.order_type} order requires limit_price"
        
        if order.order_type in ("STOP", "STOP_LIMIT") and not order.stop_price:
            return False, f"{order.order_type} order requires stop_price"
        
        return True, None
    
    async def health_check(self) -> bool:
        """
        Check if broker connection is healthy.
        
        Returns:
            True if connection is working
        """
        try:
            await self.get_account_info()
            return True
        except Exception:
            return False
