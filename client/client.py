import asyncio
import websockets
import json
from aioconsole import ainput

class CollaborativeClient:
    def __init__(self):
        self.content = ""
        self.version = 0

    async def connect(self, uri):
        self.websocket = await websockets.connect(uri)
        response = await self.websocket.recv()
        init_data = json.loads(response)
        if init_data["type"] == "init":
            self.content = init_data["content"]
            self.version = init_data["version"]
            print(f"Connected. Initial content: {self.content}")

        asyncio.create_task(self.listen_for_updates())
        await self.input_loop()

    async def listen_for_updates(self):
        try:
            async for message in self.websocket:
                data = json.loads(message)
                if data["type"] == "update":
                    self.apply_operation(data["operation"])
                    self.version = data["version"]
                    print(f"\n--- New content: ---\n{self.content}\nEnter edit (pos text): ", end="")
        except websockets.exceptions.ConnectionClosed:
            print("Disconnected from server.")

    def apply_operation(self, op):  # Fixed typo in method name
        if op["type"] == "insert":
            self.content = (
                self.content[:op["position"]] 
                + op["text"] 
                + self.content[op["position"]:]
            )
        elif op["type"] == "delete":
            start = op["position"]
            end = start + op["length"]
            self.content = self.content[:start] + self.content[end:]

    async def input_loop(self):
        while True:
            try:
                user_input = await ainput("Enter edit (pos text) or '/delete pos length': ")
                if user_input.startswith("/delete"):
                    _, pos, length = user_input.split()
                    op = {
                        "type": "delete",
                        "position": int(pos),
                        "length": int(length)
                    }
                else:
                    pos, text = user_input.split(" ", 1)
                    op = {
                        "type": "insert",
                        "position": int(pos),
                        "text": text
                    }
                await self.websocket.send(json.dumps({
                    "type": "edit",
                    "version": self.version,
                    "operation": op
                }))
            except Exception as e:
                print(f"Error: {e}")

async def main():
    client = CollaborativeClient()
    await client.connect("ws://localhost:8000/ws")

if __name__ == "__main__":
    asyncio.run(main())