"""
Unit tests for Execution Engine (Prompt 10).

Tests cover:
- Paper broker functionality
- Execution engine mode enforcement
- Pre-validation pipeline
- GUIDE vs AUTONOMOUS mode behavior
- Order lifecycle management
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import (
    ExecutionOrder,
    ExecutionLog,
    BrokerConnection,
    BrokerType,
    OrderType,
    OrderSide,
    OrderStatus,
)
from app.models.signal import Signal, SignalType, SignalStatus
from app.execution.base_broker import (
    BaseBrokerAdapter,
    BrokerOrderResult,
    OrderRequest,
)
from app.execution.paper_broker import PaperBrokerAdapter
from app.execution.engine import ExecutionEngine, ExecutionMode


# ============================================================================
# Paper Broker Tests
# ============================================================================

class TestPaperBroker:
    """Test paper trading broker functionality."""
    
    @pytest.fixture
    def paper_broker(self) -> PaperBrokerAdapter:
        """Create paper broker with default settings."""
        return PaperBrokerAdapter(
            initial_balance=Decimal("100000"),
            slippage_bps=0,  # No slippage for predictable tests
            commission_per_trade=Decimal("0"),
        )
    
    @pytest.mark.asyncio
    async def test_paper_broker_connect(self, paper_broker: PaperBrokerAdapter):
        """Test paper broker connection."""
        assert not paper_broker.is_connected
        result = await paper_broker.connect()
        assert result is True
        assert paper_broker.is_connected
    
    @pytest.mark.asyncio
    async def test_paper_broker_account_info(self, paper_broker: PaperBrokerAdapter):
        """Test account info retrieval."""
        await paper_broker.connect()
        info = await paper_broker.get_account_info()
        
        assert info.balance == Decimal("100000")
        assert info.equity == Decimal("100000")
        assert info.currency == "USD"
    
    @pytest.mark.asyncio
    async def test_paper_broker_set_price(self, paper_broker: PaperBrokerAdapter):
        """Test setting simulated prices."""
        paper_broker.set_price("AAPL", Decimal("150.00"))
        price = await paper_broker.get_current_price("AAPL")
        assert price == Decimal("150.00")
    
    @pytest.mark.asyncio
    async def test_paper_broker_market_buy(self, paper_broker: PaperBrokerAdapter):
        """Test market buy order execution."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        
        result = await paper_broker.submit_order(order)
        
        assert result.success is True
        assert result.broker_order_id is not None
        assert result.filled_price == Decimal("150.00")
        assert result.filled_quantity == Decimal("10")
        
        # Check position created
        position = await paper_broker.get_position("AAPL")
        assert position is not None
        assert position.quantity == Decimal("10")
        assert position.average_price == Decimal("150.00")
        
        # Check balance decreased
        info = await paper_broker.get_account_info()
        assert info.balance == Decimal("98500")  # 100000 - (150 * 10)
    
    @pytest.mark.asyncio
    async def test_paper_broker_market_sell(self, paper_broker: PaperBrokerAdapter):
        """Test market sell order execution."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        # First buy
        buy_order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        await paper_broker.submit_order(buy_order)
        
        # Then sell at higher price
        paper_broker.set_price("AAPL", Decimal("160.00"))
        sell_order = OrderRequest(
            symbol="AAPL",
            side="SELL",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        result = await paper_broker.submit_order(sell_order)
        
        assert result.success is True
        assert result.filled_price == Decimal("160.00")
        
        # Position should be closed
        position = await paper_broker.get_position("AAPL")
        assert position is None
        
        # Balance should reflect profit
        info = await paper_broker.get_account_info()
        assert info.balance == Decimal("100100")  # 100000 - 1500 + 1600
    
    @pytest.mark.asyncio
    async def test_paper_broker_insufficient_balance(self, paper_broker: PaperBrokerAdapter):
        """Test order rejection for insufficient balance."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("1000"),  # 150,000 > 100,000
        )
        
        result = await paper_broker.submit_order(order)
        
        assert result.success is False
        assert "Insufficient balance" in result.error_message
    
    @pytest.mark.asyncio
    async def test_paper_broker_insufficient_position(self, paper_broker: PaperBrokerAdapter):
        """Test sell rejection for insufficient position."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        order = OrderRequest(
            symbol="AAPL",
            side="SELL",
            order_type="MARKET",
            quantity=Decimal("10"),  # No position
        )
        
        result = await paper_broker.submit_order(order)
        
        assert result.success is False
        assert "Insufficient position" in result.error_message
    
    @pytest.mark.asyncio
    async def test_paper_broker_limit_order_not_triggered(self, paper_broker: PaperBrokerAdapter):
        """Test limit order that doesn't trigger."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("10"),
            limit_price=Decimal("145.00"),  # Below current price
        )
        
        result = await paper_broker.submit_order(order)
        
        assert result.success is True
        assert result.filled_price is None  # Not filled
        assert "pending" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_paper_broker_cancel_order(self, paper_broker: PaperBrokerAdapter):
        """Test cancelling pending order."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        # Create pending limit order
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("10"),
            limit_price=Decimal("145.00"),
        )
        
        result = await paper_broker.submit_order(order)
        assert result.success is True
        
        # Cancel it
        cancel_result = await paper_broker.cancel_order(result.broker_order_id)
        assert cancel_result.success is True
    
    @pytest.mark.asyncio
    async def test_paper_broker_reset(self, paper_broker: PaperBrokerAdapter):
        """Test resetting paper broker state."""
        await paper_broker.connect()
        paper_broker.set_price("AAPL", Decimal("150.00"))
        
        # Make a trade
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        await paper_broker.submit_order(order)
        
        # Reset
        paper_broker.reset()
        
        # Verify reset
        info = await paper_broker.get_account_info()
        assert info.balance == Decimal("100000")
        
        positions = await paper_broker.get_positions()
        assert len(positions) == 0


# ============================================================================
# Order Validation Tests
# ============================================================================

class TestOrderValidation:
    """Test order validation logic."""
    
    def test_validate_empty_symbol(self):
        """Test validation rejects empty symbol."""
        broker = PaperBrokerAdapter()
        order = OrderRequest(
            symbol="",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        is_valid, error = broker.validate_order(order)
        assert is_valid is False
        assert "Symbol" in error
    
    def test_validate_invalid_side(self):
        """Test validation rejects invalid side."""
        broker = PaperBrokerAdapter()
        order = OrderRequest(
            symbol="AAPL",
            side="INVALID",
            order_type="MARKET",
            quantity=Decimal("10"),
        )
        is_valid, error = broker.validate_order(order)
        assert is_valid is False
        assert "Invalid side" in error
    
    def test_validate_invalid_order_type(self):
        """Test validation rejects invalid order type."""
        broker = PaperBrokerAdapter()
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="INVALID",
            quantity=Decimal("10"),
        )
        is_valid, error = broker.validate_order(order)
        assert is_valid is False
        assert "Invalid order type" in error
    
    def test_validate_zero_quantity(self):
        """Test validation rejects zero quantity."""
        broker = PaperBrokerAdapter()
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            quantity=Decimal("0"),
        )
        is_valid, error = broker.validate_order(order)
        assert is_valid is False
        assert "positive" in error.lower()
    
    def test_validate_limit_without_price(self):
        """Test validation rejects limit order without price."""
        broker = PaperBrokerAdapter()
        order = OrderRequest(
            symbol="AAPL",
            side="BUY",
            order_type="LIMIT",
            quantity=Decimal("10"),
        )
        is_valid, error = broker.validate_order(order)
        assert is_valid is False
        assert "limit_price" in error.lower()


# ============================================================================
# Execution Engine Tests
# ============================================================================

class TestExecutionEngine:
    """Test execution engine functionality."""
    
    @pytest.fixture
    async def test_signal(self, test_db: AsyncSession) -> Signal:
        """Create test signal."""
        signal = Signal(
            strategy_name="test_strategy",
            symbol="AAPL",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00,
            risk_percent=1.0,
            position_size=10.0,
            timeframe="H1",
            confidence=85.0,
            signal_time=datetime.utcnow(),
        )
        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)
        return signal
    
    @pytest.mark.asyncio
    async def test_execution_engine_default_mode(self, test_db: AsyncSession):
        """Test default execution mode is GUIDE."""
        engine = ExecutionEngine(test_db)
        assert engine.mode == ExecutionMode.GUIDE
    
    @pytest.mark.asyncio
    async def test_execution_engine_set_mode(self, test_db: AsyncSession):
        """Test setting execution mode."""
        engine = ExecutionEngine(test_db)
        
        engine.set_mode(ExecutionMode.AUTONOMOUS)
        assert engine.mode == ExecutionMode.AUTONOMOUS
        
        engine.set_mode(ExecutionMode.GUIDE)
        assert engine.mode == ExecutionMode.GUIDE
    
    @pytest.mark.asyncio
    async def test_execution_guide_mode_blocks_execution(
        self,
        test_db: AsyncSession,
        test_user,
    ):
        """Test GUIDE mode blocks actual execution."""
        # Create test signal inline
        signal = Signal(
            user_id=test_user.id,
            strategy_name="test_strategy",
            symbol="AAPL",
            signal_type=SignalType.LONG,
            status=SignalStatus.PENDING,
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00,
            risk_percent=1.0,
            position_size=10.0,
            timeframe="H1",
            confidence=85.0,
            signal_time=datetime.utcnow(),
        )
        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)
        
        engine = ExecutionEngine(test_db)
        engine.set_mode(ExecutionMode.GUIDE)
        
        # Set up paper broker with price
        paper_broker = engine.get_broker(BrokerType.PAPER)
        paper_broker.set_price("AAPL", Decimal("150.00"))
        await paper_broker.connect()
        
        result = await engine.execute_signal(signal.id)
        
        assert result.success is True
        assert result.mode == ExecutionMode.GUIDE
        assert "GUIDE mode" in result.blocked_reason
        assert result.execution_order_id is not None
        
        # Verify order was created but not filled
        order = await engine.get_order_status(result.execution_order_id)
        assert order.status == OrderStatus.REJECTED
        assert "GUIDE" in order.error_message
    
    @pytest.mark.asyncio
    async def test_execution_signal_not_found(self, test_db: AsyncSession):
        """Test execution with invalid signal ID."""
        engine = ExecutionEngine(test_db)
        
        result = await engine.execute_signal(99999)
        
        assert result.success is False
        assert "not found" in result.blocked_reason.lower()
    
    @pytest.mark.asyncio
    async def test_execution_cancelled_signal_rejected(
        self,
        test_db: AsyncSession,
        test_user,
    ):
        """Test execution rejects cancelled signal."""
        # Create cancelled signal
        signal = Signal(
            user_id=test_user.id,
            strategy_name="test_strategy",
            symbol="AAPL",
            signal_type=SignalType.LONG,
            status=SignalStatus.CANCELLED,
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00,
            risk_percent=1.0,
            timeframe="H1",
            confidence=85.0,
            signal_time=datetime.utcnow(),
        )
        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)
        
        engine = ExecutionEngine(test_db)
        result = await engine.execute_signal(signal.id)
        
        assert result.success is False
        assert "cancelled" in result.blocked_reason.lower()
    
    @pytest.mark.asyncio
    async def test_execution_expired_signal_rejected(
        self,
        test_db: AsyncSession,
        test_user,
    ):
        """Test execution rejects expired signal."""
        signal = Signal(
            user_id=test_user.id,
            strategy_name="test_strategy",
            symbol="AAPL",
            signal_type=SignalType.LONG,
            status=SignalStatus.EXPIRED,
            entry_price=150.00,
            stop_loss=145.00,
            take_profit=160.00,
            risk_percent=1.0,
            timeframe="H1",
            confidence=85.0,
            signal_time=datetime.utcnow(),
        )
        test_db.add(signal)
        await test_db.commit()
        await test_db.refresh(signal)
        
        engine = ExecutionEngine(test_db)
        result = await engine.execute_signal(signal.id)
        
        assert result.success is False
        assert "expired" in result.blocked_reason.lower()
    
    @pytest.mark.asyncio
    async def test_execution_paper_broker_registered_by_default(
        self,
        test_db: AsyncSession,
    ):
        """Test paper broker is registered by default."""
        engine = ExecutionEngine(test_db)
        
        broker = engine.get_broker(BrokerType.PAPER)
        
        assert broker is not None
        assert isinstance(broker, PaperBrokerAdapter)


# ============================================================================
# Order Lifecycle Tests
# ============================================================================

class TestOrderLifecycle:
    """Test order state management."""
    
    @pytest.mark.asyncio
    async def test_cancel_pending_order(self, test_db: AsyncSession, test_user):
        """Test cancelling a pending order."""
        # Create a pending order
        order = ExecutionOrder(
            user_id=test_user.id,
            client_order_id="TEST-001",
            broker_type=BrokerType.PAPER,
            symbol="AAPL",
            order_type=OrderType.LIMIT,
            side=OrderSide.BUY,
            quantity=10.0,
            price=150.00,
            status=OrderStatus.PENDING,
            strategy_name="test_strategy",
        )
        test_db.add(order)
        await test_db.commit()
        await test_db.refresh(order)
        
        engine = ExecutionEngine(test_db)
        result = await engine.cancel_order(order.id)
        
        assert result.success is True
        
        # Verify order is cancelled
        updated_order = await engine.get_order_status(order.id)
        assert updated_order.status == OrderStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_cannot_cancel_filled_order(self, test_db: AsyncSession, test_user):
        """Test cannot cancel an already filled order."""
        order = ExecutionOrder(
            user_id=test_user.id,
            client_order_id="TEST-002",
            broker_type=BrokerType.PAPER,
            symbol="AAPL",
            order_type=OrderType.MARKET,
            side=OrderSide.BUY,
            quantity=10.0,
            status=OrderStatus.FILLED,
            filled_quantity=10.0,
            average_fill_price=150.00,
            strategy_name="test_strategy",
        )
        test_db.add(order)
        await test_db.commit()
        await test_db.refresh(order)
        
        engine = ExecutionEngine(test_db)
        result = await engine.cancel_order(order.id)
        
        assert result.success is False
        assert "Cannot cancel" in result.blocked_reason
    
    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, test_db: AsyncSession):
        """Test cancelling non-existent order."""
        engine = ExecutionEngine(test_db)
        result = await engine.cancel_order(99999)
        
        assert result.success is False
        assert "not found" in result.blocked_reason.lower()


# ============================================================================
# Execution Result Tests
# ============================================================================

class TestExecutionResult:
    """Test execution result serialization."""
    
    def test_to_dict_basic(self):
        """Test basic result serialization."""
        from app.execution.engine import ExecutionResult
        
        result = ExecutionResult(
            success=True,
            mode=ExecutionMode.GUIDE,
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert d["mode"] == "GUIDE"
    
    def test_to_dict_with_blocked_reason(self):
        """Test result with blocked reason."""
        from app.execution.engine import ExecutionResult
        
        result = ExecutionResult(
            success=False,
            blocked_reason="Risk check failed",
            mode=ExecutionMode.GUIDE,
        )
        
        d = result.to_dict()
        
        assert d["success"] is False
        assert d["blocked_reason"] == "Risk check failed"
    
    def test_to_dict_with_broker_result(self):
        """Test result with broker result."""
        from app.execution.engine import ExecutionResult
        
        broker_result = BrokerOrderResult(
            success=True,
            broker_order_id="BR-123",
            filled_price=Decimal("150.00"),
            filled_quantity=Decimal("10"),
        )
        
        result = ExecutionResult(
            success=True,
            execution_order_id=1,
            mode=ExecutionMode.AUTONOMOUS,
            broker_result=broker_result,
        )
        
        d = result.to_dict()
        
        assert d["broker_result"]["success"] is True
        assert d["broker_result"]["broker_order_id"] == "BR-123"
