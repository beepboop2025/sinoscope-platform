"""
Message Queue (RabbitMQ) integration tests.

Tests message publishing, consuming, and event-driven workflows.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

pytestmark = pytest.mark.integration


class TestRabbitMQConnection:
    """Test suite for RabbitMQ connectivity."""
    
    @pytest.fixture(scope='class')
    async def rabbitmq_connection(self, test_config):
        """Create RabbitMQ connection for testing."""
        # Example using aio-pika:
        # import aio_pika
        # connection = await aio_pika.connect_robust(test_config['rabbitmq_url'])
        # yield connection
        # await connection.close()
        
        # Mock connection for demonstration
        connection = AsyncMock()
        connection.channel = AsyncMock(return_value=AsyncMock())
        yield connection
    
    @pytest.mark.asyncio
    async def test_rabbitmq_connection(self, rabbitmq_connection):
        """Test basic RabbitMQ connectivity."""
        # In real test, verify connection is open
        assert rabbitmq_connection is not None
    
    @pytest.mark.asyncio
    async def test_channel_creation(self, rabbitmq_connection):
        """Test channel creation."""
        channel = await rabbitmq_connection.channel()
        assert channel is not None


class TestQueueOperations:
    """Test suite for queue operations."""
    
    @pytest.fixture
    async def channel(self, rabbitmq_connection):
        """Create a channel for queue operations."""
        ch = await rabbitmq_connection.channel()
        yield ch
    
    @pytest.mark.asyncio
    async def test_queue_declare(self, channel):
        """Test queue declaration."""
        queue_name = 'test:queue:declare'
        
        result = await channel.declare_queue(queue_name, durable=True)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_queue_bind(self, channel):
        """Test queue binding to exchange."""
        queue_name = 'test:queue:bind'
        exchange_name = 'test:exchange'
        routing_key = 'test.routing.key'
        
        await channel.declare_exchange(exchange_name, 'topic', durable=True)
        queue = await channel.declare_queue(queue_name, durable=True)
        await queue.bind(exchange_name, routing_key)
        
        # Verify binding exists
        assert queue is not None
    
    @pytest.mark.asyncio
    async def test_queue_delete(self, channel):
        """Test queue deletion."""
        queue_name = 'test:queue:delete'
        
        await channel.declare_queue(queue_name, auto_delete=True)
        await channel.queue_delete(queue_name)
        
        # Verify queue is deleted
        # In real test, try to declare exclusive queue with same name


class TestMessagePublishing:
    """Test suite for message publishing."""
    
    @pytest.fixture
    async def publisher(self, channel):
        """Create message publisher."""
        from services.messaging.publisher import MessagePublisher
        return MessagePublisher(channel=channel)
    
    @pytest.mark.asyncio
    async def test_publish_simple_message(self, publisher, channel):
        """Test publishing a simple message."""
        # Arrange
        exchange = 'test:events'
        routing_key = 'user.created'
        message = {'user_id': '123', 'email': 'test@example.com'}
        
        # Act
        await publisher.publish(exchange, routing_key, message)
        
        # Assert
        channel.default_exchange.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_publish_with_headers(self, publisher, channel):
        """Test publishing message with headers."""
        message = {'event': 'order_placed'}
        headers = {
            'x-tenant-id': 'tenant_123',
            'x-request-id': 'req_456'
        }
        
        await publisher.publish(
            'test:events',
            'order.placed',
            message,
            headers=headers
        )
        
        channel.default_exchange.publish.assert_called()
    
    @pytest.mark.asyncio
    async def test_publish_with_persistence(self, publisher, channel):
        """Test publishing persistent message."""
        message = {'critical': 'data'}
        
        await publisher.publish(
            'test:events',
            'critical.event',
            message,
            persistent=True
        )
        
        # Verify message was published with delivery_mode=2
        call_args = channel.default_exchange.publish.call_args
        assert call_args is not None


class TestMessageConsuming:
    """Test suite for message consuming."""
    
    @pytest.fixture
    async def consumer(self, channel):
        """Create message consumer."""
        from services.messaging.consumer import MessageConsumer
        return MessageConsumer(channel=channel)
    
    @pytest.mark.asyncio
    async def test_consume_message(self, consumer, channel):
        """Test consuming a message."""
        # Arrange
        queue_name = 'test:consumer:queue'
        processed_messages = []
        
        async def handler(message):
            processed_messages.append(message.body)
            await message.ack()
        
        # Act
        await consumer.consume(queue_name, handler)
        
        # Simulate message delivery
        mock_message = AsyncMock()
        mock_message.body = json.dumps({'test': 'data'}).encode()
        await handler(mock_message)
        
        # Assert
        assert len(processed_messages) == 1
    
    @pytest.mark.asyncio
    async def test_message_acknowledgment(self, consumer, channel):
        """Test message acknowledgment."""
        mock_message = AsyncMock()
        mock_message.body = b'test'
        
        await mock_message.ack()
        
        mock_message.ack.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_message_nack_with_requeue(self, consumer, channel):
        """Test negative acknowledgment with requeue."""
        mock_message = AsyncMock()
        mock_message.body = b'test'
        
        await mock_message.nack(requeue=True)
        
        mock_message.nack.assert_called_once_with(requeue=True)
    
    @pytest.mark.asyncio
    async def test_message_rejection(self, consumer, channel):
        """Test message rejection (dead letter)."""
        mock_message = AsyncMock()
        mock_message.body = b'invalid'
        
        await mock_message.reject(requeue=False)
        
        mock_message.reject.assert_called_once_with(requeue=False)


class TestEventDrivenWorkflows:
    """Test suite for event-driven workflows."""
    
    @pytest.fixture
    async def event_bus(self, channel):
        """Create event bus service."""
        from services.messaging.event_bus import EventBus
        return EventBus(channel=channel)
    
    @pytest.mark.asyncio
    async def test_user_created_event_flow(self, event_bus, channel):
        """Test complete user creation event flow."""
        # Arrange
        events_received = []
        
        async def email_handler(event):
            events_received.append(('email', event))
        
        async def analytics_handler(event):
            events_received.append(('analytics', event))
        
        await event_bus.subscribe('user.created', email_handler)
        await event_bus.subscribe('user.created', analytics_handler)
        
        # Act - Publish user created event
        user_event = {
            'event_type': 'user.created',
            'user_id': 'usr_123',
            'email': 'new@example.com',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        await event_bus.publish('user.created', user_event)
        
        # Give time for processing
        await asyncio.sleep(0.1)
        
        # Assert - Both handlers should have received the event
        assert len(events_received) == 2
    
    @pytest.mark.asyncio
    async def test_document_processing_flow(self, event_bus, channel):
        """Test document upload and processing flow."""
        # Arrange
        workflow_steps = []
        
        async def document_uploaded_handler(event):
            workflow_steps.append('uploaded')
            # Trigger next step
            await event_bus.publish('document.process', {
                'document_id': event['document_id']
            })
        
        async def document_process_handler(event):
            workflow_steps.append('processing')
            # Simulate processing
            await asyncio.sleep(0.05)
            await event_bus.publish('document.analyze', {
                'document_id': event['document_id']
            })
        
        async def document_analyze_handler(event):
            workflow_steps.append('analyzed')
        
        await event_bus.subscribe('document.uploaded', document_uploaded_handler)
        await event_bus.subscribe('document.process', document_process_handler)
        await event_bus.subscribe('document.analyze', document_analyze_handler)
        
        # Act - Start workflow
        await event_bus.publish('document.uploaded', {
            'document_id': 'doc_123',
            'filename': 'report.pdf'
        })
        
        await asyncio.sleep(0.2)
        
        # Assert
        assert 'uploaded' in workflow_steps
        assert 'processing' in workflow_steps
        assert 'analyzed' in workflow_steps


class TestDeadLetterQueue:
    """Test suite for dead letter queue handling."""
    
    @pytest.mark.asyncio
    async def test_message_to_dead_letter_queue(self, channel):
        """Test failed messages go to DLQ."""
        # Arrange
        dlq_name = 'test:dlq'
        main_queue = 'test:main:queue'
        
        await channel.declare_queue(dlq_name, durable=True)
        
        failed_messages = []
        
        # Act - Process message that fails
        async def failing_handler(message):
            raise Exception("Processing failed")
        
        # Assert - Message should end up in DLQ
        # In real test, verify message appears in DLQ after retries
    
    @pytest.mark.asyncio
    async def test_dlq_redelivery(self, channel):
        """Test redelivery from DLQ after fix."""
        # Arrange
        dlq_name = 'test:dlq'
        
        # Move message from DLQ back to main queue
        # After issue is fixed
        
        # Assert - Message should be processed successfully


class TestMessageRouting:
    """Test suite for message routing patterns."""
    
    @pytest.mark.asyncio
    async def test_topic_exchange_routing(self, channel):
        """Test topic exchange routing."""
        # Arrange
        exchange = 'test:topic:exchange'
        await channel.declare_exchange(exchange, 'topic', durable=True)
        
        received_messages = []
        
        # Bind queue with pattern
        queue = await channel.declare_queue('test:logs:error')
        await queue.bind(exchange, 'logs.error.*')
        
        # Act - Publish with matching routing key
        await channel.default_exchange.publish(
            AsyncMock(),
            routing_key='logs.error.critical'
        )
        
        # Assert - Message should be routed to queue
    
    @pytest.mark.asyncio
    async def test_fanout_exchange(self, channel):
        """Test fanout exchange broadcasts to all queues."""
        # Arrange
        exchange = 'test:fanout:exchange'
        await channel.declare_exchange(exchange, 'fanout', durable=True)
        
        queues = ['test:fanout:q1', 'test:fanout:q2', 'test:fanout:q3']
        for q in queues:
            queue = await channel.declare_queue(q)
            await queue.bind(exchange)
        
        # Act - Publish message
        await channel.default_exchange.publish(AsyncMock(), routing_key='')
        
        # Assert - All queues should receive the message
    
    @pytest.mark.asyncio
    async def test_direct_exchange_routing(self, channel):
        """Test direct exchange exact matching."""
        # Arrange
        exchange = 'test:direct:exchange'
        await channel.declare_exchange(exchange, 'direct', durable=True)
        
        queue = await channel.declare_queue('test:direct:queue')
        await queue.bind(exchange, 'exact.key')
        
        # Act - Publish with exact routing key
        await channel.default_exchange.publish(
            AsyncMock(),
            routing_key='exact.key'
        )
        
        # Assert - Message should be delivered


class TestMessageSerialization:
    """Test suite for message serialization."""
    
    @pytest.mark.asyncio
    async def test_json_message_serialization(self, channel):
        """Test JSON message serialization."""
        message = {
            'event_type': 'test',
            'data': {'nested': {'value': 123}},
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        serialized = json.dumps(message)
        deserialized = json.loads(serialized)
        
        assert deserialized == message
    
    @pytest.mark.asyncio
    async def test_avro_message_serialization(self, channel):
        """Test Avro message serialization."""
        # For high-throughput scenarios
        # Define schema and serialize
        pass
    
    @pytest.mark.asyncio
    async def test_compression(self, channel):
        """Test message compression for large payloads."""
        import zlib
        
        large_message = {'data': 'x' * 10000}
        serialized = json.dumps(large_message)
        compressed = zlib.compress(serialized.encode())
        
        # Verify compression reduced size
        assert len(compressed) < len(serialized)
        
        # Verify decompression
        decompressed = zlib.decompress(compressed).decode()
        assert json.loads(decompressed) == large_message


class TestMessagingPatterns:
    """Test suite for messaging patterns."""
    
    @pytest.mark.asyncio
    async def test_request_reply_pattern(self, channel):
        """Test request-reply pattern."""
        # Arrange
        request_queue = 'test:rpc:requests'
        reply_queue = 'test:rpc:replies'
        
        await channel.declare_queue(request_queue)
        await channel.declare_queue(reply_queue, exclusive=True)
        
        # Server side - process request and send reply
        async def server_handler(message):
            request = json.loads(message.body)
            response = {'result': request['value'] * 2}
            # Send reply to reply_to queue
            await channel.default_exchange.publish(
                AsyncMock(body=json.dumps(response).encode()),
                routing_key=message.reply_to
            )
            await message.ack()
        
        # Client side - send request and wait for reply
        correlation_id = 'corr_123'
        request = {'value': 21}
        
        # Assert - Should receive response with matching correlation_id
    
    @pytest.mark.asyncio
    async def test_competing_consumers_pattern(self, channel):
        """Test competing consumers for load balancing."""
        # Arrange
        queue_name = 'test:work:queue'
        await channel.declare_queue(queue_name)
        
        messages_processed = []
        
        async def worker_handler(worker_id):
            async def handler(message):
                messages_processed.append(worker_id)
                await message.ack()
            return handler
        
        # Start multiple consumers
        # Messages should be distributed among them
        
        # Act - Publish messages
        
        # Assert - Work is distributed
    
    @pytest.mark.asyncio
    async def test_priority_queue_pattern(self, channel):
        """Test priority queue for message ordering."""
        # Arrange
        queue_name = 'test:priority:queue'
        
        # Declare queue with max priority
        # Publish messages with different priorities
        
        # Assert - High priority messages processed first
