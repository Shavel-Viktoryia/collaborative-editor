from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import asyncio
from typing import List, Dict

app = FastAPI()

class DocumentState(BaseModel):
    content: str = ""
    version: int = 0
    operations: List[Dict] = []

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.document = DocumentState()
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        await websocket.send_json({
            "type": "init",
            "content": self.document.content,
            "version": self.document.version
        })

    async def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def adjust_operation(self, op: Dict, client_version: int) -> Dict:
        adjusted_pos = op["position"]
        for existing_op in self.document.operations[client_version:]:
            if existing_op["type"] == "insert":
                if existing_op["position"] <= adjusted_pos:
                    adjusted_pos += len(existing_op["text"])
            elif existing_op["type"] == "delete":
                start = existing_op["position"]
                length = existing_op["length"]
                if start <= adjusted_pos:
                    if start + length <= adjusted_pos:
                        adjusted_pos -= length
                    else:
                        adjusted_pos = start
        return {**op, "position": adjusted_pos}
    
    async def apply_operation(self, op: Dict):
        if op["type"] == "insert":
            self.document.content = (
                self.document.content[:op["position"]] 
                + op["text"] 
                + self.document.content[op["position"]:]
            )
        elif op["type"] == "delete":
            start = op["position"]
            end = start + op["length"]
            self.document.content = (
                self.document.content[:start] 
                + self.document.content[end:]
            )
    
    async def broadcast(self, message: Dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data["type"] == "edit":
                async with manager.lock:
                    client_version = data["version"]
                    op = data["operation"]

                    if client_version < manager.document.version:
                        op = await manager.adjust_operation(op, client_version)

                    op["version"] = manager.document.version
                    await manager.apply_operation(op)
                    manager.document.operations.append(op)
                    manager.document.version += 1

                    await manager.broadcast({
                        "type": "update",
                        "operation": op,
                        "version": manager.document.version
                    })
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
