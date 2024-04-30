import asyncio
import json
from typing import Callable, Coroutine

import websockets

from models import Identify, OpCode, Payload


class DiscordWebsocket:
    GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

    def __init__(self, token: str):
        self._resume_gateway_url: str = ""
        self._heartbeat_interval = 0
        self._session_id: str = ""
        self._sequence = 0

        self._connected = False
        self._ready = asyncio.Event()

        self._ws_close_callback: list[Callable | Coroutine] = []
        self._ws_event_callback: Callable = None  # type: ignore

        self.token = token
        self.ws: websockets.WebSocketClientProtocol = None  # type: ignore
        self.heartbeat_task: asyncio.Task = None  # type: ignore

    def is_ready(self):
        return self._ready.is_set()

    def is_connected(self):
        return self._connected

    async def connect(self):
        url = self.GATEWAY_URL
        if self._resume_gateway_url:
            url = self._resume_gateway_url

        self.ws = await websockets.connect(url, max_size=10485760)
        self._ready.set()
        asyncio.create_task(self._ws_loop())

    async def send(self, opcode: OpCode, data: dict | str | int):
        await self._ready.wait()
        if not self.ws.closed:
            await self.ws.send(json.dumps({"op": opcode.value, "d": data}))

    async def send_heartbeat(self):
        await self.send(
            OpCode.HEARTBEAT, "null" if self._sequence == 0 else self._sequence
        )

    async def send_resume(self):
        await self.send(
            OpCode.RESUME,
            {
                "token": self.token,
                "session_id": self.sessionId,
                "seq": self._sequence,
            },
        )

    async def send_identify(self):
        await self.send(
            OpCode.IDENTIFY,
            Identify.from_token(self.token).to_json(),
        )

    async def send_heartbeat_loop(self):
        while True:
            await self.send_heartbeat()
            await asyncio.sleep(self._heartbeat_interval / 1000)

    def stop_heartbeat_job(self):
        if self.heartbeat_task is not None:
            if not self.heartbeat_task.done():
                self.heartbeat_task.cancel()

    def start_heartbeat_job(self):
        self.stop_heartbeat_job()
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat_loop())

    async def handle_close(self):
        self.stop_heartbeat_job()
        self.connected = False
        await self.ws.close()

        if self.ws.close_code == 4000:
            await asyncio.sleep(1)
            await self.connect()
        else:
            await self.close()

    async def handle_dispatch(self, payload: Payload):
        match payload.t:
            case "READY":
                ready = payload.d
                self.sessionId = ready["session_id"]
                self._resume_gateway_url = (
                    ready["resume_gateway_url"] + "/?v=10&encoding=json"
                )
                self.connected = True

            case "RESUMED":
                self.connected = True

            case _:
                pass

    async def handle_hello(self, payload: Payload):
        if self._sequence > 0 and self.sessionId != "":
            await self.send_resume()
        else:
            await self.send_identify()

        self._heartbeat_interval = payload.d["heartbeat_interval"]
        self.start_heartbeat_job()

    async def handle_invalid_session(self):
        await asyncio.sleep(1)
        await self.send_identify()

    async def reconnect_gateway(self):
        pass

    async def handle_event(self, payload: Payload):
        if self._ws_event_callback is not None:
            await self._ws_event_callback(payload)

    def set_event_callback(self, func: Callable):
        self._ws_event_callback = func

    async def on_message(self, payload: Payload):
        if payload.s > self._sequence:
            self._sequence = payload.s

        match payload.op:
            case OpCode.DISPATCH:
                await self.handle_dispatch(payload)
            case OpCode.HELLO:
                await self.handle_hello(payload)
            case OpCode.INVALID_SESSION:
                await self.handle_invalid_session()
            case OpCode.RECONNECT:
                await self.reconnect_gateway()
            case OpCode.UNKNOWN:
                await self.handle_event(payload)
            case _:
                return

    async def _ws_loop(self):
        while not self.ws.closed:
            try:
                recv = await self.ws.recv()
            except websockets.exceptions.ConnectionClosedOK:
                break

            if recv == "":
                break

            await self.on_message(Payload.from_str(recv))  # type: ignore
        await self.handle_close()

    def add_close_callback(self, func: Callable | Coroutine):
        self._ws_close_callback.append(func)

    async def close(self):
        if self.ws.closed:
            return

        for func in self._ws_close_callback:
            if isinstance(func, Coroutine):
                await func
            else:
                func()

        self.stop_heartbeat_job()
        await self.ws.close()
