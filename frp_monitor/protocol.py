"""Protocol layer for FRP Monitor - JSON line-delimited messages"""

import json
import time
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


class MessageType(Enum):
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"
    REGISTER = "register"
    PROBE_START = "probe_start"
    PROBE_RESULT = "probe_result"


@dataclass
class ProbeRequest:
    server_addr: str
    server_port: str
    protocol: str  # "tcp" or "udp"


@dataclass
class ProbeResult:
    success: bool
    rtt_ms: float
    error: Optional[str] = None
    timestamp: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "rtt_ms": self.rtt_ms,
            "error": self.error or "",
            "ts": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProbeResult":
        return cls(
            success=d.get("success", False),
            rtt_ms=d.get("rtt_ms", 0.0),
            error=d.get("error"),
            timestamp=d.get("ts", 0),
        )


@dataclass
class Message:
    type: str
    seq: int = 0
    timestamp: int = 0
    data: Any = None

    def to_dict(self) -> dict:
        d = {
            "type": self.type,
            "ts": self.timestamp,
        }
        if self.seq != 0:
            d["seq"] = self.seq
        if self.data is not None:
            if isinstance(self.data, dict):
                d["data"] = self.data
            elif isinstance(self.data, str):
                d["data"] = self.data
            else:
                d["data"] = self.data
        return d

    def encode(self) -> bytes:
        return json.dumps(self.to_dict()).encode("utf-8") + b"\n"

    @classmethod
    def decode(cls, data: bytes) -> "Message":
        d = json.loads(data.decode("utf-8"))
        return cls(
            type=d.get("type", ""),
            seq=d.get("seq", 0),
            timestamp=d.get("ts", 0),
            data=d.get("data"),
        )

    def get_data_string(self) -> Optional[str]:
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, dict) and "data" in self.data:
            val = self.data["data"]
            if isinstance(val, str):
                return val
        return None

    def get_probe_request(self) -> Optional[ProbeRequest]:
        if self.type != MessageType.PROBE_START.value:
            return None
        if isinstance(self.data, dict):
            return ProbeRequest(
                server_addr=self.data.get("server_addr", ""),
                server_port=self.data.get("server_port", ""),
                protocol=self.data.get("protocol", "tcp"),
            )
        return None

    def get_probe_result(self) -> Optional[ProbeResult]:
        if self.type != MessageType.PROBE_RESULT.value:
            return None
        if isinstance(self.data, dict):
            return ProbeResult.from_dict(self.data)
        return None


async def read_message(reader) -> Optional[Message]:
    """Read a newline-delimited JSON message from a stream"""
    line = await reader.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    return Message.decode(line)


async def write_message(writer, msg: Message) -> None:
    """Write a message to a stream"""
    writer.write(msg.encode())
    await writer.drain()


def new_ping(seq: int) -> Message:
    return Message(
        type=MessageType.PING.value,
        seq=seq,
        timestamp=int(time.time() * 1000),
    )


def new_pong(seq: int, ts: int) -> Message:
    return Message(
        type=MessageType.PONG.value,
        seq=seq,
        timestamp=ts,
    )


def new_heartbeat() -> Message:
    return Message(
        type=MessageType.HEARTBEAT.value,
        timestamp=int(time.time() * 1000),
    )


def new_register(name: str) -> Message:
    return Message(
        type=MessageType.REGISTER.value,
        timestamp=int(time.time() * 1000),
        data=name,
    )


def new_probe_start(server_addr: str, server_port: str, protocol: str = "tcp") -> Message:
    return Message(
        type=MessageType.PROBE_START.value,
        timestamp=int(time.time() * 1000),
        data={
            "server_addr": server_addr,
            "server_port": server_port,
            "protocol": protocol,
        },
    )


def new_probe_result(success: bool, rtt_ms: float, error: str = "") -> Message:
    return Message(
        type=MessageType.PROBE_RESULT.value,
        timestamp=int(time.time() * 1000),
        data={
            "success": success,
            "rtt_ms": rtt_ms,
            "error": error,
        },
    )
