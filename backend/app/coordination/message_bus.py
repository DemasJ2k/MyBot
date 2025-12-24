"""
Inter-agent message bus for coordination.

Enforces:
- Priority-based message delivery
- Message expiration
- Request-response correlation
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.models.coordination import (
    AgentMessage,
    MessageType,
    MessagePriority,
)
import logging

logger = logging.getLogger(__name__)


class MessageBus:
    """
    Inter-agent message bus for coordination.

    Enforces:
    - Priority-based message delivery
    - Message expiration
    - Request-response correlation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        subject: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        expires_in_seconds: Optional[int] = None
    ) -> AgentMessage:
        """
        Send a message from one agent to another.

        Args:
            from_agent: Sender agent name
            to_agent: Recipient agent name
            message_type: Type of message
            subject: Message subject
            payload: Message data
            priority: Message priority
            expires_in_seconds: Optional expiration time

        Returns:
            Created message
        """
        expires_at = None
        if expires_in_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)

        message = AgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            priority=priority,
            subject=subject,
            payload=payload,
            processed=False,
            sent_at=datetime.utcnow(),
            expires_at=expires_at
        )

        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)

        logger.debug(f"Message sent: {from_agent} -> {to_agent} ({message_type.value}): {subject}")

        return message

    async def receive_messages(
        self,
        agent_name: str,
        message_type: Optional[MessageType] = None,
        limit: int = 10
    ) -> List[AgentMessage]:
        """
        Receive pending messages for an agent.

        Args:
            agent_name: Agent name
            message_type: Optional filter by message type
            limit: Maximum messages to retrieve

        Returns:
            List of unprocessed messages, ordered by priority then time
        """
        # Build query
        stmt = select(AgentMessage).where(
            and_(
                AgentMessage.to_agent == agent_name,
                AgentMessage.processed == False,
                or_(
                    AgentMessage.expires_at.is_(None),
                    AgentMessage.expires_at > datetime.utcnow()
                )
            )
        )

        if message_type:
            stmt = stmt.where(AgentMessage.message_type == message_type)

        # Order by priority (lower number = higher priority), then by sent time
        stmt = stmt.order_by(
            AgentMessage.priority.asc(),
            AgentMessage.sent_at.asc()
        ).limit(limit)

        result = await self.db.execute(stmt)
        messages = list(result.scalars().all())

        return messages

    async def mark_processed(
        self,
        message_id: int,
        response_message_id: Optional[int] = None
    ):
        """Mark a message as processed."""
        stmt = select(AgentMessage).where(AgentMessage.id == message_id)
        result = await self.db.execute(stmt)
        message = result.scalar_one_or_none()

        if message:
            message.processed = True
            message.processed_at = datetime.utcnow()
            if response_message_id:
                message.response_message_id = response_message_id
            await self.db.commit()

    async def send_response(
        self,
        original_message: AgentMessage,
        response_payload: Dict[str, Any]
    ) -> AgentMessage:
        """
        Send a response to a message.

        Args:
            original_message: Message to respond to
            response_payload: Response data

        Returns:
            Response message
        """
        response = await self.send_message(
            from_agent=original_message.to_agent,
            to_agent=original_message.from_agent,
            message_type=MessageType.RESPONSE,
            subject=f"Re: {original_message.subject}",
            payload=response_payload,
            priority=original_message.priority
        )

        # Mark original as processed with response link
        await self.mark_processed(original_message.id, response.id)

        return response

    async def broadcast_halt(
        self,
        from_agent: str,
        reason: str
    ):
        """
        Broadcast HALT message to all agents.

        Args:
            from_agent: Agent issuing halt
            reason: Halt reason
        """
        agents = ["supervisor", "strategy", "risk", "execution"]

        for agent in agents:
            if agent != from_agent:
                await self.send_message(
                    from_agent=from_agent,
                    to_agent=agent,
                    message_type=MessageType.HALT,
                    subject="EMERGENCY HALT",
                    payload={"reason": reason, "timestamp": datetime.utcnow().isoformat()},
                    priority=MessagePriority.CRITICAL,
                    expires_in_seconds=60
                )

        logger.critical(f"HALT broadcast from {from_agent}: {reason}")

    async def get_message_by_id(self, message_id: int) -> Optional[AgentMessage]:
        """Get a message by ID."""
        stmt = select(AgentMessage).where(AgentMessage.id == message_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_messages_for_agent(
        self,
        agent_name: str,
        include_processed: bool = False,
        limit: int = 50
    ) -> List[AgentMessage]:
        """Get all messages for an agent."""
        stmt = select(AgentMessage).where(AgentMessage.to_agent == agent_name)
        
        if not include_processed:
            stmt = stmt.where(AgentMessage.processed == False)
        
        stmt = stmt.order_by(AgentMessage.sent_at.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
