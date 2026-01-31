"""
WebSocket Router for Real-time Audit Progress.
Level 2 Professional Feature.
"""
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ...core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["realtime"])

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, audit_id: int):
        await websocket.accept()
        if audit_id not in self.active_connections:
            self.active_connections[audit_id] = []
        self.active_connections[audit_id].append(websocket)
        logger.info(f"Client connected to progress for audit {audit_id}")

    def disconnect(self, websocket: WebSocket, audit_id: int):
        if audit_id in self.active_connections:
            self.active_connections[audit_id].remove(websocket)
            if not self.active_connections[audit_id]:
                del self.active_connections[audit_id]
        logger.info(f"Client disconnected from audit {audit_id}")

    async def broadcast_progress(self, audit_id: int, message: dict):
        if audit_id in self.active_connections:
            for connection in self.active_connections[audit_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to WS: {e}")

manager = ConnectionManager()

@router.websocket("/ws/progress/{audit_id}")
async def websocket_endpoint(websocket: WebSocket, audit_id: int):
    await manager.connect(websocket, audit_id)
    
    # Level 3: Redis Listener for the specific audit
    from ...services.cache_service import cache
    pubsub = None
    
    if cache.enabled:
        pubsub = cache.redis_client.pubsub()
        pubsub.subscribe(f"audit_progress_{audit_id}")
        logger.info(f"Subscribed to Redis: audit_progress_{audit_id}")

    try:
        # Loop para escuchar ambos: mensajes del cliente y de Redis
        while True:
            # Opción A: Escuchar Redis (blocking with timeout)
            if pubsub:
                # get_message() is non-blocking, but we can't easily use listen() with select/poll here
                # in a simple way without more complexity. 
                # Let's keep it simple but functional.
                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg['type'] == 'message':
                    # data can be bytes or str depending on redis-py version/config
                    data = msg['data']
                    if isinstance(data, bytes):
                        data = data.decode('utf-8')
                    await websocket.send_text(data)
            else:
                # Fallback if no redis: keep-alive
                await websocket.send_json({"type": "ping"})
                await asyncio.sleep(5)
            
            # Opción B: Receive data from client if needed (to keep connection alive)
            # This is optional but good for some proxies
            # try:
            #     await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
            # except asyncio.TimeoutError:
            #     pass
                
    except WebSocketDisconnect:
        if pubsub:
            pubsub.unsubscribe(f"audit_progress_{audit_id}")
        manager.disconnect(websocket, audit_id)
    except Exception as e:
        logger.error(f"WS Error: {e}")
        if pubsub:
            pubsub.unsubscribe(f"audit_progress_{audit_id}")
        manager.disconnect(websocket, audit_id)

