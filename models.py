import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

__all__ = ["Payload", "OpCode", "Presence", "Activity"]


class OpCode(Enum):
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE_UPDATE = 3
    VOICE_STATE = 4
    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    UNKNOWN = -1


class BaseData:
    def to_json(self) -> dict[str, Any]:
        """
        Convert the object attributes to a JSON serializable dictionary.

        Returns:
            Dict[str, Any]: The JSON serializable dictionary.
        """
        _d: dict[str, Any] = {}
        for k in self.__match_args__:  # type: ignore
            d = self.__getattribute__(k)
            if issubclass(type(d), BaseData):
                _d[k] = d.to_json()
            elif isinstance(d, list):
                _d[k] = [i.to_json() if issubclass(type(i), BaseData) else i for i in d]
            else:
                _d[k] = d
        return _d


@dataclass(slots=True)
class Payload(BaseData):
    t: str
    s: int
    op: OpCode
    d: dict[str, Any]

    def __init__(
        self, t: str = "", s: int = 0, op: OpCode = OpCode.UNKNOWN, d: dict = {}
    ):
        self.t = t if t else ""
        self.s = s if s else 0

        self.op = op if op else OpCode.UNKNOWN
        if isinstance(self.op, int):
            self.op = OpCode(self.op)

        self.d = d if d else {}

    @classmethod
    def from_str(cls, json_str: str):
        j = json.loads(json_str)
        return cls(**j)

    def __repr__(self) -> str:
        return f"t={self.t}, s={self.s}, op={self.op}, d=[{len(self.d)} bytes]"


@dataclass(slots=True)
class Properties(BaseData):
    browser: str
    device: str
    os: str


@dataclass(slots=True)
class Identify(BaseData):
    capabilities: int
    compress: bool
    largeThreshold: int
    properties: Properties
    token: str

    @classmethod
    def from_token(cls, token: str):
        return cls(
            capabilities=65,
            compress=False,
            largeThreshold=100,
            properties=Properties(
                browser="Discord Client",
                device="ktor",
                os="Windows",
            ),
            token=token,
        )


@dataclass(slots=True)
class Timestamps(BaseData):
    start: int
    end: int


@dataclass(slots=True)
class Assets(BaseData):
    largeImage: Optional[str]
    smallImage: Optional[str]
    largeText: Optional[str] = None
    smallText: Optional[str] = None


@dataclass(slots=True)
class Metadata(BaseData):
    buttonUrls: Optional[list[str]]


@dataclass(slots=True)
class Activity(BaseData):
    applicationId: str
    name: Optional[str]
    state: Optional[str] = None
    details: Optional[str] = None
    type: Optional[int] = 0
    timestamps: Optional[Timestamps] = None
    assets: Optional[Assets] = None
    buttons: Optional[list[str]] = None
    metadata: Optional[Metadata] = None
    url: Optional[str] = None


@dataclass(slots=True)
class Presence(BaseData):
    activities: list[Activity]
    afk: bool = False
    since: int = 0
    status: str = "online"
