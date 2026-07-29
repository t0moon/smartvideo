from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self.active.setdefault(project_id, []).append(ws)

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        if project_id in self.active:
            self.active[project_id] = [w for w in self.active[project_id] if w != ws]

    async def broadcast(self, project_id: str, message: dict) -> None:
        for ws in self.active.get(project_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket('/ws/{project_id}')
async def websocket_endpoint(ws: WebSocket, project_id: str) -> None:
    await manager.connect(project_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            # Echo for now; future: handle commands
            await ws.send_json({'type': 'echo', 'data': data})
    except WebSocketDisconnect:
        manager.disconnect(project_id, ws)
