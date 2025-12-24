"""
Tests for Multi-Agent Coordination System (Prompt 08).

Tests:
- MessageBus: Message sending, receiving, priority ordering
- SharedStateManager: Cycle creation, phase transitions, access control
- HealthMonitor: Heartbeats, error tracking, health checks
- CoordinationPipeline: Full cycle execution
"""

import pytest
from datetime import datetime, timedelta
from app.coordination.message_bus import MessageBus
from app.coordination.shared_state import SharedStateManager
from app.coordination.health_monitor import HealthMonitor
from app.coordination.pipeline import CoordinationPipeline
from app.models.coordination import (
    MessageType,
    MessagePriority,
    CoordinationPhase,
    AgentMessage,
    CoordinationState,
    AgentHealth,
)
from app.models.ai_agent import SystemMode


@pytest.mark.asyncio
class TestMessageBus:
    """Tests for MessageBus class."""

    async def test_send_and_receive_message(self, test_db):
        """Test sending and receiving a message."""
        bus = MessageBus(db=test_db)

        # Send message
        message = await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Test command",
            payload={"test": "data"},
            priority=MessagePriority.NORMAL
        )

        assert message.id is not None
        assert message.processed is False
        assert message.from_agent == "supervisor"
        assert message.to_agent == "strategy"

        # Receive messages
        messages = await bus.receive_messages("strategy")
        assert len(messages) == 1
        assert messages[0].subject == "Test command"

    async def test_message_priority_ordering(self, test_db):
        """Test that messages are returned in priority order."""
        bus = MessageBus(db=test_db)

        # Send low priority message first
        await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Low priority",
            payload={},
            priority=MessagePriority.LOW
        )

        # Send high priority message second
        await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="High priority",
            payload={},
            priority=MessagePriority.HIGH
        )

        # Receive messages - should get high priority first
        messages = await bus.receive_messages("strategy", limit=10)
        assert len(messages) == 2
        assert messages[0].subject == "High priority"
        assert messages[1].subject == "Low priority"

    async def test_mark_message_processed(self, test_db):
        """Test marking a message as processed."""
        bus = MessageBus(db=test_db)

        message = await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Test",
            payload={},
        )

        assert message.processed is False

        await bus.mark_processed(message.id)

        # Refresh to get updated state
        updated = await bus.get_message_by_id(message.id)
        assert updated.processed is True
        assert updated.processed_at is not None

    async def test_send_response(self, test_db):
        """Test sending a response to a message."""
        bus = MessageBus(db=test_db)

        original = await bus.send_message(
            from_agent="supervisor",
            to_agent="strategy",
            message_type=MessageType.COMMAND,
            subject="Original",
            payload={"request": "analyze"},
        )

        response = await bus.send_response(
            original,
            {"result": "bullish"}
        )

        assert response.subject == "Re: Original"
        assert response.from_agent == "strategy"
        assert response.to_agent == "supervisor"
        assert response.message_type == MessageType.RESPONSE

        # Original should be marked processed with response link
        updated_original = await bus.get_message_by_id(original.id)
        assert updated_original.processed is True
        assert updated_original.response_message_id == response.id

    async def test_broadcast_halt(self, test_db):
        """Test broadcasting HALT message to all agents."""
        bus = MessageBus(db=test_db)

        await bus.broadcast_halt("supervisor", "Emergency stop")

        # Check messages were sent to all other agents
        strategy_msgs = await bus.receive_messages("strategy")
        risk_msgs = await bus.receive_messages("risk")
        execution_msgs = await bus.receive_messages("execution")

        assert len(strategy_msgs) == 1
        assert len(risk_msgs) == 1
        assert len(execution_msgs) == 1

        # All should be HALT with CRITICAL priority
        for msg in [strategy_msgs[0], risk_msgs[0], execution_msgs[0]]:
            assert msg.message_type == MessageType.HALT
            assert msg.priority == MessagePriority.CRITICAL
            assert msg.subject == "EMERGENCY HALT"


@pytest.mark.asyncio
class TestSharedState:
    """Tests for SharedStateManager class."""

    async def test_create_and_retrieve_cycle(self, test_db):
        """Test creating and retrieving a coordination cycle."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(
            active_agents={"supervisor": "active", "strategy": "pending"}
        )

        assert state.cycle_id is not None
        assert state.phase == CoordinationPhase.INITIALIZING
        assert state.active_agents["supervisor"] == "active"

        # Retrieve
        retrieved = await manager.get_current_cycle(state.cycle_id)
        assert retrieved.cycle_id == state.cycle_id

    async def test_phase_transition_supervisor_only(self, test_db):
        """Test that only supervisor can transition phases."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        # Supervisor can transition
        success = await manager.transition_phase(
            state.cycle_id,
            CoordinationPhase.STRATEGY_ANALYSIS,
            "supervisor"
        )
        assert success is True

        # Other agents cannot transition
        success = await manager.transition_phase(
            state.cycle_id,
            CoordinationPhase.EXECUTION,
            "strategy"
        )
        assert success is False

    async def test_write_access_control(self, test_db):
        """Test that agents can only write their prefixed keys."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        # Strategy agent can write strategy_* keys
        success = await manager.write_shared_data(
            state.cycle_id,
            "strategy_analysis",
            {"result": "bullish"},
            "strategy"
        )
        assert success is True

        # Strategy agent cannot write risk_* keys
        success = await manager.write_shared_data(
            state.cycle_id,
            "risk_check",
            {"result": "approved"},
            "strategy"
        )
        assert success is False

        # Supervisor can write any key
        success = await manager.write_shared_data(
            state.cycle_id,
            "any_key",
            {"data": "test"},
            "supervisor"
        )
        assert success is True

    async def test_read_shared_data(self, test_db):
        """Test reading shared data."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        await manager.write_shared_data(
            state.cycle_id,
            "test_key",
            {"value": 123},
            "supervisor"
        )

        value = await manager.read_shared_data(state.cycle_id, "test_key")
        assert value == {"value": 123}

        # Non-existent key returns None
        missing = await manager.read_shared_data(state.cycle_id, "missing")
        assert missing is None

    async def test_request_halt(self, test_db):
        """Test requesting a halt."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        await manager.request_halt(state.cycle_id, "Test halt", "risk")

        updated = await manager.get_current_cycle(state.cycle_id)
        assert updated.halt_requested is True
        assert "risk: Test halt" in updated.halt_reason
        assert updated.phase == CoordinationPhase.HALTED

    async def test_complete_cycle(self, test_db):
        """Test completing a cycle."""
        manager = SharedStateManager(db=test_db)

        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        await manager.complete_cycle(
            state.cycle_id,
            result={"success": True, "trades": 5}
        )

        updated = await manager.get_current_cycle(state.cycle_id)
        assert updated.phase == CoordinationPhase.COMPLETED
        assert updated.cycle_completed_at is not None
        assert updated.cycle_result["success"] is True


@pytest.mark.asyncio
class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    async def test_heartbeat(self, test_db):
        """Test recording agent heartbeat."""
        monitor = HealthMonitor(db=test_db)

        await monitor.heartbeat("strategy", response_time_ms=50.0)

        health = await monitor.get_agent_health("strategy")
        assert health is not None
        assert health.is_healthy is True
        assert health.agent_name == "strategy"

    async def test_record_success(self, test_db):
        """Test recording successful operation."""
        monitor = HealthMonitor(db=test_db)

        await monitor.heartbeat("strategy")
        await monitor.record_success("strategy")
        await monitor.record_success("strategy")

        health = await monitor.get_agent_health("strategy")
        assert health.success_count == 2

    async def test_record_error_marks_unhealthy(self, test_db):
        """Test that high error rate marks agent unhealthy."""
        monitor = HealthMonitor(db=test_db)

        await monitor.heartbeat("strategy")
        
        # Record errors to exceed 50% error rate
        await monitor.record_error("strategy", "Error 1")
        await monitor.record_error("strategy", "Error 2")

        health = await monitor.get_agent_health("strategy")
        assert health.error_count == 2
        assert health.is_healthy is False

    async def test_check_all_agents(self, test_db):
        """Test checking health of all agents."""
        monitor = HealthMonitor(db=test_db)

        # Initialize healthy agents
        await monitor.heartbeat("strategy")
        await monitor.heartbeat("risk")
        await monitor.record_success("strategy")
        await monitor.record_success("risk")

        health_status = await monitor.check_all_agents()

        assert health_status["strategy"] is True
        assert health_status["risk"] is True

    async def test_unresponsive_agent_detection(self, test_db):
        """Test detection of unresponsive agents."""
        monitor = HealthMonitor(db=test_db)
        monitor.heartbeat_timeout_seconds = 1  # Set very short timeout for test

        await monitor.heartbeat("strategy")

        # Wait for timeout (simulated by checking with old timestamp)
        health = await monitor.get_agent_health("strategy")
        health.last_heartbeat = datetime.utcnow() - timedelta(seconds=120)
        await test_db.commit()

        health_status = await monitor.check_all_agents()
        assert health_status["strategy"] is False


@pytest.mark.asyncio
class TestCoordinationPipeline:
    """Tests for CoordinationPipeline class."""

    async def test_execute_full_cycle(self, test_db):
        """Test executing a complete coordination cycle."""
        pipeline = CoordinationPipeline(db=test_db, system_mode=SystemMode.GUIDE)

        result = await pipeline.execute_cycle(
            symbol="EURUSD",
            strategies=["MA_CROSSOVER", "RSI"],
            account_balance=10000.0,
            peak_balance=10000.0
        )

        assert result["success"] is True
        assert "strategy" in result["phases_completed"]
        assert "risk" in result["phases_completed"]
        assert "execution" in result["phases_completed"]
        assert result["mode"] == "guide"

    async def test_cycle_creates_messages(self, test_db):
        """Test that cycle execution creates inter-agent messages."""
        pipeline = CoordinationPipeline(db=test_db, system_mode=SystemMode.GUIDE)
        bus = MessageBus(db=test_db)

        await pipeline.execute_cycle(
            symbol="EURUSD",
            strategies=["MA_CROSSOVER"],
            account_balance=10000.0,
            peak_balance=10000.0
        )

        # Check messages were sent
        strategy_msgs = await bus.get_messages_for_agent("strategy", include_processed=True)
        risk_msgs = await bus.get_messages_for_agent("risk", include_processed=True)
        execution_msgs = await bus.get_messages_for_agent("execution", include_processed=True)

        assert len(strategy_msgs) > 0
        assert len(risk_msgs) > 0
        assert len(execution_msgs) > 0

    async def test_halt_cycle(self, test_db):
        """Test halting a coordination cycle."""
        pipeline = CoordinationPipeline(db=test_db, system_mode=SystemMode.GUIDE)
        manager = SharedStateManager(db=test_db)

        # Create a cycle
        state = await manager.create_cycle(active_agents={"supervisor": "active"})

        # Halt it
        await pipeline.halt_cycle(state.cycle_id, "Test halt reason")

        # Verify halted
        updated = await manager.get_current_cycle(state.cycle_id)
        assert updated.halt_requested is True
        assert updated.phase == CoordinationPhase.HALTED

    async def test_get_cycle_status(self, test_db):
        """Test getting cycle status."""
        pipeline = CoordinationPipeline(db=test_db, system_mode=SystemMode.GUIDE)

        result = await pipeline.execute_cycle(
            symbol="EURUSD",
            strategies=["MA_CROSSOVER"],
            account_balance=10000.0,
            peak_balance=10000.0
        )

        status = await pipeline.get_cycle_status(result["cycle_id"])

        assert status is not None
        assert status["cycle_id"] == result["cycle_id"]
        assert status["phase"] == "completed"

    async def test_cycle_writes_shared_data(self, test_db):
        """Test that cycle writes expected shared data."""
        pipeline = CoordinationPipeline(db=test_db, system_mode=SystemMode.GUIDE)
        manager = SharedStateManager(db=test_db)

        result = await pipeline.execute_cycle(
            symbol="GBPUSD",
            strategies=["RSI"],
            account_balance=5000.0,
            peak_balance=6000.0
        )

        # Check shared data was written
        symbol = await manager.read_shared_data(result["cycle_id"], "symbol")
        balance = await manager.read_shared_data(result["cycle_id"], "account_balance")
        mode = await manager.read_shared_data(result["cycle_id"], "mode")

        assert symbol == "GBPUSD"
        assert balance == 5000.0
        assert mode == "guide"
