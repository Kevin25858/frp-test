"""TCP client for FRP Monitor with reconnection and heartbeat"""

import asyncio
import time
from typing import Optional, Callable, Awaitable

from .protocol import (
    Message,
    MessageType,
    new_pong,
    new_heartbeat,
    new_probe_start,
    read_message,
    write_message,
    ProbeResult,
)


class Client:
    def __init__(self, server_addr: str, name: str):
        self.server_addr = server_addr
        self.name = name
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.last_seen = 0
        self.stop_ch: Optional[asyncio.Future] = None
        self.reconnect_backoff = 1.0
        self.max_backoff = 30.0
        self.probe_callback: Optional[Callable[[ProbeResult], None]] = None
        self._probe_result_event = asyncio.Event()
        self._last_probe_result: Optional[ProbeResult] = None

    async def connect(self) -> bool:
        """Establish TCP connection and send register message"""
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.server_addr.split(":")[0], int(self.server_addr.split(":")[1])),
                timeout=10.0
            )
            msg = Message(type=MessageType.REGISTER.value, timestamp=int(time.time() * 1000), data=self.name)
            await write_message(self.writer, msg)
            self.connected = True
            self.last_seen = int(time.time() * 1000)
            self.reconnect_backoff = 1.0
            return True
        except Exception:
            self.connected = False
            return False

    async def start(self):
        """Start the client - launches read, heartbeat, and monitor loops"""
        self.stop_ch = asyncio.Future()
        asyncio.create_task(self._read_loop())
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._monitor_loop())

    async def stop(self):
        """Stop the client gracefully"""
        if self.stop_ch:
            self.stop_ch.set_result(None)
        if self.writer:
            self.writer.close()
            await asyncio.wait_for(self.writer.wait_closed(), timeout=5.0)
        self.connected = False

    async def probe(self, addr: str, port: str, proto: str = "tcp") -> ProbeResult:
        """Send a probe request and wait for result"""
        msg = new_probe_start(addr, port, proto)
        await write_message(self.writer, msg)
        self._probe_result_event.clear()
        try:
            await asyncio.wait_for(self._probe_result_event.wait(), timeout=30.0)
            return self._last_probe_result
        except asyncio.TimeoutError:
            from .protocol import ProbeResult
            return ProbeResult(success=False, rtt_ms=0, error="timeout")

    def set_probe_callback(self, cb: Callable[["ProbeResult"], None]):
        """Set callback for async probe results"""
        self.probe_callback = cb

    async def _read_loop(self):
        """Read messages from server"""
        while not self.stop_ch.done():
            try:
                msg = await asyncio.wait_for(read_message(self.reader), timeout=30.0)
                if msg is None:
                    break
                self.last_seen = int(time.time() * 1000)
                await self._handle_message(msg)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break
        self.connected = False

    async def _handle_message(self, msg: Message):
        """Route messages by type"""
        if msg.type == MessageType.PING.value:
            pong = new_pong(msg.seq, msg.timestamp)
            await write_message(self.writer, pong)
        elif msg.type == MessageType.HEARTBEAT.value:
            pass
        elif msg.type == MessageType.PROBE_RESULT.value:
            from .protocol import ProbeResult
            result = msg.get_probe_result()
            if result:
                self._last_probe_result = result
                self._probe_result_event.set()
                if self.probe_callback:
                    self.probe_callback(result)

    async def _heartbeat_loop(self):
        """Send heartbeat every 10 seconds"""
        while not self.stop_ch.done() and self.connected:
            await asyncio.sleep(10)
            if self.connected:
                try:
                    msg = new_heartbeat()
                    await write_message(self.writer, msg)
                except Exception:
                    break

    async def _monitor_loop(self):
        """Monitor connection health, reconnect if dead"""
        while not self.stop_ch.done():
            await asyncio.sleep(5)
            if not self.connected:
                await self._try_reconnect()

    async def _try_reconnect(self):
        """Reconnect with exponential backoff"""
        while not self.connected and not self.stop_ch.done():
            await asyncio.sleep(self.reconnect_backoff)
            if await self.connect():
                asyncio.create_task(self._read_loop())
                asyncio.create_task(self._heartbeat_loop())
                break
            self.reconnect_backoff = min(self.reconnect_backoff * 2, self.max_backoff)

    async def run(self):
        """Connect, start, and wait for cancellation"""
        if not await self.connect():
            await self._try_reconnect()
        await self.start()
        try:
            await self.stop_ch
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()
