import asyncio
from signal import SIGINT, SIGTERM
from typing import Callable, Coroutine

import httpx

from models import OpCode, Payload, Presence
from ws import DiscordWebsocket


EventCallBackType = Callable[["DiscordClient", Payload], Coroutine]


class DiscordClient:
    def __init__(self, token: str = "", email: str = "", password: str = ""):
        if not token and not (email and password):
            raise Exception("Need token or username and password")

        if not token and (email and password):
            token = self.cred_to_token(email, password)
        self.token = token

        self.socket_subcription: dict[str, list[EventCallBackType]] = {}
        self.discord_ws: DiscordWebsocket = DiscordWebsocket(token)
        self.discord_ws.add_close_callback(
            self.change_presence(Presence([], status="offline"))
        )
        self.discord_ws.set_event_callback(self._handle_event)

    async def _handle_event(self, payload: Payload):
        event_name = payload.t.lower()
        if event_name in self.socket_subcription:
            for func in self.socket_subcription[event_name]:
                await func(self, payload)

    def close(self):
        asyncio.create_task(self.discord_ws.close()).add_done_callback(
            lambda _: asyncio.get_event_loop().stop()
        )

    def connect(self):
        loop = asyncio.get_event_loop()
        asyncio.ensure_future(self.discord_ws.connect())
        for signal_enum in [SIGINT, SIGTERM]:
            loop.add_signal_handler(signal_enum, self.close)
        loop.run_forever()

    async def change_presence(self, presence: Presence):
        await self.discord_ws.send(OpCode.PRESENCE_UPDATE, presence.to_json())

    def cred_to_token(self, email: str, password: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.3",
        }

        req = httpx.post(
            "https://discordapp.com/api/v9/auth/login",
            json={"email": email, "password": password},
            headers=headers,
        )

        if not req.is_success:
            return ""

        req_data: dict = req.json()
        if req_data.get("token"):
            return req_data["token"]

        ticket = req_data.get("ticket")
        mfa_code = input("Need 2fa code to continue: ")
        req = httpx.post(
            "https://discord.com/api/v9/auth/mfa/totp",
            json={"ticket": ticket, "code": mfa_code},
            headers=headers,
        )

        if not req.is_success:
            return ""

        req_data = req.json()
        if req_data.get("token"):
            return req_data["token"]

        return ""

    def on_event(self, func: EventCallBackType):
        func_name = func.__name__.replace("on_", "")

        if not self.socket_subcription.get(func_name, None):
            self.socket_subcription[func_name] = []

        self.socket_subcription[func_name].append(func)
        return func
