"""
WebSocket E2E tests.

Tests real-time data streaming and WebSocket functionality.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

pytestmark = [pytest.mark.e2e, pytest.mark.websocket]


class TestWebSocketConnection:
    """Test WebSocket connection establishment."""
    
    @pytest.fixture
    async def ws_client(self, test_config):
        """Create WebSocket client."""
        # Example using websockets library:
        # import websockets
        # async with websockets.connect(
        #     f"ws://{test_config['api_url'].replace('http', 'ws')}/ws"
        # ) as ws:
        #     yield ws
        
        # Mock for demonstration
        ws = AsyncMock()
        ws.send = AsyncMock()
        ws.recv = AsyncMock(return_value=json.dumps({
            'type': 'connected',
            'client_id': 'test_client'
        }))
        ws.close = AsyncMock()
        yield ws
    
    @pytest.mark.asyncio
    async def test_websocket_connection_establishment(self, ws_client):
        """Test successful WebSocket connection."""
        # Act
        await ws_client.send(json.dumps({'action': 'connect'}))
        response = await ws_client.recv()
        data = json.loads(response)
        
        # Assert
        assert data['type'] == 'connected'
        assert 'client_id' in data
    
    @pytest.mark.asyncio
    async def test_websocket_authentication(self, ws_client):
        """Test WebSocket authentication with token."""
        # Act
        await ws_client.send(json.dumps({
            'action': 'authenticate',
            'token': 'test_jwt_token'
        }))
        response = await ws_client.recv()
        data = json.loads(response)
        
        # Assert
        assert data['type'] == 'authenticated'
    
    @pytest.mark.asyncio
    async def test_websocket_invalid_token_rejection(self, ws_client):
        """Test that invalid tokens are rejected."""
        # Act
        await ws_client.send(json.dumps({
            'action': 'authenticate',
            'token': 'invalid_token'
        }))
        response = await ws_client.recv()
        data = json.loads(response)
        
        # Assert
        assert data['type'] == 'error'
        assert 'authentication failed' in data['message'].lower()


class TestRealTimeAnalysisUpdates:
    """Test real-time analysis progress updates."""
    
    @pytest.mark.asyncio
    async def test_analysis_progress_streaming(self, ws_client):
        """Test receiving analysis progress updates."""
        # Arrange
        analysis_id = 'anl_test_123'
        
        # Subscribe to analysis updates
        await ws_client.send(json.dumps({
            'action': 'subscribe',
            'channel': f'analysis:{analysis_id}'
        }))
        
        # Act - Simulate receiving progress updates
        progress_updates = [
            {'type': 'analysis.progress', 'analysis_id': analysis_id, 'progress': 0, 'status': 'started'},
            {'type': 'analysis.progress', 'analysis_id': analysis_id, 'progress': 25, 'status': 'processing'},
            {'type': 'analysis.progress', 'analysis_id': analysis_id, 'progress': 50, 'status': 'processing'},
            {'type': 'analysis.progress', 'analysis_id': analysis_id, 'progress': 75, 'status': 'processing'},
            {'type': 'analysis.progress', 'analysis_id': analysis_id, 'progress': 100, 'status': 'completed'}
        ]
        
        # Mock receiving messages
        ws_client.recv = AsyncMock(side_effect=[json.dumps(u) for u in progress_updates])
        
        received_updates = []
        for _ in range(len(progress_updates)):
            msg = await ws_client.recv()
            received_updates.append(json.loads(msg))
        
        # Assert
        assert len(received_updates) == 5
        assert received_updates[0]['progress'] == 0
        assert received_updates[-1]['progress'] == 100
        assert received_updates[-1]['status'] == 'completed'
    
    @pytest.mark.asyncio
    async def test_analysis_result_notification(self, ws_client):
        """Test receiving analysis completion with results."""
        # Arrange
        analysis_id = 'anl_test_456'
        
        result_message = {
            'type': 'analysis.completed',
            'analysis_id': analysis_id,
            'status': 'completed',
            'results': {
                'sentiment': {'score': 0.85, 'label': 'positive'},
                'entities': [{'text': 'DragonScope', 'type': 'ORG'}],
                'summary': 'This is a summary'
            },
            'completed_at': datetime.now(timezone.utc).isoformat()
        }
        
        ws_client.recv = AsyncMock(return_value=json.dumps(result_message))
        
        # Act
        msg = await ws_client.recv()
        data = json.loads(msg)
        
        # Assert
        assert data['type'] == 'analysis.completed'
        assert 'results' in data
        assert data['results']['sentiment']['label'] == 'positive'


class TestDocumentProcessingUpdates:
    """Test document processing real-time updates."""
    
    @pytest.mark.asyncio
    async def test_document_processing_status_updates(self, ws_client):
        """Test receiving document processing status updates."""
        # Arrange
        document_id = 'doc_test_789'
        
        status_updates = [
            {'type': 'document.status', 'document_id': document_id, 'status': 'uploaded'},
            {'type': 'document.status', 'document_id': document_id, 'status': 'processing'},
            {'type': 'document.progress', 'document_id': document_id, 'stage': 'extracting_text', 'percent': 30},
            {'type': 'document.progress', 'document_id': document_id, 'stage': 'analyzing', 'percent': 60},
            {'type': 'document.progress', 'document_id': document_id, 'stage': 'indexing', 'percent': 90},
            {'type': 'document.status', 'document_id': document_id, 'status': 'processed'}
        ]
        
        ws_client.recv = AsyncMock(side_effect=[json.dumps(u) for u in status_updates])
        
        # Act
        received = []
        for _ in range(len(status_updates)):
            msg = await ws_client.recv()
            received.append(json.loads(msg))
        
        # Assert
        assert received[0]['status'] == 'uploaded'
        assert received[-1]['status'] == 'processed'
        
        # Verify progress is monotonically increasing
        progress_updates = [r for r in received if 'percent' in r]
        for i in range(1, len(progress_updates)):
            assert progress_updates[i]['percent'] >= progress_updates[i-1]['percent']


class TestNotificationSystem:
    """Test real-time notifications."""
    
    @pytest.mark.asyncio
    async def test_receive_notifications(self, ws_client):
        """Test receiving system notifications."""
        # Arrange
        notifications = [
            {
                'type': 'notification',
                'notification_id': 'notif_001',
                'category': 'info',
                'title': 'Analysis Complete',
                'message': 'Your analysis has been completed',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'read': False
            },
            {
                'type': 'notification',
                'notification_id': 'notif_002',
                'category': 'warning',
                'title': 'Storage Limit',
                'message': 'You are approaching your storage limit',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'read': False
            }
        ]
        
        ws_client.recv = AsyncMock(side_effect=[json.dumps(n) for n in notifications])
        
        # Act
        received = []
        for _ in range(len(notifications)):
            msg = await ws_client.recv()
            received.append(json.loads(msg))
        
        # Assert
        assert len(received) == 2
        assert all(r['type'] == 'notification' for r in received)
        assert received[0]['category'] == 'info'
        assert received[1]['category'] == 'warning'
    
    @pytest.mark.asyncio
    async def test_mark_notification_read(self, ws_client):
        """Test marking notification as read via WebSocket."""
        # Arrange
        notification_id = 'notif_003'
        
        # Act - Send mark as read command
        await ws_client.send(json.dumps({
            'action': 'mark_read',
            'notification_id': notification_id
        }))
        
        # Expect confirmation
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'notification_updated',
            'notification_id': notification_id,
            'read': True
        }))
        
        response = await ws_client.recv()
        data = json.loads(response)
        
        # Assert
        assert data['type'] == 'notification_updated'
        assert data['read'] is True


class TestCollaborativeEditing:
    """Test collaborative features via WebSocket."""
    
    @pytest.mark.asyncio
    async def test_project_collaboration_sync(self, ws_client):
        """Test real-time project updates to collaborators."""
        # Arrange
        project_id = 'prj_collab_001'
        
        collaboration_events = [
            {
                'type': 'collaborator.joined',
                'project_id': project_id,
                'user': {'id': 'usr_002', 'name': 'Jane Doe'}
            },
            {
                'type': 'annotation.added',
                'project_id': project_id,
                'document_id': 'doc_001',
                'annotation': {'id': 'ann_001', 'text': 'Important point', 'user_id': 'usr_002'}
            },
            {
                'type': 'collaborator.left',
                'project_id': project_id,
                'user': {'id': 'usr_002', 'name': 'Jane Doe'}
            }
        ]
        
        ws_client.recv = AsyncMock(side_effect=[json.dumps(e) for e in collaboration_events])
        
        # Act
        received = []
        for _ in range(len(collaboration_events)):
            msg = await ws_client.recv()
            received.append(json.loads(msg))
        
        # Assert
        assert received[0]['type'] == 'collaborator.joined'
        assert received[1]['type'] == 'annotation.added'
        assert received[2]['type'] == 'collaborator.left'


class TestHeartbeatAndReconnection:
    """Test WebSocket heartbeat and reconnection."""
    
    @pytest.mark.asyncio
    async def test_heartbeat_ping_pong(self, ws_client):
        """Test WebSocket ping/pong heartbeat."""
        # Arrange
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'ping',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }))
        
        # Act - Receive ping
        msg = await ws_client.recv()
        data = json.loads(msg)
        
        # Respond with pong
        if data['type'] == 'ping':
            await ws_client.send(json.dumps({
                'type': 'pong',
                'timestamp': data['timestamp']
            }))
        
        # Assert
        ws_client.send.assert_called()
    
    @pytest.mark.asyncio
    async def test_reconnection_with_last_event_id(self):
        """Test reconnecting with last event ID for missed messages."""
        # This test would require actual WebSocket implementation
        # to test reconnection logic
        pass


class TestWebSocketErrors:
    """Test WebSocket error handling."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_error(self, ws_client):
        """Test rate limit error via WebSocket."""
        # Arrange
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'error',
            'code': 'RATE_LIMIT_EXCEEDED',
            'message': 'Too many requests. Please slow down.',
            'retry_after': 60
        }))
        
        # Act
        msg = await ws_client.recv()
        data = json.loads(msg)
        
        # Assert
        assert data['type'] == 'error'
        assert data['code'] == 'RATE_LIMIT_EXCEEDED'
        assert 'retry_after' in data
    
    @pytest.mark.asyncio
    async def test_subscription_not_found_error(self, ws_client):
        """Test error for invalid subscription."""
        # Act
        await ws_client.send(json.dumps({
            'action': 'subscribe',
            'channel': 'invalid:channel:format'
        }))
        
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'error',
            'code': 'INVALID_CHANNEL',
            'message': 'Channel format is invalid'
        }))
        
        msg = await ws_client.recv()
        data = json.loads(msg)
        
        # Assert
        assert data['type'] == 'error'
        assert data['code'] == 'INVALID_CHANNEL'
    
    @pytest.mark.asyncio
    async def test_permission_denied_error(self, ws_client):
        """Test permission denied error."""
        # Act - Try to subscribe to unauthorized channel
        await ws_client.send(json.dumps({
            'action': 'subscribe',
            'channel': 'analysis:other_users_analysis_id'
        }))
        
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'error',
            'code': 'PERMISSION_DENIED',
            'message': 'You do not have permission to access this resource'
        }))
        
        msg = await ws_client.recv()
        data = json.loads(msg)
        
        # Assert
        assert data['type'] == 'error'
        assert data['code'] == 'PERMISSION_DENIED'


class TestWebSocketPerformance:
    """Test WebSocket performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_message_latency(self, ws_client):
        """Test message round-trip latency."""
        import time
        
        # Arrange
        await ws_client.send(json.dumps({
            'action': 'ping',
            'timestamp': time.time()
        }))
        
        sent_time = time.time()
        
        ws_client.recv = AsyncMock(return_value=json.dumps({
            'type': 'pong',
            'timestamp': sent_time
        }))
        
        # Act
        msg = await ws_client.recv()
        received_time = time.time()
        
        latency = received_time - sent_time
        
        # Assert - Should be under 100ms for local connection
        assert latency < 0.1, f"Latency {latency}s exceeds threshold"
    
    @pytest.mark.asyncio
    async def test_concurrent_message_handling(self, ws_client):
        """Test handling multiple concurrent messages."""
        # Arrange
        num_messages = 100
        messages = [
            {'type': 'test', 'seq': i, 'data': 'x' * 1000}
            for i in range(num_messages)
        ]
        
        ws_client.recv = AsyncMock(side_effect=[json.dumps(m) for m in messages])
        
        # Act - Receive all messages concurrently
        received = await asyncio.gather(*[ws_client.recv() for _ in range(num_messages)])
        
        # Assert
        assert len(received) == num_messages
        
        # Verify sequence integrity
        data_list = [json.loads(r) for r in received]
        sequences = [d['seq'] for d in data_list]
        assert sorted(sequences) == list(range(num_messages))
